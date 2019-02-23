""" Unit tests for `ReductionForecast`. """

import unittest
from decimal import Decimal
from collections import defaultdict
from forecaster import (
    Money, Person, ReductionForecast,
    DebtPaymentStrategy, Debt, Tax)


class TestReductionForecast(unittest.TestCase):
    """ Tests ReductionForecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Money(0): Decimal(0.5)}})
        # Debt accounts need an owner:
        self.person = Person(
            initial_year=self.initial_year,
            name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 2045",
            gross_income=Money(5200),
            tax_treatment=tax,
            payment_frequency='BW')
        # We want at least two debt accounts which are repaid
        # in different orders depending on whether the strategy
        # is avalanche or snowball.
        self.debt_small = Debt(
            owner=self.person,
            balance=Money(-1000),  # Low balance ($1000)
            rate=Decimal(0),  # Low interest (0%)
            payment_frequency='M',  # Monthly payments
            minimum_payment=Money(10)
        )
        self.debt_large = Debt(
            owner=self.person,
            balance=Money(-5000),  # High balance ($5000)
            rate=Decimal(1),  # High interest (100%)
            payment_frequency='BM',  # Bimonthly payments
            minimum_payment=Money(20)
        )
        # For additional tests, set up a debt where the
        # first $100 and half of the remaining payments
        # aren't drawn from `available`:
        self.debt_partial = Debt(
            owner=self.person,
            balance=Money(-1000),
            living_expense=Money(100),
            savings_rate=Decimal(0.5)
        )

        # Track money available for use by the forecast:
        self.available = defaultdict(lambda: Money(0))
        for i in range(26):  # biweekly inflows from employment
            self.available[Decimal(0.5 + i) / 26] += Money(150)
        for i in range(12):  # monthly living expenses:
            self.available[Decimal(i) / 12] -= Money(75)
        # The result: $3000 available
        self.total_available = sum(self.available.values())

        # Now we can set up the big-ticket items:
        self.strategy = DebtPaymentStrategy(
            DebtPaymentStrategy.strategy_avalanche)
        self.forecast = ReductionForecast(
            initial_year=self.initial_year,
            debts={self.debt_large, self.debt_small},
            debt_payment_strategy=self.strategy)

    def test_trans_avalanche(self):
        """ Test account transactions under avalanche strategy. """
        # Set up forecast:
        self.strategy = DebtPaymentStrategy(
            strategy=DebtPaymentStrategy.strategy_avalanche)
        self.forecast.debt_payment_strategy = self.strategy
        self.forecast.update_available(self.available)

        # Track total debt payments for each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        debt_small_payment = (
            self.forecast.account_transactions[self.debt_small])
        debt_large_payment = (
            self.forecast.account_transactions[self.debt_large])
        # We have $3000 available to spend on debts. Both debts
        # will get their minimum payments, and the remainder
        # will go to the large, high-interest debt:
        self.assertEqual(
            debt_small_payment,
            self.debt_small.minimum_payment)
        self.assertEqual(
            debt_large_payment,
            self.total_available - debt_small_payment)

    def test_trans_snowball(self):
        """ Test account transactions under snowball strategy. """
        # Set up forecast:
        self.strategy = DebtPaymentStrategy(
            strategy=DebtPaymentStrategy.strategy_snowball)
        self.forecast.debt_payment_strategy = self.strategy
        self.forecast.update_available(self.available)

        # Track total debt payments for each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        debt_small_payment = (
            self.forecast.account_transactions[self.debt_small])
        debt_large_payment = (
            self.forecast.account_transactions[self.debt_large])
        # We have $3000 available to spend on debts. The small,
        # low-interest debt will be fully repaid and the remainder
        # will go to the large, high-interest debt:
        # (Note that the small debt has 0% interest)
        self.assertEqual(
            debt_small_payment,
            -self.debt_small.balance)
        self.assertEqual(
            debt_large_payment,
            self.total_available - debt_small_payment)

    def test_payments_from_avail(self):
        """ Test accounts partially repaid from living expenses. """
        # Set up forecast:
        self.forecast.debts = {self.debt_partial}
        self.forecast.update_available(self.available)

        # Track total debt payments for each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        debt_payment = (
            self.forecast.account_transactions[self.debt_partial])
        debt_payment_from_available = (
            self.forecast.payments_from_available[
                self.debt_partial])
        # We have $3000 available to spend on debts. That's enough
        # to fully repay this debt. The first $100 is repaid from
        # living expenses, plus 50% of the balance:
        self.assertAlmostEqual(
            self.debt_partial.balance_at_time('end'),
            Money(0),  # fully repaid
            places=2)
        self.assertEqual(
            debt_payment_from_available,
            (debt_payment - Money(100)) * Decimal(0.5))

    def test_reduction_from_debt(self):
        """ Test contributions redirected to debt accounts. """
        # Set up forecast:
        self.forecast.debts = {self.debt_partial, self.debt_small}
        self.forecast.update_available(self.available)

        # Track total debt payments for each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        reduction_from_partial = (
            self.forecast.payments_from_available[
                self.debt_partial])
        reduction_from_small = (
            self.forecast.payments_from_available[
                self.debt_small])

        self.assertEqual(
            self.forecast.reduction_from_debt,
            reduction_from_partial + reduction_from_small)

    def test_reduction_from_other(self):
        """ Test reductions from other (user-provided) sources. """
        self.forecast.update_available(self.available)
        # Set the reduction manually:
        # (TODO: Test via input dict?)
        self.forecast.reduction_from_other = Money(100)
        # This should be reflected back when called:
        self.assertEqual(
            self.forecast.reduction_from_other,
            Money(100))

    def test_reductions(self):
        """ Test contributions redirected to debt accounts. """
        # Set up forecast:
        self.forecast.debts = {self.debt_small}
        self.forecast.update_available(self.available)
        # Manually set `other` reductions:
        self.forecast.reduction_from_other = Money(100)

        # Track total debt payments for each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        reduction_from_small = (
            self.forecast.payments_from_available[
                self.debt_small])

        self.assertEqual(
            self.forecast.reductions,
            Money(100) + reduction_from_small)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

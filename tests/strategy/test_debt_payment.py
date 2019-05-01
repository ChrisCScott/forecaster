""" Unit tests for `DebtPaymentStrategy`. """

import unittest
from decimal import Decimal
from forecaster import Person, Debt, Money, DebtPaymentStrategy, Timing
from tests.util import TestCaseTransactions


class TestDebtPaymentStrategies(TestCaseTransactions):
    """ Tests the strategies of the `DebtPaymentStrategy` class.

    In particular, this class tests various payments using various
    strategies on a stock set of (multiple) debts.
    """

    def setUp(self):
        initial_year = 2000
        person = Person(
            initial_year, 'Testy McTesterson', 1980, retirement_date=2045)

        self.timing = Timing({Decimal(0.5): 1})

        # These accounts have different rates:
        self.debt_big_high_interest = Debt(
            person,
            balance=Money(1000), rate=1, minimum_payment=Money(100),
            savings_rate=1, accelerated_payment=Money('Infinity')
        )
        self.debt_small_low_interest = Debt(
            person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            savings_rate=1, accelerated_payment=Money('Infinity')
        )
        self.debt_medium = Debt(
            person,
            balance=Money(500), rate=0.5, minimum_payment=Money(50),
            savings_rate=1, accelerated_payment=Money('Infinity')
        )

        self.debts = {
            self.debt_big_high_interest,
            self.debt_medium,
            self.debt_small_low_interest
        }

        self.strategy_avalanche = DebtPaymentStrategy(
            DebtPaymentStrategy.strategy_avalanche)
        self.strategy_snowball = DebtPaymentStrategy(
            DebtPaymentStrategy.strategy_snowball)

        self.excess = Money(10)

    def min_payment(self, debts, timing=None):
        """ Finds the minimum payment *from savings* for `accounts`. """
        if timing is None:
            timing = self.timing
        payment = Money(0)
        for debt in debts:
            # This used to be a genexp, but it's been split up to allow
            # for easier inspection.
            inflows = debt.min_inflows(timing=timing)
            inflows_non_living = sum(inflows.values()) - debt.living_expense
            inflows_savings = inflows_non_living * debt.savings_rate
            payment += max(inflows_savings, Money(0))
        return payment

    def max_payment(self, debts, timing=None):
        """ Finds the maximum payment *from savings* for `debts`. """
        if timing is None:
            timing = self.timing
        payment = Money(0)
        for debt in debts:
            # This used to be a genexp, but it's been split up to allow
            # for easier inspection.
            inflows = debt.max_inflows(timing=timing)
            inflows_non_living = sum(inflows.values()) - debt.living_expense
            inflows_savings = inflows_non_living * debt.savings_rate
            payment += max(inflows_savings, Money(0))
        return payment

    def make_available(self, total, timing=None):
        """ Generates an `available` dict of cashflows. """
        if timing is None:
            timing = self.timing
        normalization = sum(self.timing.values())
        return {
            when: total * weight / normalization
            for when, weight in timing.items()}

    def test_snowball_min_payment(self):
        """ Test strategy_snowball with the minimum payment only. """
        # Inflows will exactly match minimum payments:
        total = self.min_payment(self.debts)
        available = self.make_available(total)
        results = self.strategy_snowball(self.debts, available)
        for debt in self.debts:
            self.assertTransactions(results[debt], debt.minimum_payment)

    def test_snowball_less_than_min(self):
        """ Test strategy_snowball with less than the minimum payments. """
        # TODO: Formerly, minimums would be paid regardless of the
        # amount available. That's no longer part of the design of
        # DebtPaymentStrategy (which, like TransactionStrategy, always
        # allocates no more than the amount available.) This test needs
        # to be redesigned to confirm that:
        # 1)    The sum of amounts allocated is equal to `total`
        # 2)    The order of accounts is maintained (i.e. smallest
        #       debts repaid first)
        # To do this, we'll need to increase `total` to be a non-zero
        # number. Perhaps `min_payment({self.debt_small_low_interest})`?
        total = Money(0)
        available = self.make_available(total)
        results = self.strategy_snowball(self.debts, available)
        for debt in self.debts:
            self.assertTransactions(results[debt], debt.minimum_payment)

    def test_snowball_basic(self):
        """ Test strategy_snowball with a little more than min payments. """
        # The smallest debt should be paid first.
        total = self.min_payment(self.debts) + self.excess
        available = self.make_available(total)
        results = self.strategy_snowball(self.debts, available)
        # The smallest debt should be partially repaid:
        self.assertTransactions(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment + self.excess)
        # The medium-sized debt should get its minimum payments:
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.min_inflows())
        # The largest debt should get its minimum payments:
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.min_inflows())

    def test_snowball_close_one(self):
        """ Test strategy_snowball payments to close one debt. """
        # Pay more than the first-paid debt will accomodate.
        # The excess should go to the next-paid debt (medium).
        total = self.min_payment(
            self.debts - {self.debt_small_low_interest})
        total += self.max_payment({self.debt_small_low_interest})
        total += self.excess
        available = self.make_available(total)
        results = self.strategy_snowball(self.debts, available)
        # The smallest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflows())
        # The medium-sized debt should be partially repaid:
        self.assertTransactions(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + self.excess)
        # The largest debt should get its minimum payments:
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.min_inflows())

    def test_snowball_close_two(self):
        """ Test strategy_snowball with payments to close 2 debts. """
        # Pay more than the first and second-paid debts will accomodate.
        # The self.excess should go to the next-paid debt.
        total = self.min_payment({self.debt_big_high_interest})
        total += self.max_payment(
            self.debts - {self.debt_big_high_interest})
        total += self.excess
        available = self.make_available(total)
        results = self.strategy_snowball(self.debts, available)
        # The smallest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflows())
        # The medium-size debt should be fully repaid:
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflows())
        # The largest debt should be partially repaid:
        self.assertTransactions(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment + self.excess)

    def test_snowball_close_all(self):
        """ Test strategy_snowball with payments to close all debts. """
        # Contribute more than the total max.
        total = self.max_payment(self.debts) + self.excess
        available = self.make_available(total)
        results = self.strategy_snowball(self.debts, available)
        # Each debt should be fully repaid:
        for debt in self.debts:
            self.assertEqual(results[debt], debt.max_inflows())

    def test_avalanche_min_payment(self):
        """ Test strategy_avalanche with minimum payments only. """
        total = self.min_payment(self.debts)
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        for debt in self.debts:
            self.assertTransactions(results[debt], debt.minimum_payment)

    def test_avalanche_less_than_min(self):
        """ Test strategy_avalanche with less than the minimum payments. """
        # Minimum should still be paid
        total = Money(0)
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        for debt in self.debts:
            self.assertTransactions(results[debt], debt.minimum_payment)

    def test_avalanche_basic(self):
        """ Test strategy_avalanche with a bit more than min payments. """
        # The highest-interest debt should be paid first.
        total = self.min_payment(self.debts) + self.excess
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        self.assertTransactions(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment + self.excess)
        self.assertTransactions(
            results[self.debt_medium],
            self.debt_medium.minimum_payment,)
        self.assertTransactions(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment)

    def test_avalanche_close_one(self):
        """ Test strategy_avalanche with payments to close one debt. """
        # Pay more than the first-paid debt will accomodate.
        # The excess should go to the next-paid debt (medium).
        total = self.min_payment(self.debts - {self.debt_big_high_interest})
        total += self.max_payment({self.debt_big_high_interest})
        total += self.excess
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        # The high interest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflows())
        # The medium-interest debt should be partially repaid:
        self.assertTransactions(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + self.excess)
        # The low-interest debt should receive the minimum payment:
        self.assertTransactions(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment)

    def test_avalanche_close_two(self):
        """ Test strategy_avalanche with payments to close two debts. """
        # Pay more than the first and second-paid debts will accomodate.
        # The excess should go to the next-paid debt.
        total = self.min_payment({self.debt_small_low_interest})
        total += self.max_payment(
            self.debts - {self.debt_small_low_interest})
        total += self.excess
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        # The high interest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflows())
        # The medium interest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflows())
        # The low interest debt should be partially repaid:
        self.assertTransactions(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment + self.excess)

    def test_avalanche_close_all(self):
        """ Test strategy_avalanche with payments to close all debts. """
        # Contribute more than the total max.
        total = self.max_payment(self.debts) + self.excess
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        # All debts should be fully repaid:
        for debt in self.debts:
            self.assertEqual(results[debt], debt.max_inflows())


class TestDebtPaymentStrategyAttributes(unittest.TestCase):
    """ Tests DebtPaymentStrategy's handling of Debt attributes.

    In particular, this class tests payments against one debt at a time
    and confirms that the result is consistent with the attributes of
    the Debt (i.e. `accelerate_payment`, `savings_rate`, and
    `minimum_payment`).
    """

    def setUp(self):
        """ Sets up vars for testing. """
        person = Person(
            2000, 'Testy McTesterson', 1980, retirement_date=2045)
        self.strategy = DebtPaymentStrategy(
            DebtPaymentStrategy.strategy_avalanche
        )
        self.debt = Debt(
            person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            savings_rate=1, accelerated_payment=Money('Infinity')
        )

    def test_accel_payment_none(self):
        """ Tests payments where `accelerate_payment=Money(0)`. """
        self.debt.accelerated_payment = Money(0)
        results = self.strategy({self.debt}, Money(100))
        # If there's no acceleration, only the minimum is paid.
        self.assertEqual(results[self.debt], self.debt.min_inflows())

    def test_accel_payment_partial(self):
        """ Tests payments with finite, non-zero `accelerate_payment`. """
        self.debt.accelerated_payment = Money(20)
        results = self.strategy({self.debt}, Money(100))
        # Payment should be $20 more than the minimum:
        self.assertAlmostEqual(
            sum(results[self.debt].values()),
            self.debt.minimum_payment + Money(20),
            places=4)

    def test_accel_payment_infinity(self):
        """ Tests payments where `accelerate_payment=Money('Infinity')`. """
        self.debt.accelerated_payment = Money('Infinity')
        results = self.strategy({self.debt}, Money(50))
        self.assertAlmostEqual(
            sum(results[self.debt].values()),
            Money(50),
            places=4)

    def test_savings_rate_none(self):
        """ Tests payments where `savings_rate=0`. """
        self.debt.savings_rate = 0
        results = self.strategy({self.debt}, Money(50))
        # If savings_rate is 0, we repay the whole debt immediately.
        # TODO: Limit repayments in case where savings_rate=0
        self.assertAlmostEqual(
            sum(results[self.debt].values()),
            Money(100),
            places=4)

    def test_savings_rate_half(self):
        """ Tests payments where `savings_rate=0.5`. """
        self.debt.savings_rate = Decimal(0.5)
        results = self.strategy({self.debt}, Money(25))
        # If savings_rate is 50%, we can double the payment:
        self.assertAlmostEqual(
            sum(results[self.debt].values()),
            Money(50),
            places=4)

    def test_savings_rate_full(self):
        """ Tests payments where `savings_rate=1`. """
        self.debt.savings_rate = 1
        results = self.strategy({self.debt}, Money(50))
        # If savings_rate is 50%, we can double the payment:
        self.assertAlmostEqual(
            sum(results[self.debt].values()),
            Money(50),
            places=4)

    def test_minimum_payment(self):
        """ Tests payments of less than `minimum_payment`. """
        self.debt.minimum_payment = Money(10)
        results = self.strategy({self.debt}, Money(0))
        self.assertAlmostEqual(
            sum(results[self.debt].values()),
            Money(10),
            places=4)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

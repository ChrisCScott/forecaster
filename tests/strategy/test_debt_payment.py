""" Unit tests for `DebtPaymentStrategy`. """

import unittest
from decimal import Decimal
from forecaster import Person, Debt, DebtPaymentStrategy, Timing
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

        self.timing = Timing({0.5: 1})

        # These accounts have different rates:
        self.debt_big_high_interest = Debt(
            person,
            balance=1000, rate=1, minimum_payment=100,
            accelerated_payment=float('inf'))
        self.debt_small_low_interest = Debt(
            person,
            balance=100, rate=0, minimum_payment=10,
            accelerated_payment=float('inf'))
        self.debt_medium = Debt(
            person,
            balance=500, rate=0.5, minimum_payment=50,
            accelerated_payment=float('inf'))

        self.debts = {
            self.debt_big_high_interest,
            self.debt_medium,
            self.debt_small_low_interest}

        self.max_payments = {
            debt: self.max_payment({debt}) for debt in self.debts}
        self.min_payments = {
            debt: self.min_payment({debt}) for debt in self.debts}

        self.strategy_avalanche = DebtPaymentStrategy(
            DebtPaymentStrategy.strategy_avalanche)
        self.strategy_snowball = DebtPaymentStrategy(
            DebtPaymentStrategy.strategy_snowball)

        self.excess = 10

    def setUp_decimal(self):
        initial_year = 2000
        person = Person(
            initial_year, 'Testy McTesterson', 1980, retirement_date=2045)

        self.timing = Timing({Decimal(0.5): Decimal(1)})

        # These accounts have different rates:
        self.debt_big_high_interest = Debt(
            person,
            balance=Decimal(1000), rate=Decimal(1),
            minimum_payment=Decimal(100),
            accelerated_payment=Decimal('Infinity'),
            high_precision=Decimal)
        self.debt_small_low_interest = Debt(
            person,
            balance=Decimal(100), rate=Decimal(0),
            minimum_payment=Decimal(10),
            accelerated_payment=Decimal('Infinity'),
            high_precision=Decimal)
        self.debt_medium = Debt(
            person,
            balance=Decimal(500), rate=Decimal(0.5),
            minimum_payment=Decimal(50),
            accelerated_payment=Decimal('Infinity'),
            high_precision=Decimal)

        self.debts = {
            self.debt_big_high_interest,
            self.debt_medium,
            self.debt_small_low_interest}

        self.max_payments = {
            debt: self.max_payment({debt}) for debt in self.debts}
        self.min_payments = {
            debt: self.min_payment({debt}) for debt in self.debts}

        self.strategy_avalanche = DebtPaymentStrategy(
            DebtPaymentStrategy.strategy_avalanche, high_precision=Decimal)
        self.strategy_snowball = DebtPaymentStrategy(
            DebtPaymentStrategy.strategy_snowball, high_precision=Decimal)

        self.excess = Decimal(10)

    def min_payment(self, debts, timing=None):
        """ Finds the minimum payment *from savings* for `accounts`. """
        if timing is None:
            timing = self.timing
        return sum(
            sum(debt.min_inflows(timing=timing).values()) for debt in debts)

    def max_payment(self, debts, timing=None):
        """ Finds the maximum payment *from savings* for `debts`. """
        if timing is None:
            timing = self.timing
        return sum(
            sum(debt.max_inflows(timing=timing).values()) for debt in debts)

    def make_available(self, total, timing=None):
        """ Generates an `available` dict of cashflows. """
        if timing is None:
            timing = self.timing
        normalization = sum(timing.values())
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
        # DebtPaymentStrategy (like TransactionStrategy) always
        # allocates no more than the amount available.
        # This test confirms that:
        # 1)    The sum of amounts allocated is equal to `total`
        # 2)    The order of accounts is maintained (i.e. smallest
        #       debts repaid first)
        # To do this, we set `total` to a non-zero smaller than the
        # smallest debt's minimum payment.
        total = self.min_payments[self.debt_small_low_interest] / 2
        available = self.make_available(total)
        results = self.strategy_snowball(self.debts, available)
        # Entire repayment should go to the smallest debt:
        self.assertTransactions(
            results[self.debt_small_low_interest], total)
        # Remaining debts should receive no payments:
        if self.debt_medium in results:
            self.assertTransactions(results[self.debt_medium], 0)
        if self.debt_medium in results:
            self.assertTransactions(
                results[self.debt_big_high_interest], 0)

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
        self.assertTransactions(
            results[self.debt_medium],
            self.min_payments[self.debt_medium])
        # The largest debt should get its minimum payments:
        self.assertTransactions(
            results[self.debt_big_high_interest],
            self.min_payments[self.debt_big_high_interest])

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
        self.assertTransactions(
            results[self.debt_small_low_interest],
            self.max_payments[self.debt_small_low_interest])
        # The medium-sized debt should be partially repaid:
        self.assertTransactions(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + self.excess)
        # The largest debt should get its minimum payments:
        self.assertTransactions(
            results[self.debt_big_high_interest],
            self.min_payments[self.debt_big_high_interest])

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
        self.assertTransactions(
            results[self.debt_small_low_interest],
            self.max_payments[self.debt_small_low_interest])
        # The medium-size debt should be fully repaid:
        self.assertTransactions(
            results[self.debt_medium],
            self.max_payments[self.debt_medium])
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
            self.assertTransactions(
                results[debt], self.max_payments[debt])

    def test_avalanche_min_payment(self):
        """ Test strategy_avalanche with minimum payments only. """
        total = self.min_payment(self.debts)
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        for debt in self.debts:
            self.assertTransactions(results[debt], debt.minimum_payment)

    def test_avalanche_less_than_min(self):
        """ Test strategy_avalanche with less than the minimum payments. """
        # DebtPaymentStrategy (like TransactionStrategy) always
        # allocates no more than the amount available.
        # This test confirms that:
        # 1)    The sum of amounts allocated is equal to `total`
        # 2)    The order of accounts is maintained (i.e.
        #       highest-interest debts repaid first)
        # To do this, we set `total` to a non-zero smaller than the
        # highest-interest debt's minimum payment.
        total = self.min_payments[self.debt_big_high_interest] / 2
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        # Entire repayment should go to the highest-interest debt:
        self.assertTransactions(
            results[self.debt_big_high_interest], total)
        # Remaining debts should receive no payments:
        if self.debt_medium in results:
            self.assertTransactions(results[self.debt_medium], 0)
        if self.debt_medium in results:
            self.assertTransactions(
                results[self.debt_small_low_interest], 0)

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
            self.debt_medium.minimum_payment)
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
        self.assertTransactions(
            results[self.debt_big_high_interest],
            self.max_payments[self.debt_big_high_interest])
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
        self.assertTransactions(
            results[self.debt_big_high_interest],
            self.max_payments[self.debt_big_high_interest])
        # The medium interest debt should be fully repaid:
        self.assertTransactions(
            results[self.debt_medium],
            self.max_payments[self.debt_medium])
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
            self.assertTransactions(
                results[debt], self.max_payments[debt])

    def test_accel_payment_none(self):
        """ Tests payments where `accelerate_payment=0`. """
        # Don't allow accelerated payments and try to contribute more
        # than the minimum.
        self.debt_medium.accelerated_payment = 0
        available = self.make_available(self.debt_medium.minimum_payment * 2)
        results = self.strategy_avalanche({self.debt_medium}, available)
        # If there's no acceleration, only the minimum is paid.
        self.assertTransactions(
            results[self.debt_medium], self.debt_medium.minimum_payment)

    def test_accel_payment_finite(self):
        """ Tests payments with finite, non-zero `accelerate_payment`. """
        # Allow only $20 in accelerated payments and try to contribute
        # even more than that.
        self.debt_medium.accelerated_payment = 20
        available = self.make_available(
            self.debt_medium.minimum_payment + 40)
        results = self.strategy_avalanche({self.debt_medium}, available)
        # Payment should be $20 more than the minimum:
        self.assertTransactions(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + 20)

    def test_accel_payment_infinity(self):
        """ Tests payments where `accelerate_payment=float('inf')`. """
        # No limit on accelerated payments. Try to contribute more than
        # the debt requires to be fully repaid:
        self.debt_medium.accelerated_payment = float('inf')
        available = self.make_available(
            2 * sum(self.debt_medium.max_inflows().values()))
        results = self.strategy_avalanche({self.debt_medium}, available)
        # Payments should max out money available:
        self.assertTransactions(
            results[self.debt_medium],
            self.max_payments[self.debt_medium])

    def test_decimal(self):
        """ Tests Debt with Decimal inputs. """
        # Convert values to Decimal:
        self.setUp_decimal()

        # This test is based on test_avalanche_close_one.

        # Pay more than the first-paid debt will accomodate.
        # The excess should go to the next-paid debt (medium).
        total = self.min_payment(self.debts - {self.debt_big_high_interest})
        total += self.max_payment({self.debt_big_high_interest})
        total += self.excess
        available = self.make_available(total)
        results = self.strategy_avalanche(self.debts, available)
        # The high interest debt should be fully repaid:
        self.assertTransactions(
            results[self.debt_big_high_interest],
            self.max_payments[self.debt_big_high_interest])
        # The medium-interest debt should be partially repaid:
        self.assertTransactions(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + self.excess)
        # The low-interest debt should receive the minimum payment:
        self.assertTransactions(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

""" Unit tests for `DebtPaymentStrategy`. """

import unittest
from decimal import Decimal
from forecaster import Person, Debt, Money, DebtPaymentStrategy


class TestDebtPaymentStrategies(unittest.TestCase):
    """ Tests the strategies of the `DebtPaymentStrategy` class.

    In particular, this class tests various payments using various
    strategies on a stock set of (multiple) debts.
    """

    def setUp(self):
        initial_year = 2000
        person = Person(
            initial_year, 'Testy McTesterson', 1980, retirement_date=2045)

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

    @staticmethod
    def min_payment(debts):
        """ Finds the minimum payment *from savings* for `accounts`. """
        payment = Money(0)
        for debt in debts:
            # This used to be a genexp, but it's been split up to allow
            # for easier inspection.
            inflows = debt.min_inflows()
            inflows_non_living = sum(inflows.values()) - debt.living_expense
            inflows_savings = inflows_non_living * debt.savings_rate
            payment += max(inflows_savings, Money(0))
        return payment

    @staticmethod
    def max_payment(debts):
        """ Finds the maximum payment *from savings* for `debts`. """
        payment = Money(0)
        for debt in debts:
            # This used to be a genexp, but it's been split up to allow
            # for easier inspection.
            inflows = debt.max_inflows()
            inflows_non_living = sum(inflows.values()) - debt.living_expense
            inflows_savings = inflows_non_living * debt.savings_rate
            payment += max(inflows_savings, Money(0))
        return payment

    def test_snowball_min_payment(self):
        """ Test strategy_snowball with the minimum payment only. """
        # Inflows will exactly match minimum payments:
        payment = self.min_payment(self.debts)
        results = self.strategy_snowball(self.debts, payment)
        for debt in self.debts:
            self.assertAlmostEqual(
                sum(results[debt].values()),
                debt.minimum_payment,
                places=4)

    def test_snowball_less_than_min(self):
        """ Test strategy_snowball with less than the minimum payments. """
        # Minimum should still be paid
        payment = Money(0)
        results = self.strategy_snowball(self.debts, payment)
        for debt in self.debts:
            self.assertAlmostEqual(
                sum(results[debt].values()),
                debt.minimum_payment,
                places=4)

    def test_snowball_basic(self):
        """ Test strategy_snowball with a little more than min payments. """
        # The smallest debt should be paid first.
        payment = self.min_payment(self.debts) + self.excess
        results = self.strategy_snowball(self.debts, payment)
        # The smallest debt should be partially repaid:
        self.assertAlmostEqual(
            sum(results[self.debt_small_low_interest].values()),
            self.debt_small_low_interest.minimum_payment + self.excess,
            places=4)
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
        payment = self.min_payment(
            self.debts - {self.debt_small_low_interest})
        payment += self.max_payment({self.debt_small_low_interest})
        payment += self.excess

        results = self.strategy_snowball(self.debts, payment)
        # The smallest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflows())
        # The medium-sized debt should be partially repaid:
        self.assertAlmostEqual(
            sum(results[self.debt_medium].values()),
            self.debt_medium.minimum_payment + self.excess,
            places=4)
        # The largest debt should get its minimum payments:
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.min_inflows())

    def test_snowball_close_two(self):
        """ Test strategy_snowball with payments to close 2 debts. """
        # Pay more than the first and second-paid debts will accomodate.
        # The self.excess should go to the next-paid debt.
        payment = self.min_payment({self.debt_big_high_interest})
        payment += self.max_payment(
            self.debts - {self.debt_big_high_interest})
        payment += self.excess

        results = self.strategy_snowball(self.debts, payment)
        # The smallest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflows())
        # The medium-size debt should be fully repaid:
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflows())
        # The largest debt should be partially repaid:
        self.assertAlmostEqual(
            sum(results[self.debt_big_high_interest].values()),
            self.debt_big_high_interest.minimum_payment + self.excess,
            places=4)

    def test_snowball_close_all(self):
        """ Test strategy_snowball with payments to close all debts. """
        # Contribute more than the total max.
        payment = self.max_payment(self.debts) + self.excess
        results = self.strategy_snowball(self.debts, payment)
        # Each debt should be fully repaid:
        for debt in self.debts:
            self.assertEqual(
                results[debt],
                debt.max_inflows())

    def test_avalanche_min_payment(self):
        """ Test strategy_avalanche with minimum payments only. """
        payment = self.min_payment(self.debts)
        results = self.strategy_avalanche(self.debts, payment)
        for debt in self.debts:
            self.assertAlmostEqual(
                sum(results[debt].values()),
                debt.minimum_payment,
                places=4)

    def test_avalanche_less_than_min(self):
        """ Test strategy_avalanche with less than the minimum payments. """
        # Minimum should still be paid
        payment = Money(0)
        results = self.strategy_avalanche(self.debts, payment)
        for debt in self.debts:
            self.assertAlmostEqual(
                sum(results[debt].values()),
                debt.minimum_payment,
                places=4)

    def test_avalanche_basic(self):
        """ Test strategy_avalanche with a bit more than min payments. """
        # The highest-interest debt should be paid first.
        payment = self.min_payment(self.debts) + self.excess
        results = self.strategy_avalanche(self.debts, payment)
        self.assertAlmostEqual(
            sum(results[self.debt_big_high_interest].values()),
            self.debt_big_high_interest.minimum_payment + self.excess,
            places=4)
        self.assertAlmostEqual(
            sum(results[self.debt_medium].values()),
            self.debt_medium.minimum_payment,
            places=4)
        self.assertAlmostEqual(
            sum(results[self.debt_small_low_interest].values()),
            self.debt_small_low_interest.minimum_payment,
            places=4)

    def test_avalanche_close_one(self):
        """ Test strategy_avalanche with payments to close one debt. """
        # Pay more than the first-paid debt will accomodate.
        # The excess should go to the next-paid debt (medium).
        payment = self.min_payment(self.debts - {self.debt_big_high_interest})
        payment += self.max_payment({self.debt_big_high_interest})
        payment += self.excess

        results = self.strategy_avalanche(self.debts, payment)
        # The high interest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflows())
        # The medium-interest debt should be partially repaid:
        self.assertAlmostEqual(
            sum(results[self.debt_medium].values()),
            self.debt_medium.minimum_payment + self.excess,
            places=4)
        # The low-interest debt should receive the minimum payment:
        self.assertAlmostEqual(
            sum(results[self.debt_small_low_interest].values()),
            self.debt_small_low_interest.minimum_payment,
            places=4)

    def test_avalanche_close_two(self):
        """ Test strategy_avalanche with payments to close two debts. """
        # Pay more than the first and second-paid debts will accomodate.
        # The excess should go to the next-paid debt.
        payment = self.min_payment({self.debt_small_low_interest})
        payment += self.max_payment(
            self.debts - {self.debt_small_low_interest})
        payment += self.excess

        results = self.strategy_avalanche(self.debts, payment)
        # The high interest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflows())
        # The medium interest debt should be fully repaid:
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflows())
        # The low interest debt should be partially repaid:
        self.assertAlmostEqual(
            sum(results[self.debt_small_low_interest].values()),
            self.debt_small_low_interest.minimum_payment + self.excess,
            places=4)

    def test_avalanche_close_all(self):
        """ Test strategy_avalanche with payments to close all debts. """
        # Contribute more than the total max.
        payment = self.max_payment(self.debts) + self.excess
        results = self.strategy_avalanche(self.debts, payment)
        # All debts should be fully repaid:
        for debt in self.debts:
            self.assertEqual(
                results[debt],
                debt.max_inflows())


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

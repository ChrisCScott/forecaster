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
            reduction_rate=1, accelerate_payment=True
        )
        self.debt_small_low_interest = Debt(
            person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=1, accelerate_payment=True
        )
        self.debt_medium = Debt(
            person,
            balance=Money(500), rate=0.5, minimum_payment=Money(50),
            reduction_rate=1, accelerate_payment=True
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
    def min_payment(debts, timing):
        """ Finds the minimum payment *from savings* for `accounts`. """
        # Find the minimum payment *from savings* for each account:
        return sum(
            debt.min_inflow(timing) * debt.reduction_rate
            for debt in debts
        )

    @staticmethod
    def max_payment(debts, timing):
        """ Finds the maximum payment *from savings* for `accounts`. """
        # Find the minimum payment *from savings* for each account:
        return sum(
            debt.max_inflow(timing) * debt.reduction_rate
            for debt in debts
        )

    def test_init_implicit(self):
        """ Test __init__ with implicit (optional omitted) parameters. """
        # Pylint gets confused by attributes added via a metaclass.
        # pylint: disable=no-member
        method = DebtPaymentStrategy.strategy_avalanche.strategy_key
        strategy = DebtPaymentStrategy(method)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.timing, 'end')

    def test_init_explicit(self):
        """ Test __init__ with explicit parameters. """
        method = 'Snowball'
        timing = 'end'
        strategy = DebtPaymentStrategy(method, timing)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.timing, timing)

    def test_init_invalid(self):
        """ Test __init__ with invalid parameters. """
        # Test invalid strategies
        with self.assertRaises(ValueError):
            DebtPaymentStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            DebtPaymentStrategy(strategy=1)
        # Test invalid timing
        with self.assertRaises(TypeError):
            DebtPaymentStrategy(strategy="Snowball", timing={})

    def test_snowball_min_payment(self):
        """ Test strategy_snowball with the minimum payment only. """
        payment = self.min_payment(
            self.debts, self.strategy_snowball.timing)
        results = self.strategy_snowball(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

    def test_snowball_less_than_min(self):
        """ Test strategy_snowball with less than the minimum payments. """
        # Minimum should still be paid
        payment = Money(0)
        results = self.strategy_snowball(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

    def test_snowball_basic(self):
        """ Test strategy_snowball with a little more than min payments. """
        # The smallest debt should be paid first.
        payment = self.min_payment(
            self.debts, self.strategy_snowball.timing
        ) + self.excess
        results = self.strategy_snowball(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment + self.excess
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment
        )

    def test_snowball_close_one(self):
        """ Test strategy_snowball payments to close one debt. """
        # Pay more than the first-paid debt will accomodate.
        # The excess should go to the next-paid debt (medium).
        payment = (
            self.min_payment(
                self.debts - {self.debt_small_low_interest},
                self.strategy_snowball.timing
            ) + self.max_payment(
                {self.debt_small_low_interest},
                self.strategy_snowball.timing
            ) + self.excess
        )
        results = self.strategy_snowball(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflow(
                self.strategy_snowball.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + self.excess
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment
        )

    def test_snowball_close_two(self):
        """ Test strategy_snowball with payments to close 2 debts. """
        # Pay more than the first and second-paid debts will accomodate.
        # The self.excess should go to the next-paid debt.
        payment = (
            self.min_payment(
                {self.debt_big_high_interest},
                self.strategy_snowball.timing
            ) + self.max_payment(
                self.debts - {self.debt_big_high_interest},
                self.strategy_snowball.timing
            ) + self.excess
        )
        results = self.strategy_snowball(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflow(
                self.strategy_snowball.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflow(self.strategy_snowball.timing)
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment + self.excess
        )

    def test_snowball_close_all(self):
        """ Test strategy_snowball with payments to close all debts. """
        # Contribute more than the total max.
        payment = (
            self.max_payment(self.debts, self.strategy_snowball.timing)
            + self.excess)
        results = self.strategy_snowball(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(
                results[debt],
                debt.max_inflow(self.strategy_snowball.timing))

    def test_avalanche_min_payment(self):
        """ Test strategy_avalanche with minimum payments only. """
        payment = self.min_payment(
            self.debts, self.strategy_avalanche.timing)
        results = self.strategy_avalanche(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

    def test_avalanche_less_than_min(self):
        """ Test strategy_avalanche with less than the minimum payments. """
        # Minimum should still be paid
        payment = Money(0)
        results = self.strategy_avalanche(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

    def test_avalanche_basic(self):
        """ Test strategy_avalanche with a bit more than min payments. """
        # The highest-interest debt should be paid first.
        payment = self.min_payment(
            self.debts, self.strategy_avalanche.timing
        ) + self.excess
        results = self.strategy_avalanche(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment + self.excess
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment
        )

    def test_avalanche_close_one(self):
        """ Test strategy_avalanche with payments to close one debt. """
        # Pay more than the first-paid debt will accomodate.
        # The excess should go to the next-paid debt (medium).
        payment = (
            self.min_payment(
                self.debts - {self.debt_big_high_interest},
                self.strategy_avalanche.timing
            ) + self.max_payment(
                {self.debt_big_high_interest},
                self.strategy_avalanche.timing
            ) + self.excess
        )
        results = self.strategy_avalanche(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflow(
                self.strategy_avalanche.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + self.excess
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment
        )

    def test_avalanche_close_two(self):
        """ Test strategy_avalanche with payments to close two debts. """
        # Pay more than the first and second-paid debts will accomodate.
        # The excess should go to the next-paid debt.
        payment = (
            self.min_payment(
                {self.debt_small_low_interest}, self.strategy_avalanche.timing
            ) + self.max_payment(
                self.debts - {self.debt_small_low_interest},
                self.strategy_avalanche.timing
            ) + self.excess
        )
        results = self.strategy_avalanche(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflow(
                self.strategy_avalanche.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflow(self.strategy_avalanche.timing)
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment + self.excess
        )

    def test_avalanche_close_all(self):
        """ Test strategy_avalanche with payments to close all debts. """
        # Contribute more than the total max.
        payment = self.max_payment(
            self.debts, self.strategy_avalanche.timing
        ) + self.excess
        results = self.strategy_avalanche(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(
                results[debt],
                debt.max_inflow(self.strategy_avalanche.timing)
            )


class TestDebtPaymentStrategyAttributes(unittest.TestCase):
    """ Tests DebtPaymentStrategy's handling of Debt attributes.

    In particular, this class tests payments against one debt at a time
    and confirms that the result is consistent with the attributes of
    the Debt (i.e. `accelerate_payment`, `reduction_rate`, and
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
            reduction_rate=1, accelerate_payment=True
        )

    def test_accelerate_payment_false(self):
        """ Tests payments to a `Debt` where `accelerate_payment=False`. """
        self.debt.accelerate_payment = False
        results = self.strategy(Money(100), {self.debt})
        # If there's no acceleration, only the minimum is paid.
        self.assertEqual(results[self.debt], self.debt.minimum_payment)

    def test_accelerate_payment_true(self):
        """ Tests payments to a `Debt` where `accelerate_payment=True`. """
        self.debt.accelerate_payment = True
        results = self.strategy(Money(50), {self.debt})
        self.assertEqual(results[self.debt], Money(50))

    def test_reduction_rate_none(self):
        """ Tests payments to a `Debt` where `reduction_rate=0`. """
        self.debt.reduction_rate = 0
        results = self.strategy(Money(50), {self.debt})
        # If reduction_rate is 0, we repay the whole debt immediately.
        # TODO: Change this behaviour
        self.assertEqual(results[self.debt], Money(100))

    def test_reduction_rate_half(self):
        """ Tests payments to a `Debt` where `reduction_rate=0.5`. """
        self.debt.reduction_rate = Decimal(0.5)
        results = self.strategy(Money(25), {self.debt})
        # If reduction_rate is 50%, we can double the payment:
        self.assertEqual(results[self.debt], Money(50))

    def test_reduction_rate_full(self):
        """ Tests payments to a `Debt` where `reduction_rate=1`. """
        self.debt.reduction_rate = 1
        results = self.strategy(Money(50), {self.debt})
        # If reduction_rate is 50%, we can double the payment:
        self.assertEqual(results[self.debt], Money(50))

    def test_minimum_payment(self):
        """ Tests payments of less than `minimum_payment`. """
        self.debt.minimum_payment = Money(10)
        results = self.strategy(Money(0), {self.debt})
        self.assertEqual(results[self.debt], Money(10))

if __name__ == '__main__':
    unittest.main()

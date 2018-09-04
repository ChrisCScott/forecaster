""" TODO """

import unittest
import decimal
from decimal import Decimal
from forecaster import Person, Debt, Money

class TestDebtMethods(unittest.TestCase):
    """ Test Debt. """

    def setUp(self):
        """ Sets up class attributes for convenience. """
        super().setUp()
        # We use caps because this is a type.
        # pylint: disable=invalid-name
        self.AccountType = Debt
        # pylint: enable=invalid-name

        # It's important to synchronize the initial years of related
        # objects, so store it here:
        self.initial_year = 2000
        # Every init requires an owner, so store that here:
        self.owner = Person(
            self.initial_year, "test", 2000,
            raise_rate={year: 1 for year in range(2000, 2066)},
            retirement_date=2065)

        # Debt takes three args: reduction_rate (Decimal),
        # minimum_payment (Money), and accelerate_payment (bool)
        self.minimum_payment = Money(10)
        self.reduction_rate = Decimal(1)
        self.accelerate_payment = True

    def test_init(self, *args, **kwargs):
        """ Test Debt.__init__ """
        # Don't call the superclass init, since it's based on positive
        # balances.
        # super().test_init(*args, **kwargs)

        # Test default init.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.minimum_payment, Money(0))
        self.assertEqual(account.reduction_rate, 1)
        self.assertEqual(account.accelerated_payment, Money('Infinity'))

        # Test init with appropriate-type args.
        minimum_payment = Money(100)
        reduction_rate = Decimal(1)
        accelerated_payment = Money(0)
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=minimum_payment, reduction_rate=reduction_rate,
            accelerated_payment=accelerated_payment, **kwargs)
        self.assertEqual(account.minimum_payment, minimum_payment)
        self.assertEqual(account.reduction_rate, reduction_rate)
        self.assertEqual(account.accelerated_payment, accelerated_payment)

        # Test init with args of alternative types.
        minimum_payment = 100
        reduction_rate = 1
        accelerated_payment = 10
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=minimum_payment, reduction_rate=reduction_rate,
            accelerated_payment=accelerated_payment, **kwargs)
        self.assertEqual(account.minimum_payment, minimum_payment)
        self.assertEqual(account.reduction_rate, reduction_rate)
        self.assertEqual(
            account.accelerated_payment, Money(accelerated_payment))

        # Test init with args of non-convertible types
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                minimum_payment='invalid', **kwargs)
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                reduction_rate='invalid', **kwargs)
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                accelerated_payment='invalid', **kwargs)

    def test_max_inflow_large_balance(self, *args, **kwargs):
        """ Test `max_inflow` with balance greater than minimum payment. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=-1000, **kwargs)
        self.assertEqual(account.max_inflow(), Money(1000))

    def test_max_inflow_small_balance(self, *args, **kwargs):
        """ Test `max_inflow` with balance less than minimum payment. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=1000, balance=-100, **kwargs)
        self.assertEqual(account.max_inflow(), Money(100))

    def test_max_inflow_zero_balance(self, *args, **kwargs):
        """ Test `max_inflow` with zero balance. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=0, **kwargs)
        self.assertEqual(account.max_inflow(), Money(0))

    def test_max_inflow_no_accel(self, *args, **kwargs):
        """ Test `max_inflow` with zero `accelerated_payment`. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=200, accelerated_payment=0, **kwargs)
        self.assertEqual(account.max_inflow(), Money(100))

    def test_max_inflow_partial_accel(self, *args, **kwargs):
        """ Test `max_inflow` with finite `accelerated_payment`. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=200, accelerated_payment=50, **kwargs)
        self.assertEqual(account.max_inflow(), Money(150))

    def test_max_inflow_small_inflow(self, *args, **kwargs):
        """ Test `max_inflow` with inflows less than the total max. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=200, accelerated_payment=50, **kwargs)
        account.add_transaction(60)
        self.assertEqual(account.max_inflow(), Money(90))

    def test_max_inflow_large_inflow(self, *args, **kwargs):
        """ Test `max_inflow` with inflows greater than the total max. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=200, accelerated_payment=50, **kwargs)
        account.add_transaction(170)
        # Should not return a negative number:
        self.assertEqual(account.max_inflow(), Money(0))

    def test_min_inflow_large_balance(self, *args, **kwargs):
        """ Test `min_inflow` with balance greater than min. payment. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=-1000, **kwargs)
        self.assertEqual(account.min_inflow(), Money(100))

    def test_min_inflow_small_balance(self, *args, **kwargs):
        """ Test `min_inflow` with balance less than min. payment. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=1000, balance=-100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(100))

    def test_min_inflow_zero_balance(self, *args, **kwargs):
        """ Test `min_inflow` with zero balance. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=0, **kwargs)
        self.assertEqual(account.min_inflow(), Money(0))

    def test_min_inflow_small_inflow(self, *args, **kwargs):
        """ Test `min_inflow` with inflows less than the min. payment. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=10, balance=-100, **kwargs)
        account.add_transaction(5)
        self.assertEqual(account.min_inflow(), Money(5))

    def test_min_inflow_large_inflow(self, *args, **kwargs):
        """ Test `min_inflow` with inflows more than the min. payment. """
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=10, balance=-100, **kwargs)
        account.add_transaction(20)
        self.assertEqual(account.min_inflow(), Money(0))

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

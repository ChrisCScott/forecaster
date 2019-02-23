""" Unit tests for `Debt`. """

import unittest
import decimal
from decimal import Decimal
from forecaster import Person, Debt, Money

# Unlike other Account subclasses, we don't subclass
# from TestAccountMethods. Most of those tests are
# inapplicable because they balances of debts are
# negative.
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

        # Basic Debt account:
        self.debt = Debt(
            self.owner,
            balance=-1000,
            minimum_payment=Money(10),
            living_expense=Money(0),
            savings_rate=Decimal('0.5'),
            accelerated_payment=Money('Infinity')
        )

    def test_init_default(self):
        """ Test Debt.__init__ with default args. """
        account = self.AccountType(
            self.owner)
        self.assertEqual(account.minimum_payment, Money(0))
        self.assertEqual(account.savings_rate, 1)
        self.assertEqual(account.accelerated_payment, Money('Infinity'))

    def test_init_explicit(self, *args, **kwargs):
        """ Test Debt.__init__ with explicit args of expected types. """
        minimum_payment = Money(100)
        reduction_rate = Decimal(1)
        accelerated_payment = Money(0)
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=minimum_payment, savings_rate=reduction_rate,
            accelerated_payment=accelerated_payment, **kwargs)
        self.assertEqual(account.minimum_payment, minimum_payment)
        self.assertEqual(account.savings_rate, reduction_rate)
        self.assertEqual(account.accelerated_payment, accelerated_payment)

    def test_init_convert(self, *args, **kwargs):
        """ Test Debt.__init__ with args needing conversion. """
        minimum_payment = 100
        reduction_rate = 1
        accelerated_payment = 10
        living_expense = '1000'
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=minimum_payment,
            living_expense=living_expense,
            savings_rate=reduction_rate,
            accelerated_payment=accelerated_payment,
            **kwargs)
        self.assertEqual(account.minimum_payment, minimum_payment)
        self.assertEqual(account.savings_rate, reduction_rate)
        self.assertEqual(
            account.accelerated_payment, Money(accelerated_payment))
        self.assertEqual(account.living_expense, Money(living_expense))

    def test_init_invalid(self, *args, **kwargs):
        """ Test Debt.__init__ with non-convertible args. """
        with self.assertRaises(decimal.InvalidOperation):
            _ = self.AccountType(
                self.owner, *args,
                minimum_payment='invalid', **kwargs)
        with self.assertRaises(decimal.InvalidOperation):
            _ = self.AccountType(
                self.owner, *args,
                savings_rate='invalid', **kwargs)
        with self.assertRaises(decimal.InvalidOperation):
            _ = self.AccountType(
                self.owner, *args,
                accelerated_payment='invalid', **kwargs)
        with self.assertRaises(decimal.InvalidOperation):
            _ = self.AccountType(
                self.owner, *args,
                living_expense='invalid', **kwargs)

    def test_max_inflow_large_balance(self):
        """ Test `max_inflow` with balance greater than minimum payment. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-1000)
        self.assertEqual(self.debt.max_inflow(), Money(1000))

    def test_max_inflow_small_balance(self):
        """ Test `max_inflow` with balance less than minimum payment. """
        self.debt.minimum_payment = 1000
        self.debt.balance = Money(-100)
        self.assertEqual(self.debt.max_inflow(), Money(100))

    def test_max_inflow_zero_balance(self):
        """ Test `max_inflow` with zero balance. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(0)
        self.assertEqual(self.debt.max_inflow(), Money(0))

    def test_max_inflow_no_accel(self):
        """ Test `max_inflow` with zero `accelerated_payment`. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-200)
        self.debt.accelerated_payment = 0
        self.assertEqual(self.debt.max_inflow(), Money(100))

    def test_max_inflow_partial_accel(self):
        """ Test `max_inflow` with finite `accelerated_payment`. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-200)
        self.debt.accelerated_payment = 50
        self.assertEqual(self.debt.max_inflow(), Money(150))

    def test_max_inflow_small_inflow(self):
        """ Test `max_inflow` with inflows less than the total max. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-200)
        self.debt.accelerated_payment = 50
        self.debt.add_transaction(60)
        self.assertEqual(self.debt.max_inflow(), Money(90))

    def test_max_inflow_large_inflow(self):
        """ Test `max_inflow` with inflows greater than the total max. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-200)
        self.debt.accelerated_payment = 0
        self.debt.add_transaction(170)
        # Should not return a negative number:
        self.assertEqual(self.debt.max_inflow(), Money(0))

    def test_min_inflow_large_balance(self):
        """ Test `min_inflow` with balance greater than min. payment. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-1000)
        self.assertEqual(self.debt.min_inflow(), Money(100))

    def test_min_inflow_small_balance(self):
        """ Test `min_inflow` with balance less than min. payment. """
        self.debt.minimum_payment = 1000
        self.debt.balance = Money(-100)
        self.assertEqual(self.debt.min_inflow(), Money(100))

    def test_min_inflow_zero_balance(self):
        """ Test `min_inflow` with zero balance. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(0)
        self.assertEqual(self.debt.min_inflow(), Money(0))

    def test_min_inflow_small_inflow(self):
        """ Test `min_inflow` with inflows less than the min. payment. """
        self.debt.minimum_payment = 10
        self.debt.balance = Money(-100)
        self.debt.add_transaction(5)
        self.assertEqual(self.debt.min_inflow(), Money(5))

    def test_min_inflow_large_inflow(self):
        """ Test `min_inflow` with inflows more than the min. payment. """
        self.debt.minimum_payment = 10
        self.debt.balance = Money(-100)
        self.debt.add_transaction(20)
        self.assertEqual(self.debt.min_inflow(), Money(0))

    def test_payment_basic(self):
        """ Test `payment` for account with only `savings_rate` set. """
        payment = self.debt.payment(
            savings_available=100,
            living_expenses_available=100,
            other_payments=0,
            when='end')
        self.assertEqual(payment, Money(200))

    def test_payment_savings_limited(self):
        """ Test `payment` limited by available savings amounts. """
        payment = self.debt.payment(
            savings_available=50,
            living_expenses_available=100,
            other_payments=0,
            when='end')
        self.assertEqual(payment, Money(100))

    def test_payment_living_limited(self):
        """ Test `payment` limited by available living amounts. """
        payment = self.debt.payment(
            savings_available=100,
            living_expenses_available=50,
            other_payments=0,
            when='end')
        self.assertEqual(payment, Money(100))

    def test_payment_accel_limited(self):
        """ Test `payment` limited by `accelerated_payment`. """
        self.debt.minimum_payment = 100
        self.debt.accelerated_payment = 100
        # Should be min + accel, so $200.
        payment = self.debt.payment(
            savings_available=1000,
            living_expenses_available=1000,
            other_payments=0,
            when='end')
        self.assertEqual(payment, Money(200))

    def test_payment_balance_limited(self):
        """ Test `payment` limited by `balance`. """
        self.debt.balance = Money(-100)
        # Balance is $100, so that's the payment.
        payment = self.debt.payment(
            savings_available=1000,
            living_expenses_available=1000,
            other_payments=0,
            when='end')
        self.assertEqual(payment, Money(100))

    def test_payment_other_limited(self):
        """ Test `payment` limited by `other_payment`. """
        self.debt.minimum_payment = 100
        self.debt.accelerated_payment = 100
        # Max payment is $200, so we'll set $200 of other payments.
        payment = self.debt.payment(
            savings_available=1000,
            living_expenses_available=1000,
            other_payments=200,
            when='end')
        self.assertEqual(payment, Money(0))

    def test_payment_inflow_limited(self):
        """ Test `payment` limited by `account.inflows`. """
        self.debt.minimum_payment = 100
        self.debt.accelerated_payment = 100
        self.debt.add_transaction(Money(200), when='start')
        # Max payment is $200, there should be $0 left of payments.
        payment = self.debt.payment(
            savings_available=1000,
            living_expenses_available=1000,
            other_payments=0,
            when='end')
        self.assertEqual(payment, Money(0))

    def test_payment_savings_only(self):
        """ Test `payment` with `savings_rate=1`. """
        self.debt.savings_rate = 1
        payment = self.debt.payment(
            savings_available=100,
            living_expenses_available=100,
            other_payments=0,
            when='end')
        self.assertEqual(payment, Money(100))

    def test_payment_living_only(self):
        """ Test `payment` with `savings_rate=0`. """
        self.debt.savings_rate = 0
        payment = self.debt.payment(
            savings_available=200,
            living_expenses_available=100,
            other_payments=0,
            when='end')
        self.assertEqual(payment, Money(100))

    def test_payment_complex(self):
        """ Test `payment` with all args to non-default values. """
        self.debt.minimum_payment = 100
        self.debt.living_expense = 100
        self.debt.savings_rate = Decimal('0.75')
        self.debt.accelerated_payment = 500
        self.debt.add_transaction(20)
        # We'll use $30 of living expenses first (after accounting
        # for $50 in other payments and $20 of inflows),
        # then use $100 of living expenses and $300 of savings
        # for a total of $430 in payments
        payment = self.debt.payment(
            savings_available=300,
            living_expenses_available=250,
            other_payments=50,
            when='end')
        self.assertEqual(payment, Money(430))

    def test_payment_from_savings(self):
        """ Test `payment_from_savings`. """
        self.debt.savings_rate = Decimal('0.5')
        self.debt.living_expense = 100
        # An existing payment consumes $60 of the living expense
        # amount, so of this $200 payment $40 goes to living
        # expenses and $160 is split 50-50, leaving $80 to come
        # from savings
        payment = self.debt.payment_from_savings(
            amount=Money(200), base=Money(60))
        self.assertEqual(payment, Money(80))


if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

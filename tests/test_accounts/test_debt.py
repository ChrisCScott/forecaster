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

        # We'll also need a timing value for various tests.
        # Use two inflows, at the start and end, evenly weighted:
        self.timing = {Decimal(0): 1, Decimal(1): 1}

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

    def test_max_inflows_large_balance(self):
        """ Test `max_inflows` with balance greater than min. payment. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-1000)
        result = self.debt.max_inflows(self.timing)
        # Test result by adding those transactions to the account
        # and confirming that it brings the balance to $0:
        for when, value in result.items():
            self.debt.add_transaction(value, when=when)
        balance = self.debt.balance_at_time('end')
        self.assertAlmostEqual(balance, Money(0))

    def test_max_inflows_small_balance(self):
        """ Test `max_inflows` with balance less than minimum payment. """
        self.debt.minimum_payment = 1000
        self.debt.balance = Money(-100)
        result = self.debt.max_inflows(self.timing)
        for when, value in result.items():
            self.debt.add_transaction(value, when=when)
        # Result of `max_outflows` should bring balance to $0 if
        # applied as transactions:
        self.assertAlmostEqual(self.debt.balance_at_time('end'), Money(0))

    def test_max_inflows_zero_balance(self):
        """ Test `max_inflows` with zero balance. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(0)
        result = self.debt.max_inflows(self.timing)
        for value in result.values():
            self.assertEqual(value, Money(0))

    def test_max_inflows_no_accel(self):
        """ Test `max_inflows` with zero `accelerated_payment`. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-200)
        self.debt.accelerated_payment = 0
        result = self.debt.max_inflows(self.timing)
        # Total inflows should be limited to minimum_payment:
        self.assertEqual(sum(result.values()), self.debt.minimum_payment)

    def test_max_inflows_finite_accel(self):
        """ Test `max_inflows` with finite `accelerated_payment`. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-200)
        self.debt.accelerated_payment = 50
        result = self.debt.max_inflows(self.timing)
        # Total inflows should be limited to min. payment + accel:
        self.assertEqual(
            sum(result.values()),
            self.debt.minimum_payment + self.debt.accelerated_payment)

    def test_max_inflows_small_inflow(self):
        """ Test `max_inflows` with small pre-existing inflows. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-200)
        self.debt.accelerated_payment = 50
        # Add an inflow that's less than the total that we could pay:
        self.debt.add_transaction(60)
        result = self.debt.max_inflows(self.timing)
        target = (
            self.debt.minimum_payment
            + self.debt.accelerated_payment
            - Money(60))  # Amount already added
        # Total inflows should be limited to amount remaining after
        # existing transactions, up to min. payment + accel:
        self.assertEqual(sum(result.values()), target)

    def test_max_inflows_large_inflow(self):
        """ Test `max_inflows` with inflows greater than the total max. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-200)
        self.debt.accelerated_payment = 0
        # Add an inflow that's more than the total that we can pay:
        self.debt.add_transaction(170)
        result = self.debt.max_inflows(self.timing)
        target = Money(0)  # We can't add any more
        # The result should be $0, not a negative value:
        self.assertEqual(sum(result.values()), target)

    def test_min_inflows_large_balance(self):
        """ Test `min_inflows` with balance greater than min. payment. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(-1000)
        result = self.debt.min_inflows(self.timing)
        # Inflows should be capped at minimum payment:
        self.assertEqual(sum(result.values()), self.debt.minimum_payment)

    def test_min_inflows_small_balance(self):
        """ Test `min_inflows` with balance less than min. payment. """
        self.debt.minimum_payment = 1000
        self.debt.balance = Money(-100)
        # The resuls will be impacted by the timing of outflows, so
        # pick a specific timing here: a lump sum at end of year.
        timing = {Decimal(1): 1}
        result = self.debt.min_inflows(timing)
        # Inflows should be capped at the balance at the time the
        # transaction was made (i.e. $100):
        self.assertEqual(-sum(result.values()), self.debt.balance_at_time(1))

    def test_min_inflows_zero_balance(self):
        """ Test `min_inflows` with zero balance. """
        self.debt.minimum_payment = 100
        self.debt.balance = Money(0)
        result = self.debt.min_inflows(self.timing)
        # No inflows should be made to a fully-paid debt:
        self.assertEqual(sum(result.values()), Money(0))

    def test_min_inflows_small_inflow(self):
        """ Test `min_inflows` with small pre-existing inflows. """
        self.debt.minimum_payment = 10
        self.debt.balance = Money(-100)
        # Add inflow less than the min. payment:
        self.debt.add_transaction(5)
        result = self.debt.min_inflows(self.timing)
        # We only need to add another $5 to reach the min. payment:
        self.assertEqual(sum(result.values()), Money(5))

    def test_min_inflows_large_inflow(self):
        """ Test `min_inflows` with inflows more than the min. payment. """
        self.debt.minimum_payment = 10
        self.debt.balance = Money(-100)
        # Add inflow greater than the min. payment:
        self.debt.add_transaction(20)
        result = self.debt.min_inflows(self.timing)
        # No need to add any more payments to reach the minimum:
        self.assertEqual(sum(result.values()), Money(0))

    def test_payment_basic(self):
        """ Test `payment` for account with only `savings_rate` set. """
        payment = self.debt.max_payment(
            savings_available=100,
            living_expenses_available=100,
            other_payments=0,
            timing='end')
        self.assertEqual(payment, Money(200))

    def test_payment_savings_limited(self):
        """ Test `payment` limited by available savings amounts. """
        payment = self.debt.max_payment(
            savings_available=50,
            living_expenses_available=100,
            other_payments=0,
            timing='end')
        self.assertEqual(payment, Money(100))

    def test_payment_living_limited(self):
        """ Test `payment` limited by available living amounts. """
        payment = self.debt.max_payment(
            savings_available=100,
            living_expenses_available=50,
            other_payments=0,
            timing='end')
        self.assertEqual(payment, Money(100))

    def test_payment_accel_limited(self):
        """ Test `payment` limited by `accelerated_payment`. """
        self.debt.minimum_payment = 100
        self.debt.accelerated_payment = 100
        # Should be min + accel, so $200.
        payment = self.debt.max_payment(
            savings_available=1000,
            living_expenses_available=1000,
            other_payments=0,
            timing='end')
        self.assertEqual(payment, Money(200))

    def test_payment_balance_limited(self):
        """ Test `payment` limited by `balance`. """
        self.debt.balance = Money(-100)
        # Balance is $100, so that's the payment.
        payment = self.debt.max_payment(
            savings_available=1000,
            living_expenses_available=1000,
            other_payments=0,
            timing='end')
        self.assertEqual(payment, Money(100))

    def test_payment_other_limited(self):
        """ Test `payment` limited by `other_payment`. """
        self.debt.minimum_payment = 100
        self.debt.accelerated_payment = 100
        # Max payment is $200, so we'll set $200 of other payments.
        payment = self.debt.max_payment(
            savings_available=1000,
            living_expenses_available=1000,
            other_payments=200,
            timing='end')
        self.assertEqual(payment, Money(0))

    def test_payment_inflow_limited(self):
        """ Test `payment` limited by `account.inflows`. """
        self.debt.minimum_payment = 100
        self.debt.accelerated_payment = 100
        self.debt.add_transaction(Money(200), when='start')
        # Max payment is $200, there should be $0 left of payments.
        payment = self.debt.max_payment(
            savings_available=1000,
            living_expenses_available=1000,
            other_payments=0,
            timing='end')
        self.assertEqual(payment, Money(0))

    def test_payment_savings_only(self):
        """ Test `payment` with `savings_rate=1`. """
        self.debt.savings_rate = 1
        payment = self.debt.max_payment(
            savings_available=100,
            living_expenses_available=100,
            other_payments=0,
            timing='end')
        self.assertEqual(payment, Money(100))

    def test_payment_living_only(self):
        """ Test `payment` with `savings_rate=0`. """
        self.debt.savings_rate = 0
        payment = self.debt.max_payment(
            savings_available=200,
            living_expenses_available=100,
            other_payments=0,
            timing='end')
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
        payment = self.debt.max_payment(
            savings_available=300,
            living_expenses_available=250,
            other_payments=50,
            timing='end')
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

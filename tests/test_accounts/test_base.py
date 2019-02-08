""" Tests forecaster.accounts.base. """

import unittest
import math
import decimal
from decimal import Decimal
from forecaster import (
    Person, Account, Money, Scenario, AllocationStrategy)
from forecaster.utility import when_conv
from tests.test_helper import type_check

class TestAccountMethods(unittest.TestCase):
    """ A test suite for the `Account` class.

    For each Account subclass, create a test case that subclasses from
    this (or an intervening subclass). Then, in the setUp method,
    assign to class attributes `args`, and/or `kwargs` to
    determine which arguments will be prepended, postpended, or added
    via keyword when an instance of the subclass is initialized.
    Don't forget to also assign the subclass your're testing to
    `self.AccountType`, and to run `super().setUp()` at the top!

    This way, the methods of this class will still be called even for
    subclasses with mandatory positional arguments. You should still
    override the relevant methods to test subclass-specific logic (e.g.
    if the subclass modifies the treatment of the `rate` attribute
    based on an init arg, you'll want to test that by overriding
    `test_rate`)
    """

    def setUp(self):
        """ Sets up some class-specific variables for calling methods. """
        # We use caps because this is a type.
        # pylint: disable=invalid-name
        self.AccountType = Account
        # pylint: enable=invalid-name

        # It's important to synchronize the initial years of related
        # objects, so store it here:
        self.initial_year = 2000
        # Every init requires an owner, so store that here:
        self.scenario = Scenario(
            inflation=0,
            stock_return=1,
            bond_return=0.5,
            other_return=0,
            management_fees=0.03125,
            initial_year=self.initial_year,
            num_years=100)
        self.allocation_strategy = AllocationStrategy(
            strategy=AllocationStrategy.strategy_n_minus_age,
            min_equity=Decimal(0.5),
            max_equity=Decimal(0.5),
            target=Decimal(0.5),
            standard_retirement_age=65,
            risk_transition_period=20,
            adjust_for_retirement_plan=False)
        self.owner = Person(
            self.initial_year, "test", 2000,
            raise_rate={year: 1 for year in range(2000, 2066)},
            retirement_date=2065)

        # Inheriting classes should assign to self.account with an
        # instance of an appropriate subclass of Account.
        self.account = Account(self.owner, balance=100, rate=1.0)

    def test_init_basic(self, *args, **kwargs):
        """ Tests Account.__init__ """
        # Basic test: All correct values, check for equality and type
        owner = self.owner
        balance = Money(0)
        rate = 1.0
        nper = 1  # This is the easiest case to test
        initial_year = self.initial_year
        account = self.AccountType(
            owner, *args, balance=balance, rate=rate, nper=nper, **kwargs)
        # Test primary attributes
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        self.assertEqual(account.balance_history, {initial_year: balance})
        self.assertEqual(account.rate_history, {initial_year: rate})
        self.assertEqual(account.transactions_history, {
            initial_year: {}
        })
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, rate)
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, initial_year)
        self.assertEqual(account.this_year, initial_year)

        # Check types
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        self.assertTrue(type_check(account.balance_history, {int: Money}))
        self.assertIsInstance(account.balance, Money)
        self.assertTrue(type_check(account.rate_history, {int: Decimal}))
        self.assertIsInstance(account.rate, Decimal)
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.initial_year, int)

    def test_init_rate_function(self, *args, **kwargs):
        """ Tests using a function as an input for arg `rate`. """
        # Infer the rate from the account owner's asset allocation
        # (which is 50% stocks, 50% bonds, with 75% return overall)
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        balance = 0
        rate = self.allocation_strategy.rate_function(
            self.owner, self.scenario)
        account = self.AccountType(
            self.owner, *args, balance=balance, rate=rate, **kwargs)
        self.assertEqual(account.balance_history, {
            self.initial_year: balance})
        self.assertEqual(account.transactions_history, {
            self.initial_year: {}})
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, Decimal(0.75))
        self.assertEqual(account.rate_history,
                         {self.initial_year: Decimal(0.75)})
        self.assertEqual(account.transactions, {})
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, self.initial_year)
        self.assertEqual(account.rate_callable, rate)

    def test_init_type_conversion(self, *args, **kwargs):
        """ Tests using (Decimal-convertible) strings as input. """
        balance = "0"
        rate = "1.0"
        nper = 'A'
        initial_year = self.initial_year
        account = self.AccountType(
            self.owner, *args,
            balance=balance, rate=rate, nper=nper,
            **kwargs)
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        self.assertEqual(account.balance_history, {initial_year: Money(0)})
        self.assertEqual(account.rate_history, {initial_year: 1})
        self.assertEqual(
            account.transactions_history,
            {initial_year: {}})
        self.assertEqual(account.balance, Money(0))
        self.assertEqual(account.rate, 1)
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, initial_year)
        # Check types for conversion
        self.assertIsInstance(account.balance_history[initial_year], Money)
        self.assertIsInstance(account.rate_history[initial_year], Decimal)
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.initial_year, int)

    def test_init_invalid(self, *args, **kwargs):
        """ Test Account.__init__ with invalid inputs. """
        # Let's test invalid Decimal conversions next.
        # (BasicContext causes most Decimal-conversion errors to raise
        # exceptions. Invalid input will raise InvalidOperation)
        decimal.setcontext(decimal.BasicContext)
        balance = 0

        # Test with values not convertible to Decimal
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                balance="invalid input", **kwargs)
            # In some contexts, Decimal returns NaN instead of raising an error
            if account.balance == Money("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                balance=balance, rate="invalid input", **kwargs)
            if account.rate == Decimal("NaN"):
                raise decimal.InvalidOperation()

        # Finally, test passing an invalid owner:
        with self.assertRaises(TypeError):
            account = self.AccountType(
                "invalid owner", *args, **kwargs)

    def test_add_transaction_in_range(self):
        """ Test 'when' values inside of the range [0,1]. """
        self.account.add_transaction(1, when=0)
        self.assertEqual(self.account.transactions[Decimal(0)], Money(1))

        self.account.add_transaction(1, when=0.5)
        self.assertEqual(self.account.transactions[Decimal(0.5)], Money(1))

        self.account.add_transaction(1, when=1)
        self.assertEqual(self.account.transactions[Decimal(1)], Money(1))

    def test_add_transaction_out_range(self):
        """ Test 'when' values outside of the range [0,1]. """
        # All of these should raise exceptions.
        with self.assertRaises(ValueError):  # test negative
            self.account.add_transaction(1, when=-1)
        with self.assertRaises(ValueError):  # test positive
            self.account.add_transaction(1, when=2)

    def test_returns(self, *args, **kwargs):
        """ Tests Account.returns and Account.returns_history. """
        # Account with $1 balance and 100% non-compounded growth.
        # Should have returns of $1 in its first year:
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0, nper=1,
            **kwargs)
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        self.assertEqual(account.returns, Money(1))  # $1 return
        self.assertEqual(account.returns_history,
                         {self.initial_year: Money(1)})

    def test_returns_next_year(self, *args, **kwargs):
        # Account with $1 balance and 100% non-compounded growth.
        # Should have returns of $2 in its second year:
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0, nper=1,
            **kwargs)
        account.next_year()
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        self.assertEqual(account.returns_history,
                         {self.initial_year: Money(1),
                          self.initial_year + 1: Money(2)})
        self.assertEqual(account.returns, Money(2))

    def test_next_year(self, *args, **kwargs):
        """ Tests next_year with basic scenario. """
        # Simple account: Start with $1, apply 100% growth once per
        # year, no transactions. Should yield a new balance of $2.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0, nper=1, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Money(2))

    def test_next_year_no_growth(self, *args, **kwargs):
        """ Tests next_year with no growth. """
        # Start with $1 and apply 0% growth.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=0, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Money(1))

    def test_next_year_continuous_growth(self, *args, **kwargs):
        """ Tests next_year with continuous growth. """
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='C', **kwargs)
        account.next_year()
        self.assertAlmostEqual(account.balance, Money(math.e), 3)

    def test_next_year_discrete_growth(self, *args, **kwargs):
        """ Tests next_year with discrete (monthly) growth. """
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='M', **kwargs)
        account.next_year()
        self.assertAlmostEqual(account.balance, Money((1 + 1 / 12) ** 12), 3)

    def test_next_year_basic_transaction(self, *args, **kwargs):
        """ Tests next_year with a mid-year transaction. """
        # Start with $1 (which grows to $2), contribute $2 mid-year.
        # NOTE: The growth of the $2 transaction is not well-defined,
        # since it occurs mid-compounding-period. However, the output
        # should be sensible. In  particular, it should grow by $0-$1.
        # So check to confirm that the result is in the range [$4, $5]
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0, nper=1, **kwargs)
        account.add_transaction(Money(2), when='0.5')
        account.next_year()
        self.assertGreaterEqual(account.balance, Money(4))
        self.assertLessEqual(account.balance, Money(5))

    def test_next_year_no_growth_transaction(self, *args, **kwargs):
        """ Tests next_year with no growth and a mid-year transaction. """
        # Start with $1, add $2, and apply 0% growth.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=0, nper=1, **kwargs)
        account.add_transaction(Money(2), when='0.5')
        account.next_year()
        self.assertEqual(account.balance, Money(3))

    def test_next_year_continuous_growth_transaction(self, *args, **kwargs):
        """ Tests next_year with continuous growth and a mid-year transaction. """
        # This can be calculated from P = P_0 * e^rt
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='C', **kwargs)
        account.add_transaction(Money(2), when='0.5')
        next_val = Money(1 * math.e + 2 * math.e ** 0.5)
        account.next_year()
        self.assertAlmostEqual(account.balance, next_val, 5)

    def test_next_year_discrete_growth_transaction(self, *args, **kwargs):
        """ Tests next_year with discrete growth and a mid-year transaction. """
        # The $2 transaction happens at the start of a compounding
        # period, so behaviour is well-defined. It should grow by a
        # factor of (1 + r/n)^nt, for n = 12 (monthly) and t = 0.5
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='M', **kwargs)
        account.add_transaction(Money(2), when='0.5')
        next_val = Money((1 + 1 / 12) ** (12) + 2 * (1 + 1 / 12) ** (12 * 0.5))
        account.next_year()
        self.assertAlmostEqual(account.balance, next_val, 5)

    def test_add_transaction(self, *args, **kwargs):
        """ Tests add_transaction. """
        # Start with an empty account and add a transaction.
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.transactions_history, {
            self.initial_year: {}})
        account.add_transaction(Money(1), when='end')
        self.assertEqual(account.transactions_history, {
            self.initial_year: {
                1: Money(1)
            }})
        self.assertEqual(account.transactions, {1: Money(1)})
        self.assertEqual(account.inflows, Money(1))

    def test_add_transaction_multiple_different_time(self, *args, **kwargs):
        """ Tests add_transaction with multiple transactions at different times. """
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(2), 1)
        self.assertEqual(account.transactions,
            {0: Money(1), 1: Money(2)})
        self.assertEqual(account.inflows, Money(3))
        self.assertEqual(account.outflows, Money(0))

    def test_add_transaction_multiple_same_time(self, *args, **kwargs):
        """ Tests add_transaction with multiple transactions at the same time. """
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(1), 0)
        self.assertEqual(account.transactions,
            {0: Money(2)})
        self.assertEqual(account.inflows, Money(2))
        self.assertEqual(account.outflows, Money(0))

    def test_add_transaction_different_inflows_outflows(self, *args, **kwargs):
        """ Tests add_transaction with both inflows and outflows at different times. """
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'end')
        self.assertEqual(account.transactions,
            {0: Money(1), 1: Money(-2)})
        self.assertEqual(account.inflows, Money(1))
        self.assertEqual(account.outflows, Money(-2))

    def test_add_transaction_same_inflows_outflows(self, *args, **kwargs):
        """ Tests add_transaction with simultaneous inflows and outflows. """
        # NOTE: Consider whether this behaviour (i.e. simultaneous flows
        # being combined into one net flow) should be revised.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'start')
        self.assertEqual(account.transactions,
            {0: Money(-1)})
        self.assertEqual(account.inflows, 0)
        self.assertEqual(account.outflows, Money(-1))

        # TODO: Test add_transactions again after performing next_year
        # (do this recursively?)

    def test_max_outflow(self, *args, **kwargs):
        """ Test Account.max_outflow """
        # Simple scenario: $100 in a no-growth account with no
        # transactions. Should return $100 for any point in time.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=0, nper=1, **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        self.assertEqual(account.max_outflow(0.5), Money(-100))
        self.assertEqual(account.max_outflow('end'), Money(-100))

        # Try with negative balance - should return $0
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1, nper=1, **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(0))
        self.assertEqual(account.max_outflow('end'), Money(0))

        # $100 in account that grows to $200 in one compounding period.
        # No transactions.
        # NOTE: Account balances mid-compounding-period are not
        # well-defined in the current implementation, so avoid
        # testing at when=0.5
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper=1, **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        # self.assertEqual(account.max_outflow(0.5), Money(-150))
        self.assertEqual(account.max_outflow('end'), Money(-200))

        # $100 in account that grows linearly by 100%. Add $100
        # transactions at the start and end of the year.
        # NOTE: Behaviour of transactions between compounding
        # points is not well-defined, so avoid adding transactions at
        # 0.5 (or anywhere other than 'start' or 'end') when nper = 1
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper=1, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(100, when='end')
        self.assertEqual(account.max_outflow('start'), Money(-200))
        # self.assertEqual(account.max_outflow(0.25), Money(-250))
        # self.assertEqual(account.max_outflow(0.5), Money(-300))
        # self.assertEqual(account.max_outflow(0.75), Money(-350))
        self.assertEqual(account.max_outflow('end'), Money(-500))

        # Try with a negative starting balance and a positive ending
        # balance. With -$100 start and 200% interest compounding at
        # t=0.5, balance should be -$200 at t=0.5. Add $200 transaction
        # at t=0.5 so balance = 0 and another transaction at t='end' so
        # balance = $100.
        account = self.AccountType(
            self.owner, *args, balance=-200, rate=2.0, nper=2, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(200, when='0.5')
        account.add_transaction(100, when='end')
        self.assertEqual(account.max_outflow('start'), Money(0))
        self.assertEqual(account.balance_at_time('start'), Money(-100))
        self.assertEqual(account.max_outflow(0.5), Money(0))
        self.assertEqual(account.max_outflow('end'), Money(-100))

        # Test compounding. First: discrete compounding, once at the
        # halfway point. Add a $100 transaction at when=0.5 just to be
        # sure.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper=2, **kwargs)
        account.add_transaction(100, when=0.5)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        # self.assertEqual(account.max_outflow(0.25), Money(-125))
        self.assertEqual(account.max_outflow(0.5), Money(-250))
        # self.assertEqual(account.max_outflow(0.75), Money(-312.50))
        self.assertEqual(account.max_outflow('end'), Money(-375))

        # Now to test continuous compounding. Add a $100 transaction at
        # when=0.5 just to be sure.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper='C', **kwargs)
        account.add_transaction(100, when='0.5')
        self.assertEqual(account.max_outflow('start'), Money(-100))
        self.assertAlmostEqual(account.max_outflow(0.25),
                               -Money(100 * math.e ** 0.25), 5)
        self.assertAlmostEqual(account.max_outflow(0.5),
                               -Money(100 * math.e ** 0.5 + 100), 5)
        self.assertAlmostEqual(account.max_outflow(0.75),
                               -Money(100 * math.e ** 0.75 +
                                      100 * math.e ** 0.25), 5)
        self.assertAlmostEqual(account.max_outflow('end'),
                               -Money(100 * math.e +
                                      100 * math.e ** 0.5), 5)

    def test_max_inflow(self, *args, **kwargs):
        """ Test Account.max_inflow """
        # This method should always return Money('Infinity')
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        self.assertEqual(account.max_inflow(), Money('Infinity'))

        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        self.assertEqual(account.max_inflow(), Money('Infinity'))

    def test_min_outflow(self, *args, **kwargs):
        """ Test Account.min_outflow """
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        self.assertEqual(account.min_outflow(), Money(0))

        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        self.assertEqual(account.min_outflow(), Money(0))

    def test_min_inflow(self, *args, **kwargs):
        """ Test Account.min_inflow """
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(0))

        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(0))

    def test_taxable_income(self, *args, **kwargs):
        """ Test Account.taxable_income """
        # This method should return the growth in the account, which is
        # $200 at the start of the period. (The $100 withdrawal at the
        # end of the period doesn't affect taxable income.)
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.taxable_income, Money(200))

        # Losses are not taxable:
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.taxable_income, Money(0))

    def test_tax_withheld(self, *args, **kwargs):
        """ Test Account.tax_withheld """
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_withheld, Money(0))

        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_withheld, Money(0))

    def test_tax_credit(self, *args, **kwargs):
        """ Test Account.tax_credit """
        # This method should always return $0, regardless of balance,
        # inflows, or outflows
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_credit, Money(0))

        # Test with negative balance
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_credit, Money(0))

    def test_tax_deduction(self, *args, **kwargs):
        """ Test Account.tax_deduction """
        # This method should always return $0, regardless of balance,
        # inflows, or outflows
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_deduction, Money(0))

        # Test with negative balance
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_deduction, Money(0))

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

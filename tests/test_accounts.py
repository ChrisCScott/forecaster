""" Module for testing forecaster.accounts classes. """

import unittest
import math
import decimal
from decimal import Decimal
from forecaster import (
    Person, Account, Debt, ContributionLimitAccount, AllocationStrategy,
    Scenario, Money)
from forecaster.accounts import when_conv
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

    def test_nper_continuous(self):
        """ Test setting nper to 'C' and 'None' (equivalent). """
        # TODO: Refactor Account so that nper is a property, set up
        # this test to set self.account.nper = 'C' (same for others)
        account = self.AccountType(
            self.owner, *args, nper='C', **kwargs)
        self.assertEqual(account.nper, 'C')
        self.assertIsInstance(account.nper, (type(None), str))
        
        account = self.AccountType(
            self.owner, *args, nper=None, **kwargs)
        self.assertEqual(account.nper, 'C')
        self.assertIsInstance(account.nper, (type(None), str))

    def test_nper_daily(self, *args, **kwargs):
        """ Test setting nper to 'D'. """
        account = self.AccountType(
            self.owner, *args, nper='D', **kwargs)
        self.assertEqual(account.nper, 365)
        self.assertIsInstance(account.nper, int)

    def test_nper_weekly(self, *args, **kwargs):
        """ Test setting nper to 'W'. """
        account = self.AccountType(
            self.owner, *args, nper='W', **kwargs)
        self.assertEqual(account.nper, 52)

    def test_nper_biweekly(self, *args, **kwargs):
        """ Test setting nper to 'BW'. """
        account = self.AccountType(
            self.owner, *args, nper='BW', **kwargs)
        self.assertEqual(account.nper, 26)

    def test_nper_semimonthly(self, *args, **kwargs):
        """ Test setting nper to 'SM'. """
        account = self.AccountType(
            self.owner, *args, nper='SM', **kwargs)
        self.assertEqual(account.nper, 24)

    def test_nper_monthly(self, *args, **kwargs):
        """ Test setting nper to 'M'. """
        account = self.AccountType(
            self.owner, *args, nper='M', **kwargs)
        self.assertEqual(account.nper, 12)

    def test_nper_bimonthly(self, *args, **kwargs):
        """ Test setting nper to 'BM'. """
        account = self.AccountType(
            self.owner, *args, nper='BM', **kwargs)
        self.assertEqual(account.nper, 6)

    def test_nper_quarterly(self, *args, **kwargs):
        """ Test setting nper to 'Q'. """
        account = self.AccountType(
            self.owner, *args, nper='Q', **kwargs)
        self.assertEqual(account.nper, 4)

    def test_nper_semiannually(self, *args, **kwargs):
        """ Test setting nper to 'SA'. """
        account = self.AccountType(
            self.owner, *args, nper='SA', **kwargs)
        self.assertEqual(account.nper, 2)

    def test_nper_annually(self, *args, **kwargs):
        """ Test setting nper to 'A'. """
        account = self.AccountType(
            self.owner, *args, nper='A', **kwargs)
        self.assertEqual(account.nper, 1)

    def test_nper_invalid(self, *args, **kwargs):
        """ Test setting nper to invalid values. """
        # These should all raise errors.
        with self.assertRaises(ValueError):
            _ = self.AccountType(
                self.owner, *args, nper=0, **kwargs)

        with self.assertRaises(ValueError):
            _ = self.AccountType(
                self.owner, *args, nper=-1, **kwargs)

        with self.assertRaises(TypeError):
            _ = self.AccountType(
                self.owner, *args, nper=0.5, **kwargs)

        with self.assertRaises(TypeError):
            _ = self.AccountType(
                self.owner, *args, nper=1.5, **kwargs)

        with self.assertRaises(ValueError):
            _ = self.AccountType(
                self.owner, *args, nper='invalid', **kwargs)

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

        account.next_year()
        self.assertEqual(account.returns_history,
                         {self.initial_year: Money(1),
                          self.initial_year + 1: Money(2)})
        self.assertEqual(account.returns, Money(2))

    def test_next_year(self, *args, **kwargs):
        """ Tests next_year. """
        # Simple account: Start with $1, apply 100% growth once per
        # year, no transactions. Should yield a new balance of $2.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0, nper=1, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Money(2))

        # No growth: Start with $1 and apply 0% growth.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=0, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Money(1))

        # Try with continuous growth
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='C', **kwargs)
        account.next_year()
        self.assertAlmostEqual(account.balance, Money(math.e), 3)

        # Try with discrete (monthly) growth
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='M', **kwargs)
        account.next_year()
        self.assertAlmostEqual(account.balance, Money((1 + 1 / 12) ** 12), 3)

        # Repeat above with a $2 contribution halfway through the year

        # Start with $1 (which grows to $2) and contribute $2.
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

        # No growth: Start with $1, add $2, and apply 0% growth.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=0, nper=1, **kwargs)
        account.add_transaction(Money(2), when='0.5')
        account.next_year()
        self.assertEqual(account.balance, Money(3))

        # Try with continuous growth
        # This can be calculated from P = P_0 * e^rt
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='C', **kwargs)
        account.add_transaction(Money(2), when='0.5')
        next_val = Money(1 * math.e + 2 * math.e ** 0.5)
        account.next_year()
        self.assertAlmostEqual(account.balance, next_val, 5)

        # Try with discrete growth
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
        # We need to make sure that initial_year is in the same range
        # as inflation_adjustments, otherwise init will fail:
        initial_year = self.initial_year

        # Start with an empty account and add a transaction.
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.transactions_history, {
            initial_year: {}})
        account.add_transaction(Money(1), 'end')
        self.assertEqual(account.transactions_history, {
            initial_year: {
                1: Money(1)
            }})
        self.assertEqual(account.transactions, {1: Money(1)})
        self.assertEqual(account.inflows, Money(1))

        # Try adding multiple transactions at different times.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(2), 1)
        self.assertEqual(account.transactions_history, {
            initial_year: {0: Money(1), 1: Money(2)}})
        self.assertEqual(account.inflows, Money(3))
        self.assertEqual(account.outflows, 0)

        # Try adding multiple transactions at the same time.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(1), 0)
        self.assertEqual(account.transactions_history, {
            initial_year: {0: Money(2)}})
        self.assertEqual(account.inflows, Money(2))
        self.assertEqual(account.outflows, Money(0))

        # Try adding both inflows and outflows at different times.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'end')
        self.assertEqual(account.transactions_history, {
            initial_year: {0: Money(1), 1: Money(-2)}})
        self.assertEqual(account.inflows, Money(1))
        self.assertEqual(account.outflows, Money(-2))

        # Try adding simultaneous inflows and outflows
        # NOTE: Consider whether this behaviour (i.e. simultaneous flows
        # being combined into one net flow) should be revised.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'start')
        self.assertEqual(account.transactions_history, {
            initial_year: {0: Money(-1)}})
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


class TestContributionLimitAccountMethods(TestAccountMethods):
    """ Tests ContributionLimitAccount. """

    def setUp(self):
        """ Sets up variables for testing ContributionLimitAccount """
        super().setUp()

        self.AccountType = ContributionLimitAccount
        self.contribution_room = 0

    def test_init_basic(self, *args, **kwargs):
        """ Test ContributionLimitAccount.__init__ """
        super().test_init_basic(
            *args, contribution_room=self.contribution_room, **kwargs)

        # Basic init using pre-built ContributionLimitAccount-specific args
        # and default Account args
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.contribution_room, self.contribution_room)

    def test_init_contributor_implicit(self, *args, **kwargs):
        """ Test implicit initialization of contributor parameter. """
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.contributor, self.owner)

    def test_init_contributor_explicit(self, *args, **kwargs):
        """ Test explicit initialization of contributor parameter. """
        contributor = Person(
            self.initial_year, "Name", "1 January 2000",
            retirement_date="1 January 2020")
        account = self.AccountType(
            self.owner, *args, contributor=contributor, **kwargs)
        self.assertEqual(account.contributor, contributor)

    def test_contribution_room(self, *args, **kwargs):
        """ Test explicit initialization of contribution_room. """
        account = self.AccountType(
            self.owner, *args, contribution_room=Money(100), **kwargs)
        self.assertEqual(account.contribution_room, Money(100))

    def test_init_invalid(self, *args, **kwargs):
        """ Test ContributionLimitAccount.__init__ with invalid inputs. """
        super().test_init_invalid(
            *args, contribution_room=self.contribution_room, **kwargs)

        # Test invalid `person` input
        with self.assertRaises(TypeError):
            self.AccountType(
                self.owner, contributor='invalid person',
                *args, **kwargs)

        # Finally, test a non-Money-convertible contribution_room:
        with self.assertRaises(decimal.InvalidOperation):
            self.AccountType(
                self.owner, *args,
                contribution_room='invalid', **kwargs)

    def test_properties(self, *args, **kwargs):
        """ Test ContributionLimitAccount properties """
        # Basic check: properties return scalars (current year's values)
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contribution_room,
                         self.contribution_room)

        # NOTE: ContributionLimitAccount.next_year() raises NotImplementedError
        # and some subclasses require args for next_year(). That is
        # already dealt with by test_next, so check that properties are
        # pointing to the current year's values after calling next_year
        # in text_next.

    def test_next_year(self, *args, **kwargs):
        """ Test ContributionLimitAccount.next_year. """
        # next_contribution_room is not implemented for
        # ContributionLimitAccount, and it's required for next_year, so confirm
        # that trying to call next_year() throws an appropriate error.
        if self.AccountType == ContributionLimitAccount:
            account = ContributionLimitAccount(self.owner)
            with self.assertRaises(NotImplementedError):
                account.next_year()
        # For other account types, try a conventional next_year test
        else:
            super().test_next_year(
                *args, **kwargs)

    def test_returns(self, *args, **kwargs):
        """ Test ContributionLimitAccount.returns. """
        # super().test_returns calls next_year(), which calls
        # next_contribution_room(), which is not implemented for
        # ContributionLimitAccount. Don't test returns for this class,
        # and instead allow subclasses to pass through.
        if self.AccountType != ContributionLimitAccount:
            super().test_returns(*args, **kwargs)

    def test_max_inflow(self, *args, **kwargs):
        """ Test ContributionLimitAccount.max_inflow. """
        # Init an account with standard parameters, confirm that
        # max_inflow corresponds to contribution_room.
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.max_inflow(), self.contribution_room)

    def test_contribution_room_basic(self, *args, **kwargs):
        """ Test sharing of contribution room between accounts. """
        account1 = self.AccountType(
            self.owner, *args,
            contribution_room=Money(100), **kwargs)
        self.assertEqual(account1.contribution_room, Money(100))

        # Don't set contribution_room explicitly for account2; it should
        # automatically match account1's contribution_room amount.
        account2 = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account2.contribution_room, Money(100))

    def test_contribution_room_update(self, *args, **kwargs):
        """ Test updating contribution room via second account's init. """
        account1 = self.AccountType(
            self.owner, *args,
            contribution_room=Money(100), **kwargs)
        self.assertEqual(account1.contribution_room, Money(100))

        # Set contribution_room explicitly for account2; it should
        # override account1's contribution_room amount.
        account2 = self.AccountType(
            self.owner, *args,
            contribution_room=Money(200), **kwargs)
        self.assertEqual(account1.contribution_room, Money(200))
        self.assertEqual(account2.contribution_room, Money(200))

    def test_contribution_group_basic(self, *args, **kwargs):
        """ Test that contribution_group is set properly for 1 account. """
        account = self.AccountType(
            self.owner, *args,
            contribution_room=Money(100), **kwargs)
        self.assertEqual(account.contribution_group, {account})

    def test_contribution_group_mult(self, *args, **kwargs):
        """ Test that contribution_group is set properly for 2 accounts. """
        account1 = self.AccountType(
            self.owner, *args,
            contribution_room=Money(100), **kwargs)
        account2 = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account1.contribution_group, {account1, account2})
        self.assertEqual(account2.contribution_group, {account1, account2})


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


class TestFreeMethods(unittest.TestCase):
    """ Tests free methods in forecaster.person module. """

    def test_when_conv(self):
        """ Tests `when_conv` """

        # Test a simple, single-valued input
        when = when_conv(1)
        self.assertEqual(when, Decimal(1))

        # Test a magic input
        when = when_conv('start')
        self.assertEqual(when, Decimal(0))

        # Test a magic input
        when = when_conv('end')
        self.assertEqual(when, Decimal(1))

        # Test non-magic str input
        when = when_conv('1')
        self.assertEqual(when, Decimal(1))

        with self.assertRaises(decimal.InvalidOperation):
            when = when_conv('invalid input')


if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

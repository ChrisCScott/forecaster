""" Tests forecaster.accounts.base. """

import unittest
import math
import decimal
from decimal import Decimal
from forecaster import Person, Account, Scenario, AllocationStrategy
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

        # We'll also need a timing value for various tests.
        # Use two inflows, at the start and end, evenly weighted:
        self.timing = {Decimal(0): 1, Decimal(1): 1}

        # Inheriting classes should assign to self.account with an
        # instance of an appropriate subclass of Account.
        self.account = Account(self.owner, balance=100, rate=1.0)

    def test_init_basic(self, *args, **kwargs):
        """ Tests Account.__init__ """
        # Basic test: All correct values, check for equality and type
        owner = self.owner
        balance = Decimal(0)
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
        self.assertTrue(type_check(account.balance_history, {int: Decimal}))
        self.assertIsInstance(account.balance, Decimal)
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
        balance = Decimal(0)
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
        self.assertEqual(account.balance_history, {initial_year: Decimal(0)})
        self.assertEqual(account.rate_history, {initial_year: 1})
        self.assertEqual(
            account.transactions_history,
            {initial_year: {}})
        self.assertEqual(account.balance, Decimal(0))
        self.assertEqual(account.rate, 1)
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, initial_year)
        # Check types for conversion
        self.assertIsInstance(account.balance_history[initial_year], Decimal)
        self.assertIsInstance(account.rate_history[initial_year], Decimal)
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.initial_year, int)

    def test_init_invalid_balance(self, *args, **kwargs):
        """ Test Account.__init__ with invalid balance input. """
        # Let's test invalid Decimal conversions next.
        # (BasicContext causes most Decimal-conversion errors to raise
        # exceptions. Invalid input will raise InvalidOperation)
        decimal.setcontext(decimal.BasicContext)

        # Test with values not convertible to Decimal
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                balance="invalid input", **kwargs)
            # In some contexts, Decimal returns NaN instead of raising an error
            if account.balance == Decimal("NaN"):
                raise decimal.InvalidOperation()

    def test_init_invalid_rate(self, *args, **kwargs):
        """ Test Account.__init__ with invalid rate input. """
        decimal.setcontext(decimal.BasicContext)
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                balance=0, rate="invalid input", **kwargs)
            # `rate` is not callable if we use non-callable input
            # pylint: disable=comparison-with-callable
            if account.rate == Decimal("NaN"):
                raise decimal.InvalidOperation()
            # pylint: enable=comparison-with-callable

    def test_init_invalid_owner(self, *args, **kwargs):
        """ Test Account.__init__ with invalid rate input. """
        # Finally, test passing an invalid owner:
        with self.assertRaises(TypeError):
            _ = self.AccountType(
                "invalid owner", *args, **kwargs)

    def test_add_trans_in_range(self):
        """ Test 'when' values inside of the range [0,1]. """
        self.account.add_transaction(1, when=0)
        self.assertEqual(self.account.transactions[Decimal(0)], Decimal(1))

        self.account.add_transaction(1, when=0.5)
        self.assertEqual(self.account.transactions[Decimal(0.5)], Decimal(1))

        self.account.add_transaction(1, when=1)
        self.assertEqual(self.account.transactions[Decimal(1)], Decimal(1))

    def test_add_trans_out_range(self):
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
        self.assertEqual(account.returns, Decimal(1))  # $1 return
        self.assertEqual(account.returns_history,
                         {self.initial_year: Decimal(1)})

    def test_returns_next_year(self, *args, **kwargs):
        """ Tests Account.returns after calling next_year. """
        # Account with $1 balance and 100% non-compounded growth.
        # Should have returns of $2 in its second year:
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0, nper=1,
            **kwargs)
        account.next_year()
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        self.assertEqual(account.returns_history,
                         {self.initial_year: Decimal(1),
                          self.initial_year + 1: Decimal(2)})
        self.assertEqual(account.returns, Decimal(2))

    def test_next(self, *args, **kwargs):
        """ Tests next_year with basic scenario. """
        # Simple account: Start with $1, apply 100% growth once per
        # year, no transactions. Should yield a new balance of $2.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0, nper=1, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Decimal(2))

    def test_next_no_growth(self, *args, **kwargs):
        """ Tests next_year with no growth. """
        # Start with $1 and apply 0% growth.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=0, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Decimal(1))

    def test_next_cont_growth(self, *args, **kwargs):
        """ Tests next_year with continuous growth. """
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='C', **kwargs)
        account.next_year()
        self.assertAlmostEqual(account.balance, Decimal(math.e), 3)

    def test_next_disc_growth(self, *args, **kwargs):
        """ Tests next_year with discrete (monthly) growth. """
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='M', **kwargs)
        account.next_year()
        self.assertAlmostEqual(account.balance, Decimal((1 + 1 / 12) ** 12), 3)

    def test_next_basic_trans(self, *args, **kwargs):
        """ Tests next_year with a mid-year transaction. """
        # Start with $1 (which grows to $2), contribute $2 mid-year.
        # NOTE: The growth of the $2 transaction is not well-defined,
        # since it occurs mid-compounding-period. However, the output
        # should be sensible. In  particular, it should grow by $0-$1.
        # So check to confirm that the result is in the range [$4, $5]
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0, nper=1, **kwargs)
        account.add_transaction(Decimal(2), when='0.5')
        account.next_year()
        self.assertGreaterEqual(account.balance, Decimal(4))
        self.assertLessEqual(account.balance, Decimal(5))

    def test_next_no_growth_trans(self, *args, **kwargs):
        """ Tests next_year with no growth and a transaction. """
        # Start with $1, add $2, and apply 0% growth.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=0, nper=1, **kwargs)
        account.add_transaction(Decimal(2), when='0.5')
        account.next_year()
        self.assertEqual(account.balance, Decimal(3))

    def test_next_cont_growth_trans(self, *args, **kwargs):
        """ Tests next_year with continuous growth and a transaction. """
        # This can be calculated from P = P_0 * e^rt
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='C', **kwargs)
        account.add_transaction(Decimal(2), when='0.5')
        next_val = Decimal(1 * math.e + 2 * math.e ** 0.5)
        account.next_year()
        self.assertAlmostEqual(account.balance, next_val, 5)

    def test_next_disc_growth_trans(self, *args, **kwargs):
        """ Tests next_year with discrete growth and a transaction. """
        # The $2 transaction happens at the start of a compounding
        # period, so behaviour is well-defined. It should grow by a
        # factor of (1 + r/n)^nt, for n = 12 (monthly) and t = 0.5
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1, nper='M', **kwargs)
        account.add_transaction(Decimal(2), when='0.5')
        next_val = Decimal((1 + 1 / 12) ** (12) + 2 * (1 + 1 / 12) ** (12 * 0.5))
        account.next_year()
        self.assertAlmostEqual(account.balance, next_val, 5)

    def test_add_trans(self, *args, **kwargs):
        """ Tests add_transaction. """
        # Start with an empty account and add a transaction.
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.transactions_history, {
            self.initial_year: {}})
        account.add_transaction(Decimal(1), when='end')
        self.assertEqual(account.transactions_history, {
            self.initial_year: {
                1: Decimal(1)
            }})
        self.assertEqual(account.transactions, {1: Decimal(1)})
        self.assertEqual(account.inflows(), Decimal(1))

    def test_add_trans_mult_diff_time(self, *args, **kwargs):
        """ Tests add_transaction with transactions at different times. """
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Decimal(1), 'start')
        account.add_transaction(Decimal(2), 1)
        self.assertEqual(
            account.transactions,
            {0: Decimal(1), 1: Decimal(2)})
        self.assertEqual(account.inflows(), Decimal(3))
        self.assertEqual(account.outflows(), Decimal(0))

    def test_add_trans_mult_same_time(self, *args, **kwargs):
        """ Tests add_transaction with transactions at the same time. """
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Decimal(1), 'start')
        account.add_transaction(Decimal(1), 0)
        self.assertEqual(
            account.transactions,
            {0: Decimal(2)})
        self.assertEqual(account.inflows(), Decimal(2))
        self.assertEqual(account.outflows(), Decimal(0))

    def test_add_trans_diff_in_out(self, *args, **kwargs):
        """ Tests add_transaction with in- and outflows at different times. """
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Decimal(1), 'start')
        account.add_transaction(Decimal(-2), 'end')
        self.assertEqual(
            account.transactions,
            {0: Decimal(1), 1: Decimal(-2)})
        self.assertEqual(account.inflows(), Decimal(1))
        self.assertEqual(account.outflows(), Decimal(-2))

    def test_add_trans_same_in_out(self, *args, **kwargs):
        """ Tests add_transaction with simultaneous inflows and outflows. """
        # NOTE: Consider whether this behaviour (i.e. simultaneous flows
        # being combined into one net flow) should be revised.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Decimal(1), 'start')
        account.add_transaction(Decimal(-2), 'start')
        self.assertEqual(
            account.transactions,
            {0: Decimal(-1)})
        self.assertEqual(account.inflows(), 0)
        self.assertEqual(account.outflows(), Decimal(-1))

        # TODO: Test add_transactions again after performing next_year
        # (do this recursively?)

    def test_max_outflows_constant(self, *args, **kwargs):
        """ Test max_outflows with constant-balance account """
        # Simple scenario: $100 in a no-growth account with no
        # transactions. Should return $100 for any point in time.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=0, nper=1, **kwargs)
        result = account.max_outflows(self.timing)
        for when, value in result.items():
            account.add_transaction(value, when=when)
        # Result of `max_outflows` should bring balance to $0 if
        # applied as transactions:
        self.assertAlmostEqual(account.balance_at_time('end'), Decimal(0))

    def test_max_outflows_negative(self, *args, **kwargs):
        """ Test max_outflows with negative-balance account. """
        # Try with negative balance - should return $0
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1, nper=1, **kwargs)
        result = account.max_outflows(self.timing)
        for value in result.values():
            self.assertAlmostEqual(value, Decimal(0), places=4)

    def test_max_outflows_simple(self, *args, **kwargs):
        """ Test max_outflows with simple growth, no transactions """
        # $100 in account that grows to $200 in one compounding period.
        # No transactions.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper=1, **kwargs)
        result = account.max_outflows(self.timing)
        for when, value in result.items():
            account.add_transaction(value, when=when)
        # Result of `max_outflows` should bring balance to $0 if
        # applied as transactions:
        self.assertAlmostEqual(
            account.balance_at_time('end'), Decimal(0), places=4)

    def test_max_outflows_simple_trans(self, *args, **kwargs):
        """ Test max_outflows with simple growth and transactions """
        # $100 in account that grows linearly by 100%. Add $100
        # transactions at the start and end of the year.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper=1, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(100, when='end')
        result = account.max_outflows(self.timing)
        for when, value in result.items():
            account.add_transaction(value, when=when)
        # Result of `max_outflows` should bring balance to $0 if
        # applied as transactions:
        self.assertAlmostEqual(
            account.balance_at_time('end'), Decimal(0), places=4)

    def test_max_outflows_neg_to_pos(self, *args, **kwargs):
        """ Test max_outflows going from neg. to pos. balance """
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
        result = account.max_outflows(self.timing)
        for when, value in result.items():
            account.add_transaction(value, when=when)
        # Result of `max_outflows` should bring balance to $0 if
        # applied as transactions:
        self.assertAlmostEqual(
            account.balance_at_time('end'), Decimal(0), places=4)

    def test_max_outflows_compound_disc(self, *args, **kwargs):
        """ Test max_outflows with discrete compounding """
        # Test compounding. First: discrete compounding, once at the
        # halfway point. Add a $100 transaction at when=0.5 just to be
        # sure.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper=2, **kwargs)
        account.add_transaction(100, when=0.5)
        # Three evenly-weighted transactions for some extra complexity:
        timing = {Decimal(0): 1, Decimal(0.5): 1, Decimal(1): 1}
        result = account.max_outflows(timing)
        for when, value in result.items():
            account.add_transaction(value, when=when)
        # Result of `max_outflows` should bring balance to $0 if
        # applied as transactions:
        self.assertAlmostEqual(
            account.balance_at_time('end'), Decimal(0), places=4)

    def test_max_outflows_compound_cont(self, *args, **kwargs):
        """ Test max_outflows with continuous compounding. """
        # Now to test continuous compounding. Add a $100 transaction at
        # when=0.5 just to be sure.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper='C', **kwargs)
        account.add_transaction(100, when='0.5')
        # Three evenly-weighted transactions, for extra complexity:
        timing = {Decimal(0): 1, Decimal(0.5): 1, Decimal(1): 1}
        result = account.max_outflows(timing)
        for when, value in result.items():
            account.add_transaction(value, when=when)
        # Result of `max_outflows` should bring balance to $0 if
        # applied as transactions:
        self.assertAlmostEqual(
            account.balance_at_time('end'), Decimal(0), places=4)

    def test_max_inflows_pos(self, *args, **kwargs):
        """ Test max_inflows with positive balance """
        # This method should always return Decimal('Infinity')
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        result = account.max_inflows(self.timing)
        for value in result.values():
            self.assertEqual(value, Decimal('Infinity'))

    def test_max_inflows_neg(self, *args, **kwargs):
        """ Test max_inflows with negative balance """
        # This method should always return Decimal('Infinity')
        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        result = account.max_inflows(self.timing)
        for value in result.values():
            self.assertEqual(value, Decimal('Infinity'))

    def test_min_outflows_pos(self, *args, **kwargs):
        """ Test Account.min_outflow with positive balance """
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        result = account.min_outflows(self.timing)
        for value in result.values():
            self.assertAlmostEqual(value, Decimal(0), places=4)

    def test_min_outflows_neg(self, *args, **kwargs):
        """ Test min_outflow with negative balance """
        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        result = account.min_outflows(self.timing)
        for value in result.values():
            self.assertAlmostEqual(value, Decimal(0), places=4)

    def test_min_inflows_pos(self, *args, **kwargs):
        """ Test min_inflow with positive balance """
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        result = account.min_inflows(self.timing)
        for value in result.values():
            self.assertAlmostEqual(value, Decimal(0), places=4)

    def test_min_inflows_neg(self, *args, **kwargs):
        """ Test min_inflows with negative balance """
        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        result = account.min_inflows(self.timing)
        for value in result.values():
            self.assertAlmostEqual(value, Decimal(0), places=4)

    def test_max_outflows_example(self, *args, **kwargs):
        """ Test max_outflows with its docstring example. """
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1, nper=1, **kwargs)
        # This is taken straight from the docstring example:
        result = account.max_outflows({0: 1, 1: 1})
        target = {0: Decimal(-200)/3, 1: Decimal(-200)/3}
        self.assertEqual(result.keys(), target.keys())
        for timing in result:
            self.assertAlmostEqual(
                result[timing], target[timing], places=4)

    def test_taxable_income_gain(self, *args, **kwargs):
        """ Test Account.taxable_income with gains in account """
        # This method should return the growth in the account, which is
        # $200 at the start of the period. (The $100 withdrawal at the
        # end of the period doesn't affect taxable income.)
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.taxable_income, Decimal(200))

    def test_taxable_income_loss(self, *args, **kwargs):
        """ Test Account.taxable_income with losses in account """
        # Losses are not taxable:
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.taxable_income, Decimal(0))

    def test_tax_withheld_pos(self, *args, **kwargs):
        """ Test Account.tax_withheld with positive balance. """
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_withheld, Decimal(0))

    def test_tax_withheld_neg(self, *args, **kwargs):
        """ Test Account.tax_withheld with negative balance. """
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_withheld, Decimal(0))

    def test_tax_credit_pos(self, *args, **kwargs):
        """ Test Account.tax_credit with positive balance """
        # This method should always return $0, regardless of balance,
        # inflows, or outflows
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_credit, Decimal(0))

    def test_tax_credit_neg(self, *args, **kwargs):
        """ Test Account.tax_credit with negative balance """
        # Test with negative balance
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_credit, Decimal(0))

    def test_tax_deduction_pos(self, *args, **kwargs):
        """ Test Account.tax_deduction with positive balance """
        # This method should always return $0, regardless of balance,
        # inflows, or outflows
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_deduction, Decimal(0))

    def test_tax_deduction_neg(self, *args, **kwargs):
        """ Test Account.tax_deduction with negative balance """
        # Test with negative balance
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0, **kwargs)
        account.add_transaction(100, when='start')
        account.add_transaction(-100, when='end')
        self.assertEqual(account.tax_deduction, Decimal(0))

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

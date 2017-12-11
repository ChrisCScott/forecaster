""" Module for testing forecaster.accounts classes. """

import unittest
import math
import decimal
from decimal import Decimal
import context  # pylint: disable=unused-import
from forecaster.person import Person
from forecaster.accounts import Account, Debt, RegisteredAccount, when_conv
from forecaster.strategy import AllocationStrategy
from forecaster.scenario import Scenario
from forecaster.ledger import Money
from tests.test_helper import type_check


class TestAccountMethods(unittest.TestCase):
    """ A test suite for the `Account` class.

    For each Account subclass, create a test case that subclasses from
    this (or an intervening subclass). Then, in the setUpClass method,
    assign to class attributes `args`, and/or `kwargs` to
    determine which arguments will be prepended, postpended, or added
    via keyword when an instance of the subclass is initialized.
    Don't forget to also assign the subclass your're testing to
    `cls.AccountType`, and to run `super().setUpClass()` at the top!

    This way, the methods of this class will still be called even for
    subclasses with mandatory positional arguments. You should still
    override the relevant methods to test subclass-specific logic (e.g.
    if the subclass modifies the treatment of the `rate` attribute
    based on an init arg, you'll want to test that by overriding
    `test_rate`)
    """

    @classmethod
    def setUpClass(cls):
        """ Sets up some class-specific variables for calling methods. """
        cls.AccountType = Account

        # It's important to synchronize the initial years of related
        # objects, so store it here:
        cls.initial_year = 2000
        # Every init requires an owner, so store that here:
        cls.scenario = Scenario(
            inflation=0,
            stock_return=1,
            bond_return=0.5,
            other_return=0,
            management_fees=0.03125,
            initial_year=cls.initial_year,
            num_years=100)
        cls.allocation_strategy = AllocationStrategy(
            strategy=AllocationStrategy.strategy_n_minus_age,
            min_equity=Decimal(0.5),
            max_equity=Decimal(0.5),
            target=Decimal(0.5),
            standard_retirement_age=65,
            risk_transition_period=20,
            adjust_for_retirement_plan=False)
        cls.owner = Person(
            cls.initial_year, "test", 2000,
            raise_rate={year: 1 for year in range(2000, 2066)},
            retirement_date=2065)

    def test_init_basic(self, *args, **kwargs):
        """ Tests Account.__init__ """
        # Basic test: All correct values, check for equality and type
        owner = self.owner
        balance = Money(0)
        rate = 1.0
        transactions = {1: Money(1), 0: Money(-1)}
        nper = 1  # This is the easiest case to test
        initial_year = self.initial_year
        account = self.AccountType(
            owner, *args, balance=balance, rate=rate,
            transactions=transactions, nper=nper, **kwargs)
        # Test primary attributes
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        self.assertEqual(account.balance_history, {initial_year: balance})
        self.assertEqual(account.rate_history, {initial_year: rate})
        self.assertEqual(account.transactions_history, {
            initial_year: transactions
        })
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, rate)
        self.assertEqual(account.transactions, transactions)
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
        self.assertTrue(type_check(
            account.transactions_history, {int: {Decimal: Money}}))
        self.assertTrue(type_check(account.transactions, {Decimal: Money}))
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.initial_year, int)

        # Basic test: Only balance and rate provided.
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        account = self.AccountType(
            self.owner, *args, balance=balance, rate=0, **kwargs)
        self.assertEqual(account.balance_history, {
            self.initial_year: balance})
        self.assertEqual(account.rate_history, {self.initial_year: 0})
        self.assertEqual(
            account.transactions_history, {
                self.initial_year: {}})
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, 0)
        self.assertEqual(account.transactions, {})
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, self.initial_year)

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
        transactions = {'start': "1", 'end': "-1"}
        nper = 'A'
        initial_year = self.initial_year
        account = self.AccountType(
            self.owner, *args,
            balance=balance, rate=rate, transactions=transactions, nper=nper,
            **kwargs)
        # pylint: disable=no-member
        # Pylint is confused by members added by metaclass
        self.assertEqual(account.balance_history, {initial_year: Money(0)})
        self.assertEqual(account.rate_history, {initial_year: 1})
        self.assertEqual(account.transactions_history,
                         {initial_year: {0: Money(1), 1: Money(-1)}})
        self.assertEqual(account.balance, Money(0))
        self.assertEqual(account.rate, 1)
        self.assertEqual(account.transactions, {0: Money(1), 1: Money(-1)})
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, initial_year)
        # Check types for conversion
        self.assertIsInstance(account.balance_history[initial_year], Money)
        self.assertIsInstance(account.rate_history[initial_year], Decimal)
        self.assertIsInstance(account.transactions_history[initial_year], dict)
        for key, value in account.transactions.items():
            self.assertIsInstance(key, (float, int, Decimal))
            self.assertIsInstance(value, Money)
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.initial_year, int)

    def test_init_when(self, *args, **kwargs):
        """ Test 'when' values inside and outside of the range [0,1] """
        # pylint: disable=no-member,unsubscriptable-object
        # Pylint is confused by members added by metaclass
        balance = 0

        account = self.AccountType(
            self.owner, *args,
            balance=balance, transactions={0: 1}, **kwargs)
        self.assertEqual(account.transactions[Decimal(0)],
                         Money(1))
        account = self.AccountType(
            self.owner, *args,
            balance=balance, transactions={0.5: 1}, **kwargs)
        self.assertEqual(account.transactions[Decimal(0.5)],
                         Money(1))
        account = self.AccountType(
            self.owner, *args,
            balance=balance, transactions={1: 1}, **kwargs)
        self.assertEqual(account.transactions[Decimal(1)],
                         Money(1))
        with self.assertRaises(ValueError):
            account = self.AccountType(
                self.owner, *args,
                balance=balance, transactions={-1: 1}, **kwargs)
        with self.assertRaises(ValueError):
            account = self.AccountType(
                self.owner, *args,
                balance=balance, transactions={2: 1}, **kwargs)

    def test_init_decimal_conversions(self, *args, **kwargs):
        """ Test account.__init__'s Decimal-conversion behaviour. """
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

        # pylint: disable=unsupported-membership-test
        # Pylint is confused by members added by metaclass
        with self.assertRaises((decimal.InvalidOperation, KeyError)):
            account = self.AccountType(
                self.owner, *args,
                balance=balance, transactions={"invalid input": 1}, **kwargs)
            if Decimal('NaN') in account.transactions:
                raise decimal.InvalidOperation()

        # Finally, test passing an invalid owner:
        with self.assertRaises(TypeError):
            account = self.AccountType(
                "invalid owner", *args, **kwargs)

    def test_nper(self, *args, **kwargs):
        """ Test setting nper to various values, valid and otherwise. """
        # Test valid nper values:
        # Continuous (can be represented as either None or 'C')
        account = self.AccountType(
            self.owner, *args, nper='C', **kwargs)
        self.assertEqual(account.nper, None)
        self.assertIsInstance(account.nper, (type(None), str))

        # Daily
        account = self.AccountType(
            self.owner, *args, nper='D', **kwargs)
        self.assertEqual(account.nper, 365)
        self.assertIsInstance(account.nper, int)

        # Weekly
        account = self.AccountType(
            self.owner, *args, nper='W', **kwargs)
        self.assertEqual(account.nper, 52)

        # Biweekly
        account = self.AccountType(
            self.owner, *args, nper='BW', **kwargs)
        self.assertEqual(account.nper, 26)

        # Semi-monthly
        account = self.AccountType(
            self.owner, *args, nper='SM', **kwargs)
        self.assertEqual(account.nper, 24)

        # Monthly
        account = self.AccountType(
            self.owner, *args, nper='M', **kwargs)
        self.assertEqual(account.nper, 12)

        # Bimonthly
        account = self.AccountType(
            self.owner, *args, nper='BM', **kwargs)
        self.assertEqual(account.nper, 6)

        # Quarterly
        account = self.AccountType(
            self.owner, *args, nper='Q', **kwargs)
        self.assertEqual(account.nper, 4)

        # Semiannually
        account = self.AccountType(
            self.owner, *args, nper='SA', **kwargs)
        self.assertEqual(account.nper, 2)

        # Annually
        account = self.AccountType(
            self.owner, *args, nper='A', **kwargs)
        self.assertEqual(account.nper, 1)

        # Test invalid nper values:
        with self.assertRaises(ValueError):
            account = self.AccountType(
                self.owner, *args, nper=0, **kwargs)

        with self.assertRaises(ValueError):
            account = self.AccountType(
                self.owner, *args, nper=-1, **kwargs)

        with self.assertRaises(TypeError):
            account = self.AccountType(
                self.owner, *args, nper=0.5, **kwargs)

        with self.assertRaises(TypeError):
            account = self.AccountType(
                self.owner, *args, nper=1.5, **kwargs)

        with self.assertRaises(ValueError):
            account = self.AccountType(
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
            self.owner, *args, balance=1, rate=1.0,
            transactions={}, nper=1, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Money(2))

        # No growth: Start with $1 and apply 0% growth.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=0, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Money(1))

        # Try with continuous growth
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1,
            transactions={}, nper='C', **kwargs)
        account.next_year()
        self.assertAlmostEqual(account.balance, Money(math.e), 3)

        # Try with discrete (monthly) growth
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1,
            transactions={}, nper='M', **kwargs)
        account.next_year()
        self.assertAlmostEqual(account.balance, Money((1 + 1 / 12) ** 12), 3)

        # Repeat above with a $2 contribution halfway through the year

        # Start with $1 (which grows to $2) and contribute $2.
        # NOTE: The growth of the $2 transaction is not well-defined,
        # since it occurs mid-compounding-period. However, the output
        # should be sensible. In  particular, it should grow by $0-$1.
        # So check to confirm that the result is in the range [$4, $5]
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1.0,
            transactions={0.5: Money(2)}, nper=1, **kwargs)
        account.next_year()
        self.assertGreaterEqual(account.balance, Money(4))
        self.assertLessEqual(account.balance, Money(5))

        # No growth: Start with $1, add $2, and apply 0% growth.
        account = self.AccountType(
            self.owner, *args, balance=1, rate=0,
            transactions={0.5: Money(2)}, nper=1, **kwargs)
        account.next_year()
        self.assertEqual(account.balance, Money(3))

        # Try with continuous growth
        # This can be calculated from P = P_0 * e^rt
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1,
            transactions={0.5: Money(2)}, nper='C', **kwargs)
        next_val = Money(1 * math.e + 2 * math.e ** 0.5)
        account.next_year()
        self.assertAlmostEqual(account.balance, next_val, 5)

        # Try with discrete growth
        # The $2 transaction happens at the start of a compounding
        # period, so behaviour is well-defined. It should grow by a
        # factor of (1 + r/n)^nt, for n = 12, t = 0.5
        account = self.AccountType(
            self.owner, *args, balance=1, rate=1,
            transactions={0.5: Money(2)}, nper='M', **kwargs)  # monthly
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
            self.owner, *args, balance=100, rate=0,
            transactions={}, nper=1, **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        self.assertEqual(account.max_outflow(0.5), Money(-100))
        self.assertEqual(account.max_outflow('end'), Money(-100))

        # Try with negative balance - should return $0
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1,
            transactions={}, nper=1, **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(0))
        self.assertEqual(account.max_outflow('end'), Money(0))

        # $100 in account that grows to $200 in one compounding period.
        # No transactions.
        # NOTE: Account balances mid-compounding-period are not
        # well-defined in the current implementation, so avoid
        # testing at when=0.5
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1,
            transactions={}, nper=1, **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        # self.assertEqual(account.max_outflow(0.5), Money(-150))
        self.assertEqual(account.max_outflow('end'), Money(-200))

        # $100 in account that grows linearly by 100%. Add $100
        # transactions at the start and end of the year.
        # NOTE: Behaviour of transactions between compounding
        # points is not well-defined, so avoid adding transactions at
        # 0.5 (or anywhere other than 'start' or 'end') when nper = 1
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1,
            transactions={'start': 100, 'end': 100}, nper=1, **kwargs)
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
            self.owner, *args, balance=-200, rate=2.0,
            transactions={'start': 100, 0.5: 200, 'end': 100}, nper=2,
            **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(0))
        self.assertEqual(account.balance_at_time('start'), Money(-100))
        self.assertEqual(account.max_outflow(0.5), Money(0))
        self.assertEqual(account.max_outflow('end'), Money(-100))

        # Test compounding. First: discrete compounding, once at the
        # halfway point. Add a $100 transaction at when=0.5 just to be
        # sure.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1,
            transactions={0.5: Money(100)}, nper=2, **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        # self.assertEqual(account.max_outflow(0.25), Money(-125))
        self.assertEqual(account.max_outflow(0.5), Money(-250))
        # self.assertEqual(account.max_outflow(0.75), Money(-312.50))
        self.assertEqual(account.max_outflow('end'), Money(-375))

        # Now to test continuous compounding. Add a $100 transaction at
        # when=0.5 just to be sure.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1,
            transactions={0.5: Money(100)}, nper='C', **kwargs)
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
        # This method should return the growth in the account.
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0,
            transactions={0: 100, 1: -100}, **kwargs)
        self.assertEqual(account.taxable_income, Money(200))

        # Losses are not taxable:
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0,
            transactions={0: 100, 1: -100}, **kwargs)
        self.assertEqual(account.taxable_income, Money(0))

    def test_tax_withheld(self, *args, **kwargs):
        """ Test Account.tax_withheld """
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0,
            transactions={0: 100, 1: -100}, **kwargs)
        self.assertEqual(account.tax_withheld, Money(0))

        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0,
            transactions={0: 100, 1: -100}, **kwargs)
        self.assertEqual(account.tax_withheld, Money(0))

    def test_tax_credit(self, *args, **kwargs):
        """ Test Account.tax_credit """
        # This method should always return $0, regardless of balance,
        # inflows, or outflows
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0,
            transactions={0: 100, 1: -100}, **kwargs)
        self.assertEqual(account.tax_credit, Money(0))

        # Test with negative balance
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0,
            transactions={0: 100, 1: -100}, **kwargs)
        self.assertEqual(account.tax_credit, Money(0))

    def test_tax_deduction(self, *args, **kwargs):
        """ Test Account.tax_deduction """
        # This method should always return $0, regardless of balance,
        # inflows, or outflows
        account = self.AccountType(
            self.owner, *args, balance=100, rate=1.0,
            transactions={0: 100, 1: -100}, **kwargs)
        self.assertEqual(account.tax_deduction, Money(0))

        # Test with negative balance
        account = self.AccountType(
            self.owner, *args, balance=-100, rate=1.0,
            transactions={0: 100, 1: -100}, **kwargs)
        self.assertEqual(account.tax_deduction, Money(0))


class TestRegisteredAccountMethods(TestAccountMethods):
    """ Tests RegisteredAccount. """

    @classmethod
    def setUpClass(cls):
        """ Sets up variables for testing RegisteredAccount """
        super().setUpClass()

        cls.AccountType = RegisteredAccount
        cls.contribution_room = 0

    def test_init_basic(self, *args, **kwargs):
        """ Test RegisteredAccount.__init__ """
        super().test_init_basic(
            *args, contribution_room=self.contribution_room, **kwargs)

        # Basic init using pre-built RegisteredAccount-specific args
        # and default Account args
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.contribution_room, self.contribution_room)

        # Try again with default contribution_room
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.contributor, self.owner)
        # Different subclasses have different default contribution room
        # values, so don't test subclasses
        if self.AccountType == RegisteredAccount:
            self.assertEqual(account.contribution_room, 0)

        # Test invalid `person` input
        with self.assertRaises(TypeError):
            account = self.AccountType(
                self.initial_year, 'invalid person', *args, **kwargs)

        # Finally, test a non-Money-convertible contribution_room:
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                contribution_room='invalid', **kwargs)

    def test_properties(self, *args, **kwargs):
        """ Test RegisteredAccount properties """
        # Basic check: properties return scalars (current year's values)
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contribution_room,
                         self.contribution_room)

        # NOTE: RegisteredAccount.next_year() raises NotImplementedError
        # and some subclasses require args for next_year(). That is
        # already dealt with by test_next, so check that properties are
        # pointing to the current year's values after calling next_year
        # in text_next.

    def test_next_year(self, *args, **kwargs):
        # next_contribution_room is not implemented for
        # RegisteredAccount, and it's required for next_year, so confirm
        # that trying to call next_year() throws an appropriate error.
        if self.AccountType == RegisteredAccount:
            account = RegisteredAccount(self.owner)
            with self.assertRaises(NotImplementedError):
                account.next_year()
        # For other account types, try a conventional next_year test
        else:
            super().test_next_year(
                *args, **kwargs)

    def test_returns(self, *args, **kwargs):
        # super().test_returns calls next_year(), which calls
        # next_contribution_room(), which is not implemented for
        # RegisteredAccount. Don't test returns for this class,
        # and instead allow subclasses to pass through.
        if self.AccountType != RegisteredAccount:
            super().test_returns(*args, **kwargs)

    def test_max_inflow(self, *args, **kwargs):
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.max_inflow(), self.contribution_room)

        account = self.AccountType(
            self.owner, *args,
            contribution_room=1000000, **kwargs)
        self.assertEqual(account.max_inflow(), Money(1000000))


class TestDebtMethods(unittest.TestCase):
    """ Test Debt. """

    @classmethod
    def setUpClass(cls):
        """ Sets up class attributes for convenience. """
        super().setUpClass()
        cls.AccountType = Debt

        # It's important to synchronize the initial years of related
        # objects, so store it here:
        cls.initial_year = 2000
        # Every init requires an owner, so store that here:
        cls.owner = Person(
            cls.initial_year, "test", 2000,
            raise_rate={year: 1 for year in range(2000, 2066)},
            retirement_date=2065)

        # Debt takes three args: reduction_rate (Decimal),
        # minimum_payment (Money), and accelerate_payment (bool)
        cls.minimum_payment = Money(10)
        cls.reduction_rate = Decimal(1)
        cls.accelerate_payment = True

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
        self.assertEqual(account.accelerate_payment, False)

        # Test init with appropriate-type args.
        minimum_payment = Money(100)
        reduction_rate = Decimal(1)
        accelerate_payment = False
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=minimum_payment, reduction_rate=reduction_rate,
            accelerate_payment=accelerate_payment, **kwargs)
        self.assertEqual(account.minimum_payment, minimum_payment)
        self.assertEqual(account.reduction_rate, reduction_rate)
        self.assertEqual(account.accelerate_payment, accelerate_payment)

        # Test init with args of alternative types.
        minimum_payment = 100
        reduction_rate = 1
        accelerate_payment = 'Evaluates to True, like all non-empty strings'
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=minimum_payment, reduction_rate=reduction_rate,
            accelerate_payment=accelerate_payment, **kwargs)
        self.assertEqual(account.minimum_payment, minimum_payment)
        self.assertEqual(account.reduction_rate, reduction_rate)
        self.assertEqual(account.accelerate_payment, bool(accelerate_payment))

        # Test init with args of non-convertible types
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                minimum_payment='invalid', **kwargs)
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                reduction_rate='invalid', **kwargs)

    def test_max_inflow(self, *args, **kwargs):
        """ Test Debt.max_inflow """
        # Test when balance is greater than minimum payment
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=-1000, **kwargs)
        self.assertEqual(account.max_inflow(), Money(1000))

        # Test when balance is less than minimum payment
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=1000, balance=-100, **kwargs)
        self.assertEqual(account.max_inflow(), Money(100))

        # Test when minimum payment and balance are equal in size
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=-100, **kwargs)
        self.assertEqual(account.max_inflow(), Money(100))

        # Test with 0 balance
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=0, **kwargs)
        self.assertEqual(account.max_inflow(), Money(0))

    def test_min_inflow(self, *args, **kwargs):
        """ Test Debt.min_inflow """
        # Test when balance is greater than minimum payment
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=-1000, **kwargs)
        self.assertEqual(account.min_inflow(), Money(100))

        # Test when balance is less than minimum payment
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=1000, balance=-100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(100))

        # Test when minimum payment and balance are equal in size
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=-100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(100))

        # Test with 0 balance
        account = self.AccountType(
            self.owner, *args,
            minimum_payment=100, balance=0, **kwargs)
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

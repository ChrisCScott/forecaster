''' Unit tests for `People` and `Account` classes. '''

import unittest
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
import warnings
import math
import decimal
from decimal import Decimal
from settings import Settings
import ledger
from ledger import Money
from ledger import Account
from ledger import When
from test_helper import *


class TestWhen(unittest.TestCase):
    """ A test case for the `When` class. """

    def test_new(self):
        """ Tests `When.__new__` """

        # Test a simple, single-valued input
        w = When(1)
        self.assertEqual(w, Decimal(1))

        # Test a magic input
        w = When('start')
        self.assertEqual(w, Decimal(1))

        # Test default initialization
        w = When()
        self.assertEqual(w, Decimal())

        # Test non-magic str input
        w = When('1')
        self.assertEqual(w, Decimal(1))

        with self.assertRaises(decimal.InvalidOperation):
            w = When('invalid input')


# TODO: Update Account tests to use new multi-year data model


class TestAccountMethods(unittest.TestCase):
    """ A test suite for the `Account` class """

    def test_init(self, AccountType=Account):
        """ Tests Account.__init__ """

        # Basic test: All correct values, check for equality and type
        balance = Money(0)
        apr = 1.0
        transactions = {1: Money(1), 0: Money(-1)}
        nper = 1  # This is the easiest case, since apr==rate.
        settings = Settings()
        account = AccountType(balance, apr, transactions, nper, settings)
        # Test primary attributes
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.apr, apr)
        self.assertEqual(account.transactions, transactions)
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.settings, settings)
        self.assertIsInstance(account.balance, Money)
        self.assertIsInstance(account.apr, Decimal)
        self.assertIsInstance(account.transactions, dict)
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.settings, Settings)

        # Basic test: Only balance provided.
        account = AccountType(balance)
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.apr, 0)
        self.assertEqual(account.transactions, {})
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.settings, Settings)

        # Test with (Decimal-convertible) strings as input
        balance = "0"
        apr = "1.0"
        transactions = {'start': "1", 'end': "-1"}
        nper = 'A'
        account = AccountType(balance, apr, transactions, nper)
        # Test primary attributes
        self.assertEqual(account.balance, Money(0))
        self.assertEqual(account.apr, 1)
        self.assertEqual(account.transactions, {1: Money(1), 0: Money(-1)})
        self.assertEqual(account.nper, 1)
        self.assertIsInstance(account.balance, Money)
        self.assertIsInstance(account.apr, Decimal)
        self.assertIsInstance(account.transactions, dict)
        for key, value in account.transactions.items():
            self.assertIsInstance(key, (float, int, Decimal))
            self.assertIsInstance(value, Money)
        self.assertIsInstance(account.nper, int)

        # Test 'when' values inside and outside of the range [0,1]
        account = AccountType(balance, transactions={0: 1})
        self.assertEqual(account.transactions[Decimal(0)], Money(1))
        account = AccountType(balance, transactions={0.5: 1})
        self.assertEqual(account.transactions[Decimal(0.5)], Money(1))
        account = AccountType(balance, transactions={1: 1})
        self.assertEqual(account.transactions[Decimal(1)], Money(1))
        with self.assertRaises(ValueError):
            account = AccountType(balance, transactions={-1: 1})
        with self.assertRaises(ValueError):
            account = AccountType(balance, transactions={2: 1})

        # Let's test invalid Decimal conversions next.
        # BasicContext causes most errors to raise exceptions
        # In particular, invalid input will raise InvalidOperation
        decimal.setcontext(decimal.BasicContext)

        # Test with values not convertible to Decimal
        with self.assertRaises(decimal.InvalidOperation):
            account = AccountType(balance="invalid input")
            # In some contexts, Decimal returns NaN instead of raising an error
            if account.balance == Money("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = AccountType(balance, apr="invalid input")
            if account.rate == Decimal("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises((decimal.InvalidOperation, KeyError)):
            account = AccountType(balance, transactions={"invalid input": 1})
            if Decimal('NaN') in account.transactions.keys():
                raise decimal.InvalidOperation()

        # Test valid nper values:
        account = AccountType(balance, nper='C')  # continuous
        self.assertEqual(account.nper, None)
        self.assertIsInstance(account.nper, (type(None), str))

        account = AccountType(balance, nper='D')  # daily
        self.assertEqual(account.nper, 365)
        self.assertIsInstance(account.nper, int)

        account = AccountType(balance, nper='W')  # weekly
        self.assertEqual(account.nper, 52)

        account = AccountType(balance, nper='BW')  # biweekly
        self.assertEqual(account.nper, 26)

        account = AccountType(balance, nper='SM')  # semi-monthly
        self.assertEqual(account.nper, 24)

        account = AccountType(balance, nper='M')  # monthly
        self.assertEqual(account.nper, 12)

        account = AccountType(balance, nper='BM')  # bimonthly
        self.assertEqual(account.nper, 6)

        account = AccountType(balance, nper='Q')  # quarterly
        self.assertEqual(account.nper, 4)

        account = AccountType(balance, nper='SA')  # semiannually
        self.assertEqual(account.nper, 2)

        account = AccountType(balance, nper='A')  # annually
        self.assertEqual(account.nper, 1)

        # Test invalid nper values:
        with self.assertRaises(ValueError):
            account = AccountType(balance, nper=0)

        with self.assertRaises(ValueError):
            account = AccountType(balance, nper=-1)

        with self.assertRaises(TypeError):
            account = AccountType(balance, nper=0.5)

        with self.assertRaises(TypeError):
            account = AccountType(balance, nper=1.5)

        with self.assertRaises(ValueError):
            account = AccountType(balance, nper="invalid input")

        # Recurse onto all subclasses of AccountType
        # (Recall that, at first iteration, AccountType=Account)
        for SubType in AccountType.__subclasses__():
            self.test_init(SubType)

    def test_rate(self, AccountType=Account):
        """ Tests rate and nper.

        This also indirectly tests apr_to_rate and rate_to_apr """
        # Simple account: Start with $1, apply 100% growth once per
        # year, no transactions. Should yield a next_balance of $2.
        account = AccountType(1, Decimal(1.0), {}, 1)
        self.assertEqual(account.rate, Decimal(1))

        # Update rate via apr.setter.
        account.apr = Decimal(2.0)
        self.assertEqual(account.rate, Decimal(2))

        # Update rate via rate.setter.
        account.rate = Decimal(3.0)
        self.assertEqual(account.rate, Decimal(3))
        self.assertEqual(account.apr, Decimal(3))

        # Now let's update nper based on a str
        account.nper = 'C'  # continuous growth
        self.assertEqual(account.apr, Decimal(3))  # apr unchanged
        # Derive r [rate] from P = P_0 * e^rt
        self.assertEqual(account.rate, math.log(Decimal(3) + 1))
        self.assertEqual(account.nper, None)

        # Let's use a discrete compounding method (other than 'A'/1)
        account.nper = 'M'  # monthly compounding
        nper = account.nper
        self.assertEqual(account.apr, Decimal(3))  # apr unchanged
        # Derive r [rate] from P = P_0 * (1 + r/n)^nt
        # This works out to r = n * [(1 + apr)^(1 / n) - 1]
        self.assertAlmostEqual(account.rate,
                               Decimal(nper * (((1 + 3) ** (nper ** -1)) - 1)),
                               3)
        self.assertEqual(account.nper, 12)  # Just to be safe, check nper

        # Recurse onto all subclasses of AccountType
        # (Recall that, at first iteration, AccountType=Account)
        for SubType in AccountType.__subclasses__():
            self.test_init(SubType)

    def test_next(self, AccountType=Account):
        """ Tests next_balance and next_year.

        This also indirectly tests present_value and future_value.
        """
        # Simple account: Start with $1, apply 100% growth once per
        # year, no transactions. Should yield a next_balance of $2.
        account = AccountType(1, 1.0, {}, 1)
        self.assertEqual(account.next_balance, Money(2))
        self.assertEqual(account.next_year().balance, Money(2))

        # No growth: Start with $1 and apply 0% growth.
        account = AccountType(1, 0)
        self.assertEqual(account.next_balance, Money(1))
        self.assertEqual(account.next_year().balance, Money(1))

        # Try with continuous growth
        account = AccountType(1, 1, {}, 'C')
        self.assertAlmostEqual(account.next_balance, Money(2), 3)
        self.assertAlmostEqual(account.next_year().balance, Money(2), 3)

        # Try with discrete growth
        account = AccountType(1, 1, {}, 'M')  # monthly
        self.assertAlmostEqual(account.next_balance, Money(2), 3)
        self.assertAlmostEqual(account.next_year().balance, Money(2), 3)

        # Repeat above with a $2 contribution halfway through the year

        # Start with $1 (which grows to $2) and contribute $2.
        # NOTE: The growth of the $2 transaction is not well-defined,
        # since it occurs mid-compounding-period. However, the output
        # should be sensible. In  particular, it should grow by $0-$1.
        # So check to confirm that the result is in the range [$4, $5]
        account = AccountType(1, 1.0, {0.5: Money(2)}, 1)
        self.assertGreaterEqual(account.next_balance, Money(4))
        self.assertLessEqual(account.next_balance, Money(5))
        self.assertGreaterEqual(account.next_year().balance, Money(4))
        self.assertLessEqual(account.next_year().balance, Money(5))

        # No growth: Start with $1, add $2, and apply 0% growth.
        account = AccountType(1, 0, {0.5: Money(2)}, 1)
        self.assertEqual(account.next_balance, Money(3))
        self.assertEqual(account.next_year().balance, Money(3))

        # Try with continuous growth
        # Initial $1 will grow to $2 (because apr = 100%)
        # $2 added at mid-point will grow by a factor of e ^ rt
        # r is the instantantaneous rate of growth, not the apr.
        # This can be calculated via Account.apr_to_rate, or by deriving
        # from P = P_0 * e^rt -> 1 + apr = e^rt where t=1
        # so r = log(1 + apr) and $2 will grow to:
        # 2 * e ^ (log(1 + apr)t)) = 2 * (1 + apr)^t
        account = AccountType(1, 1, {0.5: Money(2)}, 'C')
        next_val = 2 * Money(1) + Money(2) * (1 + 1) ** Decimal(0.5)
        self.assertAlmostEqual(account.next_balance, next_val, 5)
        self.assertAlmostEqual(account.next_year().balance, next_val, 5)

        # Try with discrete growth
        # Initial $1 will grow to $2.
        # The $2 transaction happens at the start of a compounding
        # period, so behaviour is well-defined. It should grow by a
        # factor of (1 + r/n)^nt, for n = 12, t = 0.5
        # where r is derived from:
        # P = P_0 * (1 + r/n) ^ nt for P = P_0 * (1 + apr), apr = 1
        # This reduces to r = n * [(1 + apr)^(1/n) - 1]
        account = AccountType(1, 1, {0.5: Money(2)}, 'M')  # monthly
        r = Decimal(12 * ((1 + 1) ** (1/12) - 1))
        next_val = 2 * Money(1) + \
            Money(2) * (1 + r / 12) ** (12 * Decimal(0.5))
        self.assertEqual(account.rate, r)  # just to be safe
        self.assertAlmostEqual(account.next_balance, next_val, 5)
        self.assertAlmostEqual(account.next_year().balance, next_val, 5)

        # Recurse onto all subclasses of AccountType
        # (Recall that, at first iteration, AccountType=Account)
        for SubType in AccountType.__subclasses__():
            self.test_init(SubType)

    # TODO: When cached properties are implemented, provide a test.
    #    def test_cached_properties(self):
        """ Tests cached properties for various account types.

        Account: next_balance
        SavingsAccount: contributions, withdrawals, taxable_income,
            tax_withheld, tax_credit
        RRSP: taxable_income, tax_withheld
        TFSA: taxable_income
        TaxableAccount: _acb_and_capital_gain, next_acb, capital_gain,
            taxable_income
        Debt: payments, withdrawals
        OtherProperty: taxable_income
        """
    ''' Commented out:
        # Simple test: apr = rate, next_balance = 2
        account = AccountType(1, 1.0, {}, 1)
        next_account = AccountType(2)
        self.assertEqual(account.next_balance, Money(2))
        # Bypass setter methods (so cache is not invalidated).
        # If next_balance is cached, it will still return 2 (not 0)
        account._balance = 0
        self.assertEqual(account.next_balance, Money(2))
        # Now update balance through the setter
        account.balance = 0
        next_account = AccountType(0)
        self.assertEqual(account.next_balance, Money(0))
    '''

    def test_add_transaction(self, AccountType=Account):
        """ Tests add_transaction and related methods.

        Account: add_transaction
        SavingsAccount: contribute, withdraw
        Debt: pay, withdraw
        """
        # Start with an empty account and add a transaction.
        account = AccountType(balance=0, apr=0, transactions={})
        initial_year = account.initial_year
        self.assertEqual(account.transactions, {initial_year: {}})
        account.add_transaction(Money(1), 'end')
        self.assertEqual(account.transactions, {initial_year: {0: Money(1)}})
        self.assertEqual(account.inflows(initial_year), Money(1))
        # Just to be safe, confirm that new transactions are being seen
        # by next_balance
        self.assertEqual(account.next_balance(), Money(1))

        # Try adding multiple transactions at different times.
        account = AccountType(balance=0, apr=0, transactions={})
        account.add_transaction(Money(1), 0)
        account.add_transaction(Money(2), 'start')
        self.assertEqual(account.transactions, {initial_year:
                                                {0: Money(1), 1: Money(2)}})
        self.assertEqual(account.outflows(), 0)

        # Try adding multiple transactions at the same time.
        account = AccountType(balance=0, apr=0, transactions={})
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(1), 1)
        self.assertEqual(account.transactions, {initial_year: {1: Money(2)}})
        self.assertEqual(account.inflows(), Money(2))
        self.assertEqual(account.outflows(), 0)

        # Try adding both inflows and outflows at different times.
        account = AccountType(balance=0, apr=0, transactions={})
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'end')
        self.assertEqual(account.transactions, {initial_year:
                                                {1: Money(1), 0: Money(-2)}})
        self.assertEqual(account.inflows(), Money(1))
        self.assertEqual(account.outflows(), Money(-2))

        # Try adding simultaneous inflows and outflows
        # TODO: Consider whether this behaviour should be revised.
        account = AccountType(balance=0, apr=0, transactions={})
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'start')
        self.assertEqual(account.transactions, {initial_year: {1: Money(-1)}})
        self.assertEqual(account.inflows(), 0)
        self.assertEqual(account.outflows(), Money(-1))

        # Basic sanity tests for subclasses' aliases contribute/withdraw
        if issubclass(AccountType, ledger.SavingsAccount):
            account = AccountType(balance=0, apr=0, transactions={})
            account.contribute(Money(1), 'start')
            account.withdraw(Money(-2), 'end')
            self.assertEqual(account.transactions, {initial_year:
                                                    {1: Money(1),
                                                     0: Money(-2)}})
            self.assertEqual(account.contributions(), Money(1))
            self.assertEqual(account.withdrawals(), Money(-2))

        # Basic sanity tests for subclasses' aliases pay/withdraw
        if issubclass(AccountType, ledger.Debt):
            account = AccountType(balance=0, apr=0, transactions={})
            account.pay(Money(1), 'start')
            account.withdraw(Money(-2), 'end')
            self.assertEqual(account.transactions, {initial_year:
                                                    {1: Money(1),
                                                     0: Money(-2)}})
            self.assertEqual(account.payments(), Money(1))
            self.assertEqual(account.withdrawals(), Money(-2))

    # TODO: Test tax-related functionality (once we know where we want
    # it to live!)
    # TODO: Test OtherProperty (once we've settled on its functionality)
    # TODO: Test add_transactions again after performing next_year
    # (do this recursively?)

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

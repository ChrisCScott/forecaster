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
from ledger import Money
from ledger import Person
from ledger import Account


class TestPersonMethods(unittest.TestCase):
    """ A test suite for the `Person` class. """

    def setUp(self):
        """ Sets up default vaules for testing """
        self.name = "Testy McTesterson"
        self.birth_date = datetime(2000, 2, 1)  # 1 February 2000
        self.retirement_date = datetime(2065, 6, 26)  # 26 June 2065
        self.person = Person(self.name, self.birth_date, self.retirement_date)

    def test_init(self):
        """ Tests Person.__init__ """

        # Should work when all arguments are passed correctly
        person = Person(self.name, self.birth_date, self.retirement_date)
        self.assertEqual(person.name, self.name)
        self.assertEqual(person.birth_date, self.birth_date)
        self.assertEqual(person.retirement_date, self.retirement_date)
        self.assertIsInstance(person.name, str)
        self.assertIsInstance(person.birth_date, datetime)
        self.assertIsInstance(person.retirement_date, datetime)

        # Should work with optional arguments omitted
        person = Person(self.name, self.birth_date)
        self.assertEqual(person.name, self.name)
        self.assertEqual(person.birth_date, self.birth_date)
        self.assertIsNone(person.retirement_date)

        # Should work with strings instead of dates
        birth_date_str = "1 January 2000"
        birth_date = datetime(2000, 1, 1)
        person = Person(self.name, birth_date_str)
        self.assertEqual(person.birth_date, birth_date)
        self.assertIsInstance(person.birth_date, datetime)

        # Should fail if retirement_date precedes birth_date
        with self.assertRaises(ValueError):
            person = Person(self.name, self.birth_date,
                            self.birth_date - relativedelta(days=1))

        # Should fail if a string is not parseable to a date
        birth_date = "not a date"
        with self.assertRaises(ValueError):
            person = Person(self.name, birth_date)
        with self.assertRaises(ValueError):
            person = Person(self.name, self.birth_date, birth_date)

        # Should work with non-str/non-datetime values as well
        birth_date = 2000
        retirement_date = birth_date + 65
        person = Person(self.name, birth_date, retirement_date)
        self.assertEqual(person.birth_date.year,
                         datetime(2000, 1, 1).year)
        self.assertEqual(person.birth_date.year + 65,
                         person.retirement_date.year)
        self.assertEqual(person.birth_date.month,
                         person.retirement_date.month)
        self.assertEqual(person.birth_date.day,
                         person.retirement_date.day)

        # Let's mix different types of non-datetime inputs. Should work.
        birth_date = "3 February 2001"
        retirement_date = 2002
        person = Person(self.name, birth_date, retirement_date)
        birth_date = datetime(2001, 2, 3)
        self.assertEqual(person.birth_date, birth_date)
        self.assertEqual(person.retirement_date.year, retirement_date)
        self.assertEqual(person.birth_date.month,
                         person.retirement_date.month)
        self.assertEqual(person.birth_date.day,
                         person.retirement_date.day)

        # Let's mix datetime and non-datetime inputs. Should work.
        birth_date = "3 February 2001"
        retirement_date = datetime(2002, 1, 1)
        person = Person(self.name, birth_date, retirement_date)
        birth_date = datetime(2001, 2, 3)
        self.assertEqual(person.birth_date, birth_date)
        self.assertEqual(person.retirement_date.year, retirement_date.year)
        self.assertEqual(person.birth_date.month, birth_date.month)
        self.assertEqual(person.retirement_date.month,
                         retirement_date.month)
        self.assertEqual(person.birth_date.day, birth_date.day)
        self.assertEqual(person.retirement_date.day, retirement_date.day)

    def test_age(self):
        """ Tests person.age """

        # Test output for person's 20th birthday:
        date = self.birth_date + relativedelta(years=20)
        self.assertEqual(self.person.age(date), 20)
        self.assertIsInstance(self.person.age(date), int)

        # Test output for day before person's 20th birthday:
        date = self.birth_date + relativedelta(years=20, days=-1)
        self.assertEqual(self.person.age(date), 19)

        # Test output for day after person's 20th birthday:
        date = date + relativedelta(days=2)
        self.assertEqual(self.person.age(date), 20)

        # NOTE: The following tests for negative ages, and should
        # probably be left undefined (i.e. implementation-specific)

        # Test output for day before person's birth
        date = self.birth_date - relativedelta(days=1)
        self.assertEqual(self.person.age(date), -1)

        # Test output for one year before person's birth
        date = self.birth_date - relativedelta(years=1)
        self.assertEqual(self.person.age(date), -1)

        # Test output for one year and a day before person's birth
        date = self.birth_date - relativedelta(years=1, days=1)
        self.assertEqual(self.person.age(date), -2)

        # Repeat the above, but with strings
        date = str(self.birth_date + relativedelta(years=20))
        self.assertEqual(self.person.age(date), 20)

        date = str(self.birth_date + relativedelta(years=20) -
                   relativedelta(days=1))
        self.assertEqual(self.person.age(date), 19)

        date = str(self.birth_date + relativedelta(years=20, day=1))
        self.assertEqual(self.person.age(date), 20)

        date = str(self.birth_date - relativedelta(days=1))
        self.assertEqual(self.person.age(date), -1)

        # Finally, test ints as input
        date = self.birth_date.year + 20
        self.assertEqual(self.person.age(date), 20)

        date = self.birth_date.year - 1
        self.assertEqual(self.person.age(date), -1)

    def test_retirement_age(self):
        """ Tests person.retirement_age """

        # Test that the retirement age for stock person is accurate
        delta = relativedelta(self.person.retirement_date,
                              self.person.birth_date)
        self.assertEqual(self.person.retirement_age, delta.years)
        self.assertIsInstance(self.person.retirement_age, int)

        # Test retiring on 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65)
        person = Person(self.name, self.birth_date, retirement_date)
        self.assertEqual(person.retirement_age, 65)

        # Test retiring on day after 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65, day=1)
        person = Person(self.name, self.birth_date, retirement_date)
        self.assertEqual(person.retirement_age, 65)

        # Test retiring on day before 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65) - \
            relativedelta(days=1)
        person = Person(self.name, self.birth_date, retirement_date)
        self.assertEqual(person.retirement_age, 64)

        # Test person with no known retirement date
        person = Person(self.name, self.birth_date)
        self.assertIsNone(person.retirement_age)


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
        """ Tests rate and nper """
        # Simple account: Start with $1, apply 100% growth once per
        # year, no transactions. Should yield a next_balance of $2.
        account = Account(1, Decimal(1.0), {}, 1)
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

    def test_next(self, AccountType=Account):
        """ Tests next_balance and next_year. """
        # Simple account: Start with $1, apply 100% growth once per
        # year, no transactions. Should yield a next_balance of $2.
        account = Account(1, 1.0, {}, 1)
        self.assertEqual(account.next_balance, Money(2))
        self.assertEqual(account.next_year().balance, Money(2))

        # No growth: Start with $1 and apply 0% growth.
        account = Account(1, 0)
        self.assertEqual(account.next_balance, Money(1))
        self.assertEqual(account.next_year().balance, Money(1))

        # Try with continuous growth
        account = Account(1, 1, {}, 'C')
        self.assertAlmostEqual(account.next_balance, Money(2), 3)
        self.assertAlmostEqual(account.next_year().balance, Money(2), 3)

        # Try with discrete growth
        account = Account(1, 1, {}, 'M')  # monthly
        self.assertAlmostEqual(account.next_balance, Money(2), 3)
        self.assertAlmostEqual(account.next_year().balance, Money(2), 3)

        # Repeat above with a $2 contribution halfway through the year

        # Start with $1 (which grows to $2) and contribute $2 (which
        # doesn't grow, as it's contributed mid-period). Total: $4
        # NOTE: If partial growth is enabled (no interface for this
        # currently), the $2 contribution would grow to $3.
        account = Account(1, 1.0, {0.5: Money(2)}, 1)
        self.assertEqual(account.next_balance, Money(4))
        self.assertEqual(account.next_year().balance, Money(4))

        # No growth: Start with $1, add $2, and apply 0% growth.
        account = Account(1, 0, {0.5: Money(2)}, 1)
        self.assertEqual(account.next_balance, Money(1))
        self.assertEqual(account.next_year().balance, Money(1))

        # Try with continuous growth
        # Initial $1 will grow to $2 (because apr = 100%)
        # $2 added at mid-point will grow by a factor of e ^ rt
        # (which works out to 2 * e ^ 0.5)
        account = Account(1, 1, {0.5: Money(2)}, 'C')
        self.assertAlmostEqual(account.next_balance,
                               Money(2) * math.exp(0.5),
                               3)
        self.assertAlmostEqual(account.next_year().balance,
                               Money(2) * math.exp(0.5),
                               3)

        # Try with discrete growth
        # Initial $1 will grow to $2, and the $2 transaction will grow
        # by a factor of (1 + r/n)^nt = (1 + 1 / 6)^(6 * 0.5)
        account = Account(1, 1, {0.5: Money(2)}, 'M')  # monthly
        self.assertAlmostEqual(account.next_balance,
                               Money(2) * ((1 + (1 / 6)) ** (6 * 0.5)),
                               3)
        self.assertAlmostEqual(account.next_year().balance,
                               Money(2) * ((1 + (1 / 6)) ** (6 * 0.5)),
                               3)

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
        account = Account(1, 1.0, {}, 1)
        next_account = Account(2)
        self.assertEqual(account.next_balance, Money(2))
        # Bypass setter methods (so cache is not invalidated).
        # If next_balance is cached, it will still return 2 (not 0)
        account._balance = 0
        self.assertEqual(account.next_balance, Money(2))
        # Now update balance through the setter
        account.balance = 0
        next_account = Account(0)
        self.assertEqual(account.next_balance, Money(0))
    '''

    def test_add_transaction(self):
        """ Tests add_transaction and related methods.

        Account: add_transaction
        SavingsAccount: contribute, withdraw
        Debt: pay, withdraw
        """
        pass

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    warnings.simplefilter('error')
    unittest.main()

''' Unit tests for `People` and `Account` classes. '''

import unittest
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
import warnings
import math
import decimal
from decimal import Decimal
from random import Random
from settings import Settings
import ledger
from ledger import *
from test_helper import *


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


class TestWhen(unittest.TestCase):
    """ A test case for the `when_conv` free method. """

    def test_when_conv(self):
        """ Tests `when_conv` """

        # Test a simple, single-valued input
        w = when_conv(1)
        self.assertEqual(w, Decimal(1))

        # Test a magic input
        w = when_conv('start')
        self.assertEqual(w, Decimal(0))

        # Test a magic input
        w = when_conv('end')
        self.assertEqual(w, Decimal(1))

        # Test non-magic str input
        w = when_conv('1')
        self.assertEqual(w, Decimal(1))

        with self.assertRaises(decimal.InvalidOperation):
            w = when_conv('invalid input')


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

        # Initialize the args and kwargs attributes. Subclasses will
        # access these via add_args and get_args.
        cls.args = {}
        cls.kwargs = {}
        cls.add_args(Account)
        # Some subclasses add args that are based on initial_year, so
        # store that here at the class level:
        cls.initial_year = 2000

    @classmethod
    def add_args(cls, AccountType, *args, **kwargs):
        """ Convenience method. Adds args to the front of the list. """
        # Prepend args to the list of args for each superclass.
        # (This matches the pattern for Account subclasses, which
        # prepend their additional arguments)
        for AT in cls.args:
            la = list(args)
            la.extend(cls.args[AT])
            cls.args[AT] = la
        cls.args[AccountType] = []

        for AT in cls.kwargs:
            cls.kwargs[AT].update(kwargs)
        cls.kwargs[AccountType] = {}

    @classmethod
    def _get_args(cls, AccountType, arg_dict):
        """ Gets args (pre/post/kw) for methods that target AccountType. """
        # Get args for this account type
        if AccountType in arg_dict:
            return arg_dict[AccountType]
        # If this account type doesn't have args registered, then
        # iteratively check for each supertype's registered args.
        else:
            while AccountType is not Account:
                AccountType = AccountType.__bases__[0]
                if AccountType in arg_dict:
                    return arg_dict[AccountType]

    @classmethod
    def get_args(cls, AccountType):
        """ Convenience method. Returns (args, kwargs). """
        return (cls._get_args(AccountType, cls.args),
                cls._get_args(AccountType, cls.kwargs))

    def test_init(self):
        """ Tests Account.__init__ """
        args, kwargs = self.get_args(Account)

        # Basic test: All correct values, check for equality and type
        balance = Money(0)
        rate = 1.0
        transactions = {1: Money(1), 0: Money(-1)}
        nper = 1  # This is the easiest case to test
        initial_year = self.initial_year
        settings = Settings()
        account = self.AccountType(*args, balance, rate, transactions,
                                   nper, initial_year, settings,
                                   **kwargs)
        # Test primary attributes
        self.assertEqual(account._balance, {initial_year: balance})
        self.assertEqual(account._rate, {initial_year: rate})
        self.assertEqual(account._transactions, {initial_year: transactions})
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, rate)
        self.assertEqual(account.transactions, transactions)
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, initial_year)
        self.assertEqual(account.last_year, initial_year)

        # Check types
        self.assertIsInstance(account._balance, dict)
        for key, val in account._balance.items():
            self.assertIsInstance(key, int)
            self.assertIsInstance(val, Money)
        self.assertIsInstance(account.balance, Money)
        self.assertIsInstance(account._rate, dict)
        for key, val in account._rate.items():
            self.assertIsInstance(key, int)
            self.assertIsInstance(val, (Decimal, float, int))
        self.assertIsInstance(account.rate, Decimal)
        self.assertIsInstance(account._transactions, dict)
        for key, val in account._transactions.items():
            self.assertIsInstance(key, int)
            self.assertIsInstance(val, dict)
            for key, v in val.items():
                self.assertIsInstance(key, Decimal)
                self.assertIsInstance(v, Money)
        self.assertIsInstance(account.transactions, dict)
        for key, val in account.transactions.items():
            self.assertIsInstance(key, Decimal)
            self.assertIsInstance(val, Money)
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.initial_year, int)

        # Basic test: Only balance provided.
        account = self.AccountType(*args, balance, **kwargs)
        self.assertEqual(account._balance, {Settings.initial_year: balance})
        self.assertEqual(account._rate, {Settings.initial_year: 0})
        self.assertEqual(account._transactions, {Settings.initial_year: {}})
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, 0)
        self.assertEqual(account.transactions, {})
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, Settings.initial_year)

        # Test with (Decimal-convertible) strings as input
        balance = "0"
        rate = "1.0"
        transactions = {'start': "1", 'end': "-1"}
        nper = 'A'
        initial_year = self.initial_year
        account = self.AccountType(*args, balance, rate, transactions,
                                   nper, initial_year, settings,
                                   **kwargs)
        self.assertEqual(account._balance, {initial_year: Money(0)})
        self.assertEqual(account._rate, {initial_year: 1})
        self.assertEqual(account._transactions,
                         {initial_year: {0: Money(1), 1: Money(-1)}})
        self.assertEqual(account.balance, Money(0))
        self.assertEqual(account.rate, 1)
        self.assertEqual(account.transactions, {0: Money(1), 1: Money(-1)})
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, initial_year)
        # Check types for conversion
        self.assertIsInstance(account._balance[initial_year], Money)
        self.assertIsInstance(account._rate[initial_year], Decimal)
        self.assertIsInstance(account._transactions[initial_year], dict)
        for key, value in account.transactions.items():
            self.assertIsInstance(key, (float, int, Decimal))
            self.assertIsInstance(value, Money)
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.initial_year, int)

        # Test 'when' values inside and outside of the range [0,1]
        account = self.AccountType(*args,
                                   balance=balance, transactions={0: 1},
                                   initial_year=initial_year,
                                   **kwargs)
        self.assertEqual(account.transactions[Decimal(0)],
                         Money(1))
        account = self.AccountType(*args,
                                   balance=balance, transactions={0.5: 1},
                                   initial_year=initial_year,
                                   **kwargs)
        self.assertEqual(account.transactions[Decimal(0.5)],
                         Money(1))
        account = self.AccountType(*args,
                                   balance=balance, transactions={1: 1},
                                   initial_year=initial_year,
                                   **kwargs)
        self.assertEqual(account.transactions[Decimal(1)],
                         Money(1))
        with self.assertRaises(ValueError):
            account = self.AccountType(*args,
                                       balance=balance, transactions={-1: 1},
                                       **kwargs)
        with self.assertRaises(ValueError):
            account = self.AccountType(*args,
                                       balance=balance, transactions={2: 1},
                                       **kwargs)

        # Let's test invalid Decimal conversions next.
        # BasicContext causes most errors to raise exceptions
        # In particular, invalid input will raise InvalidOperation
        decimal.setcontext(decimal.BasicContext)

        # Test with values not convertible to Decimal
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(*args,
                                       balance="invalid input",
                                       **kwargs)
            # In some contexts, Decimal returns NaN instead of raising an error
            if account.balance == Money("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(*args,
                                       balance=balance, rate="invalid input",
                                       **kwargs)
            if account.rate == Decimal("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises((decimal.InvalidOperation, KeyError)):
            account = self.AccountType(*args,
                                       balance=balance,
                                       transactions={"invalid input": 1},
                                       **kwargs)
            if Decimal('NaN') in account.transactions:
                raise decimal.InvalidOperation()

        # Test valid nper values:
        # Continuous (can be represented as either None or 'C')
        account = self.AccountType(*args,
                                   balance=balance, nper='C',
                                   **kwargs)
        self.assertEqual(account.nper, None)
        self.assertIsInstance(account.nper, (type(None), str))

        # Daily
        account = self.AccountType(*args,
                                   balance=balance, nper='D',
                                   **kwargs)
        self.assertEqual(account.nper, 365)
        self.assertIsInstance(account.nper, int)

        # Weekly
        account = self.AccountType(*args,
                                   balance=balance, nper='W',
                                   **kwargs)
        self.assertEqual(account.nper, 52)

        # Biweekly
        account = self.AccountType(*args,
                                   balance=balance, nper='BW',
                                   **kwargs)
        self.assertEqual(account.nper, 26)

        # Semi-monthly
        account = self.AccountType(*args,
                                   balance=balance, nper='SM',
                                   **kwargs)
        self.assertEqual(account.nper, 24)

        # Monthly
        account = self.AccountType(*args,
                                   balance=balance, nper='M',
                                   **kwargs)
        self.assertEqual(account.nper, 12)

        # Bimonthly
        account = self.AccountType(*args,
                                   balance=balance, nper='BM',
                                   **kwargs)
        self.assertEqual(account.nper, 6)

        # Quarterly
        account = self.AccountType(*args,
                                   balance=balance, nper='Q',
                                   **kwargs)
        self.assertEqual(account.nper, 4)

        # Semiannually
        account = self.AccountType(*args,
                                   balance=balance, nper='SA',
                                   **kwargs)
        self.assertEqual(account.nper, 2)

        # Annually
        account = self.AccountType(*args,
                                   balance=balance, nper='A',
                                   **kwargs)
        self.assertEqual(account.nper, 1)

        # Test invalid nper values:
        with self.assertRaises(ValueError):
            account = self.AccountType(*args,
                                       balance=balance, nper=0,
                                       **kwargs)

        with self.assertRaises(ValueError):
            account = self.AccountType(*args,
                                       balance=balance, nper=-1,
                                       **kwargs)

        with self.assertRaises(TypeError):
            account = self.AccountType(*args,
                                       balance=balance, nper=0.5,
                                       **kwargs)

        with self.assertRaises(TypeError):
            account = self.AccountType(*args,
                                       balance=balance, nper=1.5,
                                       **kwargs)

        with self.assertRaises(ValueError):
            account = self.AccountType(*args,
                                       balance=balance, nper='invalid input',
                                       **kwargs)

    def test_next(self, *next_args, **next_kwargs):
        """ Tests next_balance and next_year.

        This also indirectly tests present_value and future_value.
        """
        args, kwargs = self.get_args(Account)

        # Simple account: Start with $1, apply 100% growth once per
        # year, no transactions. Should yield a next_balance of $2.
        account = self.AccountType(*args, 1, 1.0, {}, 1,
                                   **kwargs)
        self.assertEqual(account.next_balance(), Money(2))
        account.next_year(*next_args, **next_kwargs)
        self.assertEqual(account.balance, Money(2))

        # No growth: Start with $1 and apply 0% growth.
        account = self.AccountType(*args, 1, 0,
                                   **kwargs)
        self.assertEqual(account.next_balance(), Money(1))
        account.next_year(*next_args, **next_kwargs)
        self.assertEqual(account.balance, Money(1))

        # Try with continuous growth
        account = self.AccountType(*args, 1, 1, {}, 'C',
                                   **kwargs)
        self.assertAlmostEqual(account.next_balance(), Money(math.e), 3)
        account.next_year(*next_args, **next_kwargs)
        self.assertAlmostEqual(account.balance, Money(math.e), 3)

        # Try with discrete growth
        account = self.AccountType(*args, 1, 1, {}, 'M',
                                   **kwargs)  # monthly
        self.assertAlmostEqual(account.next_balance(),
                               Money((1+1/12) ** 12), 3)
        account.next_year(*next_args, **next_kwargs)
        self.assertAlmostEqual(account.balance, Money((1+1/12) ** 12), 3)

        # Repeat above with a $2 contribution halfway through the year

        # Start with $1 (which grows to $2) and contribute $2.
        # NOTE: The growth of the $2 transaction is not well-defined,
        # since it occurs mid-compounding-period. However, the output
        # should be sensible. In  particular, it should grow by $0-$1.
        # So check to confirm that the result is in the range [$4, $5]
        account = self.AccountType(*args, 1, 1.0, {0.5: Money(2)}, 1,
                                   **kwargs)
        self.assertGreaterEqual(account.next_balance(), Money(4))
        self.assertLessEqual(account.next_balance(), Money(5))
        account.next_year(*next_args, **next_kwargs)
        self.assertGreaterEqual(account.balance, Money(4))
        self.assertLessEqual(account.balance, Money(5))

        # No growth: Start with $1, add $2, and apply 0% growth.
        account = self.AccountType(*args, 1, 0, {0.5: Money(2)}, 1,
                                   **kwargs)
        self.assertEqual(account.next_balance(), Money(3))
        account.next_year(*next_args, **next_kwargs)
        self.assertEqual(account.balance, Money(3))

        # Try with continuous growth
        # This can be calculated from P = P_0 * e^rt
        account = self.AccountType(*args, 1, 1, {0.5: Money(2)}, 'C',
                                   **kwargs)
        next_val = Money(1 * math.e + 2 * math.e ** 0.5)
        self.assertAlmostEqual(account.next_balance(), next_val, 5)
        account.next_year(*next_args, **next_kwargs)
        self.assertAlmostEqual(account.balance, next_val, 5)

        # Try with discrete growth
        # The $2 transaction happens at the start of a compounding
        # period, so behaviour is well-defined. It should grow by a
        # factor of (1 + r/n)^nt, for n = 12, t = 0.5
        account = self.AccountType(*args, 1, 1, {0.5: Money(2)}, 'M',
                                   **kwargs)  # monthly
        next_val = Money((1 + 1/12) ** (12) + 2 * (1 + 1/12) ** (12 * 0.5))
        self.assertAlmostEqual(account.next_balance(), next_val, 5)
        account.next_year(*next_args, **next_kwargs)
        self.assertAlmostEqual(account.balance, next_val, 5)

    def test_add_transaction(self):
        """ Tests add_transaction and related methods.

        Account: add_transaction
        SavingsAccount: contribute, withdraw
        Debt: pay, withdraw
        """
        args, kwargs = self.get_args(Account)
        # We need to make sure that initial_year is in the same range
        # as inflation_adjustments, otherwise init will fail:
        initial_year = self.initial_year

        # Start with an empty account and add a transaction.
        account = self.AccountType(*args, 0, 0, {},
                                   initial_year=initial_year,
                                   **kwargs)
        self.assertEqual(account._transactions, {initial_year: {}})
        account.add_transaction(Money(1), 'end')
        self.assertEqual(account._transactions, {initial_year: {1: Money(1)}})
        self.assertEqual(account.transactions, {1: Money(1)})
        self.assertEqual(account.inflows(initial_year), Money(1))
        # Just to be safe, confirm that new transactions are being seen
        # by next_balance
        self.assertEqual(account.next_balance(), Money(1))

        # Try adding multiple transactions at different times.
        account = self.AccountType(*args, 0, 0, {},
                                   initial_year=initial_year,
                                   **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(2), 1)
        self.assertEqual(account._transactions, {initial_year:
                                                 {0: Money(1), 1: Money(2)}})
        self.assertEqual(account.inflows(), Money(3))
        self.assertEqual(account.outflows(), 0)

        # Try adding multiple transactions at the same time.
        account = self.AccountType(*args, 0, 0, {},
                                   initial_year=initial_year,
                                   **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(1), 0)
        self.assertEqual(account._transactions, {initial_year: {0: Money(2)}})
        self.assertEqual(account.inflows(), Money(2))
        self.assertEqual(account.outflows(), Money(0))

        # Try adding both inflows and outflows at different times.
        account = self.AccountType(*args, 0, 0, {},
                                   initial_year=initial_year,
                                   **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'end')
        self.assertEqual(account._transactions, {initial_year:
                                                 {0: Money(1), 1: Money(-2)}})
        self.assertEqual(account.inflows(), Money(1))
        self.assertEqual(account.outflows(), Money(-2))

        # Try adding simultaneous inflows and outflows
        # TODO: Consider whether this behaviour should be revised.
        account = self.AccountType(*args, 0, 0, {},
                                   initial_year=initial_year,
                                   **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'start')
        self.assertEqual(account._transactions, {initial_year: {0: Money(-1)}})
        self.assertEqual(account.inflows(), 0)
        self.assertEqual(account.outflows(), Money(-1))

        # TODO: Test add_transactions again after performing next_year
        # (do this recursively?)

    def test_max_outflow(self):
        args, kwargs = self.get_args(Account)

        # Simple scenario: $100 in a no-growth account with no
        # transactions. Should return $100 for any point in time.
        account = self.AccountType(*args, 100, 0, {}, 1,
                                   **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        self.assertEqual(account.max_outflow(0.5), Money(-100))
        self.assertEqual(account.max_outflow('end'), Money(-100))

        # Try with negative balance - should return $0
        account = self.AccountType(*args, -100, 1, {}, 1,
                                   **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(0))
        self.assertEqual(account.max_outflow('end'), Money(0))

        # $100 in account that grows to $200 in one compounding period.
        # No transactions.
        # NOTE: Account balances mid-compounding-period are not
        # well-defined in the current implementation, so avoid
        # testing at when=0.5
        account = self.AccountType(*args, 100, 1, {}, 1,
                                   **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        # self.assertEqual(account.max_outflow(0.5), Money(-150))
        self.assertEqual(account.max_outflow('end'), Money(-200))

        # $100 in account that grows linearly by 100%. Add $100
        # transactions at the start and end of the year.
        # NOTE: Behaviour of transactions between compounding
        # points is not well-defined, so avoid adding transactions at
        # 0.5 (or anywhere other than 'start' or 'end') when nper = 1
        account = self.AccountType(*args, 100, 1,
                                   {'start': 100, 'end': 100}, 1,
                                   **kwargs)
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
        account = self.AccountType(*args, -200, 2.0,
                                   {'start': 100, 0.5: 200, 'end': 100}, 2,
                                   **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(0))
        self.assertEqual(account.balance_at_time('start'), Money(-100))
        self.assertEqual(account.max_outflow(0.5), Money(0))
        self.assertEqual(account.max_outflow('end'), Money(-100))

        # Test compounding. First: discrete compounding, once at the
        # halfway point. Add a $100 transaction at when=0.5 just to be
        # sure.
        account = self.AccountType(*args, 100, 1, {0.5: Money(100)}, 2,
                                   **kwargs)
        self.assertEqual(account.max_outflow('start'), Money(-100))
        # self.assertEqual(account.max_outflow(0.25), Money(-125))
        self.assertEqual(account.max_outflow(0.5), Money(-250))
        # self.assertEqual(account.max_outflow(0.75), Money(-312.50))
        self.assertEqual(account.max_outflow('end'), Money(-375))

        # Now to test continuous compounding. Add a $100 transaction at
        # when=0.5 just to be sure.
        account = self.AccountType(*args, 100, 1, {0.5: Money(100)}, 'C',
                                   **kwargs)
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

    def test_max_inflow(self, when='end', year=None):
        args, kwargs = self.get_args(Account)

        # This method should always return Money('Infinity')
        account = self.AccountType(*args, 100, **kwargs)
        self.assertEqual(account.max_inflow(), Money('Infinity'))

        account = self.AccountType(*args, -100, **kwargs)
        self.assertEqual(account.max_inflow(), Money('Infinity'))

    def test_min_outflow(self, when='end', year=None):
        args, kwargs = self.get_args(Account)

        # This method should always return $0
        account = self.AccountType(*args, 100, **kwargs)
        self.assertEqual(account.min_outflow(), Money(0))

        account = self.AccountType(*args, -100, **kwargs)
        self.assertEqual(account.min_outflow(), Money(0))

    def test_min_inflow(self, when='end', year=None):
        args, kwargs = self.get_args(Account)

        # This method should always return $0
        account = self.AccountType(*args, 100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(0))

        account = self.AccountType(*args, -100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(0))

    def test_taxable_income(self, year=None):
        args, kwargs = self.get_args(Account)

        # This method should always return $0
        account = self.AccountType(*args, 100, 1.0, {0: 100, 1: -100},
                                   **kwargs)
        self.assertEqual(account.taxable_income(), Money(0))

        account = self.AccountType(*args, -100, 1.0, {0: 100, 1: -100},
                                   **kwargs)
        self.assertEqual(account.taxable_income(), Money(0))

    def test_tax_withheld(self, year=None):
        args, kwargs = self.get_args(Account)

        # This method should always return $0
        account = self.AccountType(*args, 100, 1.0, {0: 100, 1: -100},
                                   **kwargs)
        self.assertEqual(account.tax_withheld(), Money(0))

        account = self.AccountType(*args, -100, 1.0, {0: 100, 1: -100},
                                   **kwargs)
        self.assertEqual(account.tax_withheld(), Money(0))

    def test_tax_credit(self):
        args, kwargs = self.get_args(Account)

        # This method should always return $0, regardless of balance,
        # inflows, or outflows
        account = self.AccountType(*args, 100, 1.0, {0: 100, 1: -100},
                                   **kwargs)
        self.assertEqual(account.tax_credit(), Money(0))

        # Test with negative balance
        account = self.AccountType(*args, -100, 1.0, {0: 100, 1: -100},
                                   **kwargs)
        self.assertEqual(account.tax_credit(), Money(0))

    def test_tax_deduction(self):
        args, kwargs = self.get_args(Account)

        # This method should always return $0, regardless of balance,
        # inflows, or outflows
        account = self.AccountType(*args, 100, 1.0, {0: 100, 1: -100},
                                   **kwargs)
        self.assertEqual(account.tax_deduction(), Money(0))

        # Test with negative balance
        account = self.AccountType(*args, -100, 1.0, {0: 100, 1: -100},
                                   **kwargs)
        self.assertEqual(account.tax_deduction(), Money(0))


class TestRegisteredAccountMethods(TestAccountMethods):
    """ Tests RegisteredAccount. """

    @classmethod
    def setUpClass(cls):
        """ Sets up variables for testing RegisteredAccount """
        super().setUpClass()

        cls.AccountType = RegisteredAccount

        # RRSPs take three prepended arguments: person,
        # inflation_adjustments, and contribution_room.
        # NOTE: Pass all prepended arguments explicitly, even if optional.
        cls.person = Person('Testy McTesterson', 1980, 2045)

        # Randomly generate inflation adjustments based on inflation
        # rates of 1%-20%. Be sure to include both Settings.initial_year
        # and cls.initial_year in the range, since we use default-valued
        # inits a lot (which calls Settings.initial_year).
        # Add a few extra years on to the end for testing purposes.
        cls.inflation_adjustments = {
            min(cls.initial_year, Settings.initial_year): Decimal(1)
        }
        cls.extend_inflation_adjustments(
            min(cls.inflation_adjustments),
            max(cls.initial_year, Settings.initial_year) + 5)

        cls.contribution_room = 0
        # Insert prepended arguments at the front
        cls.add_args(RegisteredAccount, cls.person, cls.inflation_adjustments,
                     cls.contribution_room)

    @classmethod
    def extend_inflation_adjustments(cls, min_year, max_year):
        """ Convenience method.

        Ensures cls.inflation_adjustment spans min_year and max_year.
        """
        rand = Random()

        # Extend inflation_adjustments forwards, assuming 1-20% inflation
        i = min(cls.inflation_adjustments)
        while i > min_year:
            cls.inflation_adjustments[i - 1] = (
                cls.inflation_adjustments[i] /
                Decimal(1 + rand.randint(1, 20)/100)
            )
            i -= 1

        # Extend inflation_adjustments forwards, assuming 1-20% inflation
        i = max(cls.inflation_adjustments)
        while i < max_year:
            cls.inflation_adjustments[i + 1] = (
                cls.inflation_adjustments[i] *
                Decimal(1 + rand.randint(1, 20)/100)
            )
            i += 1

    def test_init(self):
        super().test_init()

        args, kwargs = self.get_args(RegisteredAccount)

        # Basic init using pre-built RegisteredAccount-specific args
        # and default Account args
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room, **kwargs)
        self.assertEqual(account.person, self.person)
        self.assertEqual(account._inflation_adjustments,
                         self.inflation_adjustments)
        self.assertEqual(account.contribution_room, self.contribution_room)

        # Try again with default contribution_room
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments, **kwargs)
        self.assertEqual(account.person, self.person)
        self.assertEqual(account._inflation_adjustments,
                         self.inflation_adjustments)
        # Different subclasses have different default contribution room
        # values. There's also no settings value for RegisteredAccount's
        # contribution_room parameter (it has a hardcoded default of 0),
        # so don't test this subclasses
        if self.AccountType == RegisteredAccount:
            self.assertEqual(account.contribution_room, 0)

        # Test invalid `person` input
        with self.assertRaises(TypeError):
            account = self.AccountType(*args, 'invalid person',
                                       self.inflation_adjustments, **kwargs)

        # Try type conversion for inflation_adjustments
        account = self.AccountType(*args, self.person,
                                   {'2000': '0.02', 2001.0: 0.5,
                                    Decimal(2002): 1, 2003: Decimal('0.03')},
                                   contribution_room=500,
                                   initial_year=2000, **kwargs)
        self.assertEqual(account.person, self.person)
        self.assertEqual(account._inflation_adjustments,
                         {2000: Decimal('0.02'), 2001: Decimal('0.5'),
                          2002: Decimal('1'), 2003: Decimal('0.03')})
        self.assertEqual(account.contribution_room, Money('500'))

        # Try invalid inflation_adjustments.
        # First, pass in a non-dict
        with self.assertRaises(TypeError):
            account = self.AccountType(*args, self.person, 'invalid',
                                       self.contribution_room, **kwargs)
        # Second, pass a dict with a non-Decimal-convertible value
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(*args, self.person, {2000: 'invalid'},
                                       self.contribution_room, **kwargs)

        # Finally, test a non-Money-convertible contribution_room:
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(*args, self.person,
                                       self.inflation_adjustments, 'invalid',
                                       **kwargs)

        # Test an initial year that's out of the range of inflation_adjustments
        with self.assertRaises(ValueError):
            account = self.AccountType(*args, self.person,
                                       {2000: 0.02, 2001: 0.015},
                                       initial_year=1999, **kwargs)

    def test_properties(self):
        # Properties are inflation_adjustment and contribution_room
        args, kwargs = self.get_args(RegisteredAccount)

        # Basic check: properties return scalars (current year's values)
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room, **kwargs)
        self.assertEqual(account.inflation_adjustment,
                         self.inflation_adjustments[account.initial_year])
        self.assertEqual(account.contribution_room,
                         self.contribution_room)

        # NOTE: RegisteredAccount.next_year() raises NotImplementedError
        # and some subclasses require args for next_year(). That is
        # already dealt with by test_next, so check that properties are
        # pointing to the current year's values after calling next_year
        # in text_next.

    def test_next(self, *next_args, **next_kwargs):
        args, kwargs = self.get_args(RegisteredAccount)
        # NOTE: Can test next_year for both ValueError (bad year) and
        # NotImplementedError (if year is good)

        if self.AccountType == RegisteredAccount:
            # Check that incrementing past the last year raises a
            # ValueError:
            account = self.AccountType(
                *args, self.person, self.inflation_adjustments,
                self.contribution_room,
                initial_year=max(self.inflation_adjustments),  # i.e. last year
                **kwargs)
            with self.assertRaises(ValueError):
                account.next_year(*next_args, **next_kwargs)

            account = self.AccountType(
                *args, self.person, self.inflation_adjustments,
                self.contribution_room,
                **kwargs)
            with self.assertRaises(NotImplementedError):
                account.next_year(*next_args, **next_kwargs)
        else:
            super().test_next(*next_args, **next_kwargs)

    def test_max_inflow(self):
        args, kwargs = self.get_args(RegisteredAccount)

        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room, **kwargs)
        self.assertEqual(account.max_inflow(), self.contribution_room)

        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   1000000, **kwargs)
        self.assertEqual(account.max_inflow(), Money(1000000))


class TestRRSPMethods(TestRegisteredAccountMethods):
    """ Test RRSP """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.AccountType = RRSP

        # Ensure that inflation_adjustments covers the entire range of
        # Constants.RRSPContributionAccrualMax and the years where
        # self.person is 71-95 (plus a few extra for testing)
        min_year = min(min(Constants.RRSPContributionRoomAccrualMax),
                       cls.person.birth_date.year +
                       min(Constants.RRSPRRIFMinWithdrawal))
        max_year = max(max(Constants.RRSPContributionRoomAccrualMax),
                       cls.person.birth_date.year +
                       max(Constants.RRSPRRIFMinWithdrawal)) + 2
        cls.extend_inflation_adjustments(min_year, max_year)

        # RRSPs take the same arguments as their superclass,
        # RegisteredAccount, and we want to explicitly pass person/etc.,
        # so there's no need to call add_args.

    def test_init(self):
        super().test_init()

        args, kwargs = self.get_args(RRSP)

        # The only thing that RRSP.__init__ does is set
        # RRIF_conversion_year, so test that:
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room, **kwargs)
        self.assertEqual(self.person.age(account.RRIF_conversion_year),
                         Constants.RRSPRRIFConversionAge)

    def test_taxable_income(self):
        # RRSP.taxable_income() overrides super().taxable_income(), so
        # there's no need to call the superclass testing method here.
        args, kwargs = self.get_args(RRSP)

        # Create an RRSP with a $1,000,000 balance and no withdrawals:
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room,
                                   balance=1000000, **kwargs)
        # Since withdrawals = $0, there's no taxable income
        self.assertEqual(account.taxable_income(), 0)

        # Now add a withdrawal, confirm it's included in taxable income
        account.add_transaction(-100, 'end')
        self.assertEqual(account.taxable_income(), Money(100))

        # Now add a contribution (at a different time), confirm that it
        # has no effect on taxable_income
        account.add_transaction(100, 'start')
        self.assertEqual(account.taxable_income(), Money(100))

    def test_tax_withheld(self):
        args, kwargs = self.get_args(RRSP)

        # First, test RRSP (not RRIF) behaviour:
        # Test RRSP with no withdrawals -> no tax withheld
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room,
                                   balance=1000000,
                                   **kwargs)
        self.assertEqual(account.tax_withheld(), 0)

        # Now add a withdrawal in the lowest withholding tax bracket,
        # say $1. This should be taxed at the lowest rate
        account.add_transaction(-1, 'end')
        self.assertEqual(account.tax_withheld(), Money(
            1 * min(Constants.RRSPWithholdingTaxRate.values())
        ))
        # Now add a transaction in the highest tax bracket, say $1000000
        # This should be taxed at the highest rate
        account.add_transaction(-999999, 'start')
        self.assertEqual(account.tax_withheld(), Money(
            1000000 * max(Constants.RRSPWithholdingTaxRate.values())
        ))

        # TODO: tax thresholds are not currently inflation-adjusted;
        # implement inflation-adjustment and then test for it here?

    def test_tax_deduction(self):
        # RRSP.taxdeduction() overrides super().tax_deduction(), so
        # there's no need to call the superclass testing method here.
        args, kwargs = self.get_args(RRSP)

        # Create an RRSP with a $1,000,000 balance and no contributions:
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room,
                                   balance=1000000, **kwargs)
        # Since contributions = $0, there's no taxable income
        self.assertEqual(account.taxable_income(), 0)

        # Now add an inflow, confirm it's included in taxable income
        account.add_transaction(100, 'end')
        self.assertEqual(account.tax_deduction(), Money(100))

        # Now add an outflow (at a different time), confirm that it
        # has no effect on taxable_income
        account.add_transaction(-100, 'start')
        self.assertEqual(account.tax_deduction(), Money(100))

    def test_next(self):
        # RRSP has a mandatory argument for next_year.
        super().test_next(income=Money(100000))

        args, kwargs = self.get_args(RRSP)

        initial_contribution_room = Money(100)
        # Set income to a non-Money object to test type-conversion.
        # Use a value less than inflation-adjusted RRSPAccrualMax
        income = 100000
        # Basic test:
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   initial_contribution_room,
                                   **kwargs)
        account.next_year(income=income)
        self.assertEqual(account.contribution_room,
                         initial_contribution_room +
                         Money(income) *
                         Constants.RRSPContributionRoomAccrualRate)

        # Convert income to Money now to avoid having to explicitly
        # convert results in every following test.
        income = Money(income)

        # Pick the initial year so that we'll know the accrual max. for
        # next year
        initial_year = min(Constants.RRSPContributionRoomAccrualMax) - 1
        # Use income that's $1000 more than is necessary to max out RRSP
        # contribution room accrual for the year.
        income = (Constants.RRSPContributionRoomAccrualMax[initial_year + 1] /
                  Constants.RRSPContributionRoomAccrualRate) + 1000
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   initial_contribution_room,
                                   initial_year=initial_year,
                                   **kwargs)
        account.next_year(income=income)
        # New contribution room should be the max, plus rollover from
        # the previous year.
        self.assertEqual(
            account.contribution_room,
            initial_contribution_room +
            Money(Constants.RRSPContributionRoomAccrualMax[initial_year + 1])
        )

        # Try again, but this time contribute the max. in the first year
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   initial_contribution_room,
                                   initial_year=initial_year,
                                   **kwargs)
        account.add_transaction(account.contribution_room)
        account.next_year(income=income)
        # New contribution room should be the max; no rollover.
        self.assertEqual(
            account.contribution_room,
            Money(Constants.RRSPContributionRoomAccrualMax[initial_year + 1])
        )

        # Try again, but this time start with the last year for which we
        # know the nominal accrual max already. The next year's accrual
        # max will need to be estimated via inflation-adjustment:
        initial_year = max(Constants.RRSPContributionRoomAccrualMax)
        # Inflation-adjust the (known) accrual max for the previous year
        # to get the max for this year.
        max_accrual = (
            Constants.RRSPContributionRoomAccrualMax[initial_year] *
            self.inflation_adjustments[initial_year + 1] /
            self.inflation_adjustments[initial_year]
        )
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   initial_contribution_room,
                                   initial_year=initial_year,
                                   **kwargs)
        # Let's have income that's between the initial year's max
        # accrual and the next year's max accrual:
        income = Money(
            (max_accrual +
             Constants.RRSPContributionRoomAccrualMax[initial_year]
             ) / 2
        ) / Constants.RRSPContributionRoomAccrualRate
        account.next_year(income=income)
        # New contribution room should be simply determined by the
        # accrual rate set in Constants plus rollover.
        self.assertEqual(
            account.contribution_room,
            initial_contribution_room +
            Constants.RRSPContributionRoomAccrualRate * income
        )

        # Try again, but now with income greater than the inflation-
        # adjusted accrual max.
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   initial_contribution_room,
                                   initial_year=initial_year,
                                   **kwargs)
        account.add_transaction(account.contribution_room)  # no rollover
        income = max_accrual / Constants.RRSPContributionRoomAccrualRate + 1000
        account.next_year(income=income)
        # New contribution room should be the max accrual; no rollover.
        self.assertAlmostEqual(account.contribution_room,
                               Money(max_accrual), 3)

    def test_min_outflow(self):
        # RRSP overrides min_outflow completely; no need to call super
        args, kwargs = self.get_args(RRSP)

        # Have a static RRSP (no inflows/outflows/change in balance)
        balance = 1000000
        initial_year = min(self.inflation_adjustments)
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room,
                                   balance=balance,
                                   rate=0,
                                   initial_year=initial_year,
                                   **kwargs)
        # For each year over a lifetime, check min_outflow is correct:
        for year in range(initial_year,
                          self.person.birth_date.year +
                          max(Constants.RRSPRRIFMinWithdrawal) + 1):
            age = self.person.age(year)
            # First, check that we've converted to an RRIF if required:
            if age > Constants.RRSPRRIFConversionAge:
                self.assertTrue(account.RRIF_conversion_year < year)
            # Next, if we've converted to an RRIF, check various
            # min_outflow scenarios:
            if account.RRIF_conversion_year < year:
                # If we've converted early, use the statutory formula
                # (i.e. 1/(90-age))
                if age < min(Constants.RRSPRRIFMinWithdrawal):
                    min_outflow = account.balance / (90 - age)
                # Otherwise, use the prescribed withdrawal amount:
                else:
                    if age > max(Constants.RRSPRRIFMinWithdrawal):
                        min_outflow = account.balance * \
                            max(Constants.RRSPRRIFMinWithdrawal.values())
                    # If we're past the range of prescribed amounts,
                    # use the largest prescribed amount
                    else:
                        min_outflow = account.balance * \
                            Constants.RRSPRRIFMinWithdrawal[age]
            # If this isn't an RRIF yet, there's no min. outflow.
            else:
                min_outflow = 0
            self.assertEqual(account.min_outflow(), min_outflow)
            # Advance the account and test again on the next year:
            # (We aren't testing inflows/contribution room, so use
            # income=0)
            account.next_year(income=0)

    def test_convert_to_RRIF(self):
        args, kwargs = self.get_args(RRSP)

        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room,
                                   **kwargs)
        self.assertNotEqual(account.RRIF_conversion_year, account.initial_year)
        account.convert_to_RRIF()
        self.assertEqual(account.RRIF_conversion_year, account.initial_year)

        # TODO: If we implement automatic RRIF conversions, test that.


class TestTFSAMethods(TestRegisteredAccountMethods):
    """ Test TFSA """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = TFSA

        # Ensure that inflation_adjustments covers the entire range of
        # Constants.TFSAAnnualAccrual
        min_year = min(Constants.TFSAAnnualAccrual)
        max_year = max(Constants.TFSAAnnualAccrual) + 10
        cls.extend_inflation_adjustments(min_year, max_year)

        # TFSAs take the same prepended arguments as its superclass,
        # RegisteredAccount, so no need to call add_args

    def test_init(self):
        super().test_init()

        args, kwargs = self.get_args(TFSA)

        # TFSAs began in 2009. Confirm that we're using that as our
        # baseline for future contribution_room determinations and that
        # we've correctly set contribution_room to $5000.
        # Basic test: manually set contribution_room
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room,
                                   **kwargs)
        self.assertEqual(account._base_accrual, Money(5000))
        self.assertEqual(account._base_accrual_year, 2009)
        self.assertEqual(account.contribution_room, self.contribution_room)

        accruals = self.get_accruals()

        # For each starting year, confirm that available contribution
        # room is the sum of past accruals.
        for year in accruals:
            account = self.AccountType(
                *args, self.person, self.inflation_adjustments,
                initial_year=year,
                **kwargs)
            self.assertEqual(
                account.contribution_room,
                Money(sum([accruals[i]
                           for i in range(min(accruals), year + 1)]))
            )

    def test_next(self):
        super().test_next()

        args, kwargs = self.get_args(TFSA)

        # Set up variables for testing.
        accruals = self.get_accruals()
        rand = Random()
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   rate=0,
                                   initial_year=min(accruals),
                                   balance=0,
                                   **kwargs)

        # For each year, confirm that the balance and contribution room
        # are updated appropriately
        transactions = Money(0)
        for year in accruals:
            # Add a transaction (either an inflow or outflow)
            transaction = rand.randint(-account.balance.amount,
                                       account.contribution_room.amount)
            account.add_transaction(transaction)
            # Confirm that contribution room is the same as accruals,
            # less any net transactions
            accrual = sum(
                [accruals[i] for i in range(min(accruals), year + 1)]
            )
            self.assertEqual(
                account.contribution_room, Money(accrual) - transactions
            )
            # Confirm that balance is equal to the sum of transactions
            # over the previous years (note that this is a no-growth
            # scenario, since rate=0)
            self.assertEqual(account.balance, transactions)
            # Advance the account to next year and repeat tests
            account.next_year()
            # Update the running total of transactions, to be referenced
            # in the next round of tests.
            transactions += Money(transaction)

    def get_accruals(self):
        # Build a secquence of accruals covering known accruals and
        # 10 years where we'll need to estimate accruals with rounding
        accruals = {}
        base_year = min(Constants.TFSAAnnualAccrual)
        base_accrual = Constants.TFSAAnnualAccrual[base_year]
        for year in range(min(Constants.TFSAAnnualAccrual),
                          max(Constants.TFSAAnnualAccrual) + 10):
            if year in Constants.TFSAAnnualAccrual:
                accruals[year] = Constants.TFSAAnnualAccrual[year]
            else:
                accrual = (
                    base_accrual * self.inflation_adjustments[year] /
                    self.inflation_adjustments[base_year]
                )
                accrual = round(
                    accrual / Constants.TFSAInflationRoundingFactor
                ) * Constants.TFSAInflationRoundingFactor
                accruals[year] = accrual
        return accruals

    def test_taxable_income(self):
        args, kwargs = self.get_args(TFSA)

        # This method should always return $0
        account = self.AccountType(*args, self.person,
                                   self.inflation_adjustments,
                                   self.contribution_room,
                                   balance=1000,
                                   **kwargs)
        # Throw in some transactions for good measure:
        account.add_transaction(100, 'start')
        account.add_transaction(-200, 'end')
        self.assertEqual(account.taxable_income(), Money(0))


class TestTaxableAccountMethods(TestAccountMethods):
    """ Test TaxableAccount """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = TaxableAccount

        # TaxableAccount.__init__ has one argument: acb
        cls.add_args(TaxableAccount, None)

    def test_init(self):
        super().test_init()

        args, kwargs = self.get_args(TaxableAccount)

        # Default init
        account = self.AccountType(*args, **kwargs)
        self.assertEqual(account.acb, account.balance)
        self.assertEqual(account.capital_gain, Money(0))

        # Confirm that acb is set to balance by default
        account = self.AccountType(*args, balance=100, **kwargs)
        self.assertEqual(account.acb, account.balance)
        self.assertEqual(account.capital_gain, Money(0))

        # Confirm that initializing an account with explicit acb works.
        # (In this case, acb is 0, so the balance is 100% capital gains,
        # but those gains are unrealized, so capital_gain is $0)
        account = self.AccountType(*args, acb=0, balance=100, rate=1, **kwargs)
        self.assertEqual(account.acb, Money(0))
        self.assertEqual(account.capital_gain, Money(0))

    def test_properties(self):
        # Account doesn't currently have a test_properties method, so
        # there's no need to call super().test_properties()

        args, kwargs = self.get_args(TaxableAccount)

        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(*args,
                                   acb=50, balance=100, rate=1,
                                   **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.capital_gain, Money(0))
        # Withdrawal the entire end-of-year balance.
        account.add_transaction(-200, 'end')
        # Transactions will affect acb in the following year, not this
        # one - therefore acb should be unchanged here.
        self.assertEqual(account.acb, Money(50))
        # capital_gains in this year should be updated to reflect the
        # new transaction.
        self.assertEqual(account.capital_gain, Money(150))
        # Now add a start-of-year inflow to confirm that capital_gains
        # isn't confused.
        account.add_transaction(100, 'start')
        self.assertEqual(account.acb, Money(50))
        # By the time of the withdrawal, acb=$150 and balance=$400.
        # The $200 withdrawal will yield a $125 capital gain.
        self.assertEqual(account.capital_gain, Money(125))

    def test_next(self):
        super().test_next()

        args, kwargs = self.get_args(TaxableAccount)

        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(*args,
                                   acb=50, balance=100, rate=1,
                                   **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.capital_gain, Money(0))
        # Withdrawal the entire end-of-year balance.
        account.add_transaction(-200, 'end')
        self.assertEqual(account.capital_gain, Money(150))

        account.next_year()
        # Expect $0 balance, $0 acb, and (initially) $0 capital gains
        self.assertEqual(account.balance, Money(0))
        self.assertEqual(account.acb, Money(0))
        self.assertEqual(account.capital_gain, Money(0))
        # Add inflow in the new year. It will grow by 100%.
        account.add_transaction(100, 'start')
        self.assertEqual(account.acb, Money(0))
        self.assertEqual(account.capital_gain, Money(0))

        account.next_year()
        # Expect $200 balance
        self.assertEqual(account.acb, Money(100))
        self.assertEqual(account.capital_gain, Money(0))
        account.add_transaction(-200, 'start')
        self.assertEqual(account.acb, Money(100))
        self.assertEqual(account.capital_gain, Money(100))

    def test_taxable_income(self):
        # Don't call super.test_taxable_income(). TaxableAccount
        # completely overrides the behaviour of taxable_income().

        args, kwargs = self.get_args(TaxableAccount)

        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(*args,
                                   acb=50, balance=100, rate=1,
                                   **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.taxable_income(), Money(0))
        # Withdrawal the entire end-of-year balance.
        account.add_transaction(-200, 'end')
        self.assertEqual(account.taxable_income(), Money(150)/2)

        account.next_year()
        # Expect $0 balance, $0 acb, and (initially) $0 capital gains
        self.assertEqual(account.taxable_income(), Money(0))
        # Add inflow in the new year. It will grow by 100%.
        account.add_transaction(100, 'start')
        self.assertEqual(account.taxable_income(), Money(0))

        account.next_year()
        # Expect $200 balance
        self.assertEqual(account.taxable_income(), Money(0))
        account.add_transaction(-200, 'start')
        self.assertEqual(account.taxable_income(), Money(100)/2)


class TestDebtMethods(TestAccountMethods):
    """ Test Debt. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = Debt

        # Debt takes three args: reduction_rate (Decimal),
        # minimum_payment (Money), and accelerate_payment (bool)
        minimum_payment = Money(10)
        reduction_rate = Decimal(1)
        accelerate_payment = True
        cls.add_args(Debt, minimum_payment, reduction_rate, accelerate_payment)

    def test_init(self):
        super().test_init()

        args, kwargs = self.get_args(Debt)

        # Test default init.
        account = self.AccountType(*args, **kwargs)
        self.assertEqual(account.minimum_payment, Money(0))
        self.assertEqual(account.reduction_rate, Settings.DebtReductionRate)
        self.assertEqual(account.accelerate_payment,
                         Settings.DebtAcceleratePayment)

        # Test init with appropriate-type args.
        minimum_payment = Money(100)
        reduction_rate = Decimal(1)
        accelerate_payment = False
        account = self.AccountType(*args, minimum_payment, reduction_rate,
                                   accelerate_payment, **kwargs)
        self.assertEqual(account.minimum_payment, minimum_payment)
        self.assertEqual(account.reduction_rate, reduction_rate)
        self.assertEqual(account.accelerate_payment, accelerate_payment)

        # Test init with args of alternative types.
        minimum_payment = 100
        reduction_rate = 1
        accelerate_payment = 'Evaluates to True, like all non-empty strings'
        account = self.AccountType(*args, minimum_payment, reduction_rate,
                                   accelerate_payment, **kwargs)
        self.assertEqual(account.minimum_payment, minimum_payment)
        self.assertEqual(account.reduction_rate, reduction_rate)
        self.assertEqual(account.accelerate_payment, bool(accelerate_payment))

        # Test init with args of non-convertible types
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(*args, minimum_payment='invalid',
                                       **kwargs)
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(*args, reduction_rate='invalid',
                                       **kwargs)

    def test_max_inflow(self):
        args, kwargs = self.get_args(Debt)

        # Test when balance is greater than minimum payment
        account = self.AccountType(*args, 100, balance=-1000, **kwargs)
        self.assertEqual(account.max_inflow(), Money(1000))

        # Test when balance is less than minimum payment
        account = self.AccountType(*args, 1000, balance=-100, **kwargs)
        self.assertEqual(account.max_inflow(), Money(100))

        # Test when minimum payment and balance are equal in size
        account = self.AccountType(*args, 100, balance=-100, **kwargs)
        self.assertEqual(account.max_inflow(), Money(100))

        # Test with 0 balance
        account = self.AccountType(*args, 100, balance=0, **kwargs)
        self.assertEqual(account.max_inflow(), Money(0))

    def test_min_inflow(self):
        args, kwargs = self.get_args(Debt)

        # Test when balance is greater than minimum payment
        account = self.AccountType(*args, 100, balance=-1000, **kwargs)
        self.assertEqual(account.min_inflow(), Money(100))

        # Test when balance is less than minimum payment
        account = self.AccountType(*args, 1000, balance=-100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(100))

        # Test when minimum payment and balance are equal in size
        account = self.AccountType(*args, 100, balance=-100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(100))

        # Test with 0 balance
        account = self.AccountType(*args, 100, balance=0, **kwargs)
        self.assertEqual(account.min_inflow(), Money(0))


class TestPrincipleResidenceMethods(TestAccountMethods):
    """ Test PrincipleResidence. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = PrincipleResidence

        # PrincipleResidence no additional arguments, so no need to call
        # add_args

    def test_taxable_income(self):
        # Currently, Account also always returns $0 for taxable income,
        # so we can simply call the superclass's testing method.
        # Still, since PrincipleResidence overrides
        super().test_taxable_income()

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

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
from tax import Tax
from strategy import AllocationStrategy
from scenario import Scenario
import ledger
from ledger import *
from utility import *
from test_helper import *


class TestPersonMethods(unittest.TestCase):
    """ A test suite for the `Person` class. """

    def setUp(self):
        """ Sets up default vaules for testing """
        self.initial_year = 2020
        self.name = "Testy McTesterson"
        self.birth_date = datetime(2000, 2, 1)  # 1 February 2000
        self.retirement_date = datetime(2065, 6, 26)  # 26 June 2065
        self.gross_income = Money(100000)  # $100000
        self.raise_rate = Decimal(1)  # 100%
        self.tax_treatment = Tax(
            {self.initial_year: {
                Money(0): Decimal('0.1'),
                Money(1000): Decimal('0.2'),
                Money(100000): Decimal('0.3')}
             },
            inflation_adjust={
                year: Decimal(1 + (year - self.initial_year) / 16)
                for year in range(self.initial_year, self.initial_year + 100)
             },
            personal_deduction={self.initial_year: Money(100)},
            credit_rate={self.initial_year: Decimal('0.15')})
        scenario = Scenario(
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
            adjust_for_retirement_plan=False,
            scenario=scenario)
        self.spouse = Person(
            initial_year=self.initial_year,
            name="Spouse",
            birth_date=1998,
            retirement_date=2063,
            gross_income=Money(50000),
            raise_rate=self.raise_rate,
            spouse=None,
            tax_treatment=self.tax_treatment,
            allocation_strategy=self.allocation_strategy)
        self.owner = Person(
            initial_year=self.initial_year,
            name=self.name,
            birth_date=self.birth_date,
            retirement_date=self.retirement_date,
            gross_income=self.gross_income,
            raise_rate=self.raise_rate,
            spouse=self.spouse,
            tax_treatment=self.tax_treatment,
            allocation_strategy=self.allocation_strategy)

    def test_init(self):
        """ Tests Person.__init__ """

        # Should work when all required arguments are passed correctly
        person = Person(
            self.initial_year, self.name, self.birth_date,
            retirement_date=self.retirement_date)
        self.assertEqual(person.name, self.name)
        self.assertEqual(person.birth_date, self.birth_date)
        self.assertEqual(person.retirement_date, self.retirement_date)
        self.assertIsInstance(person.name, str)
        self.assertIsInstance(person.birth_date, datetime)
        self.assertIsInstance(person.retirement_date, datetime)
        self.assertIsNone(person.spouse)
        self.assertIsNone(person.allocation_strategy)
        self.assertIsNone(person.tax_treatment)

        # Should work with strings instead of dates
        birth_date_str = "1 January 2000"
        birth_date = datetime(2000, 1, 1)
        person = Person(
            self.initial_year, self.name, birth_date_str,
            retirement_date=self.retirement_date)
        self.assertEqual(person.birth_date, birth_date)
        self.assertIsInstance(person.birth_date, datetime)

        # Should fail if retirement_date precedes birth_date
        with self.assertRaises(ValueError):
            person = Person(
                self.initial_year, self.name, self.birth_date,
                retirement_date=self.birth_date - relativedelta(days=1))

        # Should fail if a string is not parseable to a date
        with self.assertRaises(ValueError):
            person = Person(
                self.initial_year, self.name, 'invalid',
                retirement_date=self.retirement_date)
        with self.assertRaises(ValueError):
            person = Person(
                self.initial_year, self.name, self.birth_date,
                retirement_date='invalid')

        # Should work with non-str/non-datetime values as well
        birth_date = 2000
        retirement_date = birth_date + 65
        person = Person(
            self.initial_year, self.name, birth_date,
            retirement_date=retirement_date)
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
        person = Person(
            self.initial_year, self.name, birth_date,
            retirement_date=retirement_date)
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
        person = Person(
            self.initial_year, self.name, birth_date,
            retirement_date=retirement_date)
        birth_date = datetime(2001, 2, 3)
        self.assertEqual(person.birth_date, birth_date)
        self.assertEqual(person.retirement_date.year, retirement_date.year)
        self.assertEqual(person.birth_date.month, birth_date.month)
        self.assertEqual(person.retirement_date.month,
                         retirement_date.month)
        self.assertEqual(person.birth_date.day, birth_date.day)
        self.assertEqual(person.retirement_date.day, retirement_date.day)

        # Now confirm that we can pass gross_income, spouse,
        # tax_treatment, allocation_strategy, and initial_year
        gross_income = Money(100000)
        person1 = Person(
            self.initial_year, self.name, birth_date,
            retirement_date=retirement_date,
            gross_income=gross_income,
            spouse=None, tax_treatment=self.tax_treatment,
            allocation_strategy=self.allocation_strategy)
        self.assertEqual(person1.gross_income, gross_income)
        self.assertEqual(person1.gross_income_history,
                         {self.initial_year: gross_income})
        self.assertEqual(person1.tax_treatment, self.tax_treatment)
        self.assertEqual(person1.initial_year, self.initial_year)
        self.assertIsNone(person1.spouse)
        self.assertEqual(person1.allocation_strategy, self.allocation_strategy)
        self.assertEqual(person1.accounts, set())

        # Add a spouse and confirm that both Person objects are updated
        person2 = Person(
            self.initial_year, "Spouse", self.initial_year - 20,
            retirement_date=retirement_date,
            gross_income=Money(50000),
            spouse=person1, tax_treatment=self.tax_treatment)
        self.assertEqual(person1.spouse, person2)
        self.assertEqual(person2.spouse, person1)

        # Add an account and confirm that the Person passed as owner is
        # updated.
        account1 = Account(owner=person1)
        account2 = Account(owner=person1)
        self.assertEqual(person1.accounts, {account1, account2})
        self.assertEqual(person2.accounts, set())

    def test_age(self):
        """ Tests person.age """

        # Test output for person's 20th birthday:
        date = self.birth_date + relativedelta(years=20)
        self.assertEqual(self.owner.age(date), 20)
        self.assertIsInstance(self.owner.age(date), int)

        # Test output for day before person's 20th birthday:
        date = self.birth_date + relativedelta(years=20, days=-1)
        self.assertEqual(self.owner.age(date), 19)

        # Test output for day after person's 20th birthday:
        date = date + relativedelta(days=2)
        self.assertEqual(self.owner.age(date), 20)

        # NOTE: The following tests for negative ages, and should
        # probably be left undefined (i.e. implementation-specific)

        # Test output for day before person's birth
        date = self.birth_date - relativedelta(days=1)
        self.assertEqual(self.owner.age(date), -1)

        # Test output for one year before person's birth
        date = self.birth_date - relativedelta(years=1)
        self.assertEqual(self.owner.age(date), -1)

        # Test output for one year and a day before person's birth
        date = self.birth_date - relativedelta(years=1, days=1)
        self.assertEqual(self.owner.age(date), -2)

        # Repeat the above, but with strings
        date = str(self.birth_date + relativedelta(years=20))
        self.assertEqual(self.owner.age(date), 20)

        date = str(self.birth_date + relativedelta(years=20) -
                   relativedelta(days=1))
        self.assertEqual(self.owner.age(date), 19)

        date = str(self.birth_date + relativedelta(years=20, day=1))
        self.assertEqual(self.owner.age(date), 20)

        date = str(self.birth_date - relativedelta(days=1))
        self.assertEqual(self.owner.age(date), -1)

        # Finally, test ints as input
        date = self.birth_date.year + 20
        self.assertEqual(self.owner.age(date), 20)

        date = self.birth_date.year - 1
        self.assertEqual(self.owner.age(date), -1)

    def test_retirement_age(self):
        """ Tests person.retirement_age """

        # Test that the retirement age for stock person is accurate
        delta = relativedelta(self.owner.retirement_date,
                              self.owner.birth_date)
        self.assertEqual(self.owner.retirement_age, delta.years)
        self.assertIsInstance(self.owner.retirement_age, int)

        # Test retiring on 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65)
        person = Person(
            self.initial_year, self.name, self.birth_date,
            retirement_date=retirement_date)
        self.assertEqual(person.retirement_age, 65)

        # Test retiring on day after 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65, day=1)
        person = Person(
            self.initial_year, self.name, self.birth_date,
            retirement_date=retirement_date)
        self.assertEqual(person.retirement_age, 65)

        # Test retiring on day before 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65) - \
            relativedelta(days=1)
        person = Person(
            self.initial_year, self.name, self.birth_date,
            retirement_date=retirement_date)
        self.assertEqual(person.retirement_age, 64)

        # Test person with no known retirement date
        # NOTE: This is not currently implemented
        # person = Person(self.name, self.birth_date)
        # self.assertIsNone(person.retirement_age)

    def test_next(self):
        """ Test next_year to confirm that properties are advanced. """
        initial_year = 2017
        gross_income = 100
        tax = Tax(
            {initial_year: {0: 0, 200: 0.5, 1000: 0.75}},
            inflation_adjust={2017: 1, 2018: 1, 2019: 1, 2020: 1},
            personal_deduction={2017: 0})
        person = Person(
            initial_year, 'Name', 2000,
            raise_rate=2.0,
            retirement_date=self.retirement_date,
            gross_income=gross_income,
            tax_treatment=tax)
        self.assertEqual(person.gross_income, gross_income)
        self.assertEqual(person.net_income, Money(100))
        self.assertEqual(person.this_year, initial_year)
        person.next_year()  # 200% raise - gross income is now $300
        self.assertEqual(person.gross_income, Money(300))
        self.assertEqual(person.net_income, Money(250))
        self.assertEqual(person.this_year, initial_year + 1)

    def test_taxable_income(self):
        initial_year = 2017
        gross_income = 100
        tax = Tax({initial_year: {0: 0, 200: 0.5, 1000: 0.75}},
                  {2017: 1, 2018: 1, 2019: 1, 2020: 1}, {2017: 0})
        person = Person(
            initial_year, 'Name', 2000,
            retirement_date=self.retirement_date,
            gross_income=gross_income, tax_treatment=tax)
        self.assertEqual(person.taxable_income, gross_income)

    def test_taxwithheld(self):
        initial_year = 2017
        gross_income = 300
        tax = Tax(
            {initial_year: {0: 0, 200: 0.5, 1000: 0.75}},
            inflation_adjust={2017: 1, 2018: 1, 2019: 1, 2020: 1},
            personal_deduction={2017: 0})
        person = Person(
            self.initial_year, 'Name', 2000,
            retirement_date=self.retirement_date,
            gross_income=gross_income, tax_treatment=tax)
        self.assertEqual(person.tax_withheld, Money(50))

    def test_tax_credit(self):
        initial_year = 2017
        gross_income = 300
        tax = Tax({initial_year: {0: 0, 200: 0.5, 1000: 0.75}},
                  {2017: 1, 2018: 1, 2019: 1, 2020: 1}, {2017: 0})
        person = Person(
            self.initial_year, 'Name', 2000,
            retirement_date=self.retirement_date, gross_income=gross_income,
            tax_treatment=tax)
        self.assertEqual(person.tax_credit, Money(0))

    def test_tax_deduction(self):
        initial_year = 2017
        gross_income = 300
        tax = Tax({initial_year: {0: 0, 200: 0.5, 1000: 0.75}},
                  {2017: 1, 2018: 1, 2019: 1, 2020: 1}, {2017: 0})
        person = Person(
            self.initial_year, 'Name', 2000,
            retirement_date=self.retirement_date, gross_income=gross_income,
            tax_treatment=tax)
        self.assertEqual(person.tax_deduction, Money(0))

    def test_inputs(self):
        initial_year = 2017
        gross_income = 500
        inputs = {'gross_income': {
            initial_year: Money(1000), initial_year+2: Money(0)
            }
        }
        person = Person(
            initial_year, 'Name', 2000, retirement_date=2065,
            gross_income=gross_income, raise_rate=1, inputs=inputs)
        # We've gross income for the first and third years; the second
        # year should be set programmatically based on a 100% raise.
        self.assertEqual(person.gross_income, Money(1000))
        person.next_year()
        self.assertEqual(person.gross_income, Money(2000))
        person.next_year()
        self.assertEqual(person.gross_income, Money(0))


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
        scenario = Scenario(
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
            adjust_for_retirement_plan=False,
            scenario=scenario)
        cls.owner = Person(
            cls.initial_year, "test", 2000,
            raise_rate={year: 1 for year in range(2000, 2066)},
            retirement_date=2065,
            allocation_strategy=cls.allocation_strategy)

    def test_init(self, *args, **kwargs):
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
        self.assertTrue(type_check(account.balance_history, {int: Money}))
        self.assertIsInstance(account.balance, Money)
        self.assertTrue(type_check(account.rate_history, {int: Decimal}))
        self.assertIsInstance(account.rate, Decimal)
        self.assertTrue(type_check(account.transactions_history,
                                   {int: {Decimal: Money}}))
        self.assertTrue(type_check(account.transactions, {Decimal: Money}))
        self.assertIsInstance(account.nper, int)
        self.assertIsInstance(account.initial_year, int)

        # Basic test: Only balance and rate provided.
        account = self.AccountType(
            self.owner, *args, balance=balance, rate=0, **kwargs)
        self.assertEqual(account.balance_history, {
            self.initial_year: balance
            })
        self.assertEqual(account.rate_history, {self.initial_year: 0})
        self.assertEqual(account.transactions_history, {
            self.initial_year: {}
            })
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, 0)
        self.assertEqual(account.transactions, {})
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, self.initial_year)

        # Try again, but this time don't set rate explicitly; instead
        # use default behaviour and infer its rate from its owner's
        # asset allocation (which is 50% stocks, 50% bonds, with 75%
        # return overall)
        account = self.AccountType(
            self.owner, *args, balance=balance, **kwargs)
        self.assertEqual(account.balance_history, {
            self.initial_year: balance
            })
        self.assertEqual(account.transactions_history, {
            self.initial_year: {}
            })
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, Decimal(0.75))
        self.assertEqual(account.rate_history,
                         {self.initial_year: Decimal(0.75)})
        self.assertEqual(account.transactions, {})
        self.assertEqual(account.nper, 1)
        self.assertEqual(account.initial_year, self.initial_year)
        self.assertEqual(account.rate_function,
                         account.rate_from_asset_allocation)

        # Test with (Decimal-convertible) strings as input
        balance = "0"
        rate = "1.0"
        transactions = {'start': "1", 'end': "-1"}
        nper = 'A'
        initial_year = self.initial_year
        account = self.AccountType(
            self.owner, *args,
            balance=balance, rate=rate, transactions=transactions, nper=nper,
            **kwargs)
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

        # Test 'when' values inside and outside of the range [0,1]
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
            if account.balance == Money("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                balance=balance, rate="invalid input", **kwargs)
            if account.rate == Decimal("NaN"):
                raise decimal.InvalidOperation()

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
        self.assertAlmostEqual(account.balance, Money((1+1/12) ** 12), 3)

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
        next_val = Money((1 + 1/12) ** (12) + 2 * (1 + 1/12) ** (12 * 0.5))
        account.next_year()
        self.assertAlmostEqual(account.balance, next_val, 5)

    def test_add_transaction(self, *args, **kwargs):
        """ Tests add_transaction. """
        # We need to make sure that initial_year is in the same range
        # as inflation_adjustments, otherwise init will fail:
        initial_year = self.initial_year

        # Start with an empty account and add a transaction.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.transactions_history, {
            initial_year: {}
            })
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
            initial_year: {0: Money(1), 1: Money(2)}
            })
        self.assertEqual(account.inflows, Money(3))
        self.assertEqual(account.outflows, 0)

        # Try adding multiple transactions at the same time.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(1), 0)
        self.assertEqual(account.transactions_history, {
            initial_year: {0: Money(2)}
            })
        self.assertEqual(account.inflows, Money(2))
        self.assertEqual(account.outflows, Money(0))

        # Try adding both inflows and outflows at different times.
        account = self.AccountType(
            self.owner, *args, **kwargs)
        account.add_transaction(Money(1), 'start')
        account.add_transaction(Money(-2), 'end')
        self.assertEqual(account.transactions_history, {
            initial_year: {0: Money(1), 1: Money(-2)}
            })
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
            initial_year: {0: Money(-1)}
            })
        self.assertEqual(account.inflows, 0)
        self.assertEqual(account.outflows, Money(-1))

        # TODO: Test add_transactions again after performing next_year
        # (do this recursively?)

    def test_max_outflow(self, *args, **kwargs):

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
        # This method should always return Money('Infinity')
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        self.assertEqual(account.max_inflow(), Money('Infinity'))

        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        self.assertEqual(account.max_inflow(), Money('Infinity'))

    def test_min_outflow(self, *args, **kwargs):
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        self.assertEqual(account.min_outflow(), Money(0))

        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        self.assertEqual(account.min_outflow(), Money(0))

    def test_min_inflow(self, *args, **kwargs):
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(0))

        account = self.AccountType(
            self.owner, *args, balance=-100, **kwargs)
        self.assertEqual(account.min_inflow(), Money(0))

    def test_taxable_income(self, *args, **kwargs):
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


class TestDebtMethods(unittest.TestCase):
    """ Test Debt. """

    @classmethod
    def setUpClass(cls):
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

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

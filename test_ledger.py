''' Unit tests for `People` and `Account` classes. '''

import unittest
from datetime import datetime
from dateutil.parser import parse
from dateutil.relativedelta import relativedelta
import decimal
from decimal import Decimal
from moneyed import Money
from settings import Settings
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

        # Test output for day before person's birth
        date = self.birth_date - relativedelta(days=1)
        with self.assertRaises(ValueError):
            self.person.age(date)

        # Repeat the above, but with strings
        date = str(self.birth_date + relativedelta(years=20))
        self.assertEqual(self.person.age(date), 20)

        date = str(self.birth_date + relativedelta(years=20) -
                   relativedelta(days=1))
        self.assertEqual(self.person.age(date), 19)

        date = str(self.birth_date + relativedelta(years=20, day=1))
        self.assertEqual(self.person.age(date), 20)

        date = str(self.birth_date - relativedelta(days=1))
        with self.assertRaises(ValueError):
            self.person.age(date)

        # Finally, test ints as input
        date = self.birth_date.year + 20
        self.assertEqual(self.person.age(date), 20)

        date = self.birth_date.year - 1
        with self.assertRaises(ValueError):
            self.person.age(date)

    @staticmethod
    def num_years(date1, date2):
        """ Returns the number of full years between date1 and date2.

        Helper method for test_retirement_age.

        Example:
            num_years(datetime(2000,1,1), datetime(2001,1,1)) = 1
            num_years(datetime(2000,1,2), datetime(2001,1,1)) = 0

        Returns:
            An int. The number of full years between date1 and date2.
                Hours/seconds/etc. are ignored.
        """
        # Return the difference in years, unless date2's date is earlier
        # in the calendar than date1's date (disregarding the year)
        year_diff = date2.year - date1.year
        month_diff = date2.month - date1.month
        day_diff = date2.day - date1.day

        if month_diff == 0:   # Same month in date2...
            if day_diff < 0:  # ... but an earlier day
                year_diff -= 1
        elif month_diff < 0:  # Earlier month in date2
            year_diff -= 1

        return year_diff

    def test_retirement_age(self):
        """ Tests person.retirement_age """

        # Test that the retirement age for stock person is accurate
        delta = relativedelta(self.person.retirement_date,
                              self.person.birth_date)
        self.assertEqual(self.person.retirement_age(), delta.years)
        self.assertIsInstance(self.person.retirement_age(), int)

        # Test retiring on 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65)
        person = Person(self.name, self.birth_date, retirement_date)
        self.assertEqual(self.person.retirement_age(), 65)

        # Test retiring on day after 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65, day=1)
        person = Person(self.name, self.birth_date, retirement_date)
        self.assertEqual(self.person.retirement_age(), 65)

        # Test retiring on day before 65th birthday
        retirement_date = self.birth_date + relativedelta(years=65) - \
            relativedelta(days=1)
        person = Person(self.name, self.birth_date, retirement_date)
        self.assertEqual(self.person.retirement_age(), 64)

        # Test person with no known retirement date
        self.person = Person(self.name, self.birth_date)
        self.assertIsNone(self.person.retirement_age())


class TestAccountMethods(unittest.TestCase):
    """ A test suite for the `Account` class """

    def test_init(self, AccountType=Account):
        """ Tests Account.__init__ """

        # Basic test: All correct values, check for equality and type
        balance = Money(0)
        rate = 1.0
        inflow = Money(3.0)
        outflow = Money(2.0)
        inflow_inclusion = 0.75
        outflow_inclusion = 0.25
        account = AccountType(balance, rate, inflow, outflow,
                              inflow_inclusion, outflow_inclusion)
        self.assertEqual(account.balance, balance)
        self.assertEqual(account.rate, rate)
        self.assertEqual(account.inflow, inflow)
        self.assertEqual(account.outflow, outflow)
        self.assertEqual(account.inflow_inclusion, inflow_inclusion)
        self.assertEqual(account.outflow_inclusion, outflow_inclusion)
        self.assertIsInstance(account.balance, Money)
        self.assertIsInstance(account.rate, Decimal)
        self.assertIsInstance(account.inflow, Money)
        self.assertIsInstance(account.outflow, Money)
        self.assertIsInstance(account.inflow_inclusion, Decimal)
        self.assertIsInstance(account.outflow_inclusion, Decimal)

        # Basic test: Only balance provided.
        account = AccountType(balance)
        self.assertEqual(account.balance, balance)
        self.assertIsNone(account.rate)
        self.assertIsNone(account.inflow)
        self.assertIsNone(account.outflow)
        self.assertIsNone(account.inflow_inclusion)
        self.assertIsNone(account.outflow_inclusion)

        # Test with (Decimal-convertible) strings as input
        balance = "0"
        rate = "1"
        inflow = "3"
        outflow = "2"
        inflow_inclusion = "0.75"
        outflow_inclusion = "0.25"
        account = AccountType(balance, rate, inflow, outflow,
                              inflow_inclusion, outflow_inclusion)
        self.assertEqual(account.balance, Money(0))
        self.assertEqual(account.rate, Decimal(1))
        self.assertEqual(account.inflow, Money(3))
        self.assertEqual(account.outflow, Money(2))
        self.assertEqual(account.inflow_inclusion, Decimal(0.75))
        self.assertEqual(account.outflow_inclusion, Decimal(0.25))
        self.assertIsInstance(account.balance, Money)
        self.assertIsInstance(account.rate, Decimal)
        self.assertIsInstance(account.inflow, Money)
        self.assertIsInstance(account.outflow, Money)
        self.assertIsInstance(account.inflow_inclusion, Decimal)
        self.assertIsInstance(account.outflow_inclusion, Decimal)

        # Test *_inclusion inside and outside of the range [0,1]
        account = AccountType(balance, inflow_inclusion=0)
        self.assertEqual(account.inflow_inclusion, Decimal(0))
        account = AccountType(balance, inflow_inclusion=0.5)
        self.assertEqual(account.inflow_inclusion, Decimal(0.5))
        account = AccountType(balance, inflow_inclusion=1)
        self.assertEqual(account.inflow_inclusion, Decimal(1))
        with self.assertRaises(ValueError):
            account = AccountType(balance, inflow_inclusion=-1)
        with self.assertRaises(ValueError):
            account = AccountType(balance, inflow_inclusion=2)

        account = AccountType(balance, outflow_inclusion=0)
        self.assertEqual(account.outflow_inclusion, Decimal(0))
        account = AccountType(balance, outflow_inclusion=0.5)
        self.assertEqual(account.outflow_inclusion, Decimal(0.5))
        account = AccountType(balance, outflow_inclusion=1)
        self.assertEqual(account.outflow_inclusion, Decimal(1))
        with self.assertRaises(ValueError):
            account = AccountType(balance, outflow_inclusion=-1)
        with self.assertRaises(ValueError):
            account = AccountType(balance, outflow_inclusion=2)

        # BasicContext causes most errors to raise exceptions
        # In particular, invalid input will raise InvalidOperation
        decimal.setcontext(decimal.BasicContext)

        # Test with values not convertible to Decimal
        with self.assertRaises(decimal.InvalidOperation):
            account = AccountType(balance="invalid input")
            if account.balance == Money("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = AccountType(balance, rate="invalid input")
            if account.rate == Decimal("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = AccountType(balance, inflow="invalid input")
            if account.inflow == Money("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = AccountType(balance, outflow="invalid input")
            if account.outflow == Money("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = AccountType(balance, inflow_inclusion="invalid input")
            if account.inflow_inclusion == Decimal("NaN"):
                raise decimal.InvalidOperation()

        with self.assertRaises(decimal.InvalidOperation):
            account = AccountType(balance, outflow_inclusion="invalid input")
            if account.outflow_inclusion == Decimal("NaN"):
                raise decimal.InvalidOperation()

        # Recurse onto all subclasses of AccountType
        # (Recall that, at first iteration, AccountType=Account)
        for SubType in AccountType.__subclasses__():
            self.test_init(SubType)

if __name__ == '__main__':
    
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

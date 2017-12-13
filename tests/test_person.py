""" Unit tests for `People` and `Account` classes. """

import unittest
import decimal
from decimal import Decimal
from datetime import datetime
from dateutil.relativedelta import relativedelta
from forecaster import Person, Account, Tax, Money


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
        self.spouse = Person(
            initial_year=self.initial_year,
            name="Spouse",
            birth_date=1998,
            retirement_date=2063,
            gross_income=Money(50000),
            raise_rate=self.raise_rate,
            spouse=None,
            tax_treatment=self.tax_treatment)
        self.owner = Person(
            initial_year=self.initial_year,
            name=self.name,
            birth_date=self.birth_date,
            retirement_date=self.retirement_date,
            gross_income=self.gross_income,
            raise_rate=self.raise_rate,
            spouse=self.spouse,
            tax_treatment=self.tax_treatment)

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
        # tax_treatment, and initial_year
        gross_income = Money(100000)
        person1 = Person(
            self.initial_year, self.name, birth_date,
            retirement_date=retirement_date,
            gross_income=gross_income,
            spouse=None, tax_treatment=self.tax_treatment)
        self.assertEqual(person1.gross_income, gross_income)
        self.assertEqual(
            # pylint: disable=no-member
            # Pylint is confused by members added by metaclass
            person1.gross_income_history,
            {self.initial_year: gross_income}
        )
        self.assertEqual(person1.tax_treatment, self.tax_treatment)
        self.assertEqual(person1.initial_year, self.initial_year)
        self.assertIsNone(person1.spouse)
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
        inputs = {
            'gross_income': {
                initial_year: Money(1000), initial_year + 2: Money(0)
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


if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

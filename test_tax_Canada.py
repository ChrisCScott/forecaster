""" Tests for Canada-specific Tax subclasses. """

import unittest
from decimal import Decimal
from tax_Canada import *
from ledger import Person
from ledger_Canada import *
from constants_Canada import ConstantsCanada as Constants
from test_helper import *


class TestCanadianResidentTax(unittest.TestCase):
    """ Tests CanadianResidentTax """

    def setUp(self):
        self.initial_year = 2000
        # Build 100 years of inflation adjustments with steadily growing
        # adjustment factors. First, pick a nice number (ideally a power
        # of 2 to avoid float precision issues); inflation_adjustment
        # will grow by adding the inverse (1/n) of this number annually
        growth_factor = 32
        year_range = range(self.initial_year, self.initial_year + 100)
        self.inflation_adjustments = {
            year: 1 + (year - self.initial_year) / growth_factor
            for year in year_range
        }
        # For convenience, store the year where inflation has doubled
        # the nominal value of money
        self.double_year = self.initial_year + growth_factor
        # Build some brackets with nice round numbers:
        self.tax_brackets = {
            self.initial_year: {
                Money(0): Decimal('0.1'),
                Money('100'): Decimal('0.2'),
                Money('10000'): Decimal('0.3')
            }
        }
        # For convenience in testing, build an accum dict that
        # corresponds to the tax brackets above.
        self.accum = {
            self.initial_year: {
                Money(0): Money('0'),
                Money('100'): Money('10'),
                Money('10000'): Money('1990')
            }
        }
        self.personal_deduction = {
            self.initial_year: Money('100')
        }
        self.credit_rate = {
            self.initial_year: Decimal('0.1')
        }

    def test_init(self):
        """ Test TaxCanada.__init__ """
        tax = TaxCanada(self.inflation_adjustments, province='BC')
        # Test federal tax:
        # There's some type-conversion going on, so test the Decimal-
        # valued `amount` of the Tax's tax bracket's keys against the
        # Decimal key object of the Constants tax brackets.
        self.assertEqual(
            tax.federal_tax._tax_brackets,
            {year: {
                Money(bracket): value
                for bracket, value in
                Constants.TaxBrackets['Federal'][year].items()
            } for year in Constants.TaxBrackets['Federal']}
        )
        self.assertTrue(callable(tax.federal_tax.inflation_adjust))
        self.assertEqual(tax.federal_tax._personal_deduction,
                         Constants.TaxBasicPersonalDeduction['Federal'])
        self.assertEqual(tax.federal_tax._credit_rate,
                         Constants.TaxCreditRate['Federal'])
        # Test provincial tax:
        self.assertEqual(
            tax.provincial_tax._tax_brackets,
            {year: {
                Money(bracket): value
                for bracket, value in
                Constants.TaxBrackets['BC'][year].items()
            } for year in Constants.TaxBrackets['BC']}
        )
        self.assertTrue(callable(tax.provincial_tax.inflation_adjust))
        self.assertEqual(tax.provincial_tax._personal_deduction,
                         Constants.TaxBasicPersonalDeduction['BC'])
        self.assertEqual(tax.provincial_tax._credit_rate,
                         Constants.TaxCreditRate['BC'])

        # Omit optional argument:
        tax = TaxCanada(self.inflation_adjustments)
        self.assertEqual(tax.province, 'BC')
        self.assertEqual(
            tax.provincial_tax._tax_brackets,
            {year: {
                Money(bracket): value
                for bracket, value in
                Constants.TaxBrackets['BC'][year].items()
            } for year in Constants.TaxBrackets['BC']}
        )
        self.assertTrue(callable(tax.provincial_tax.inflation_adjust))
        self.assertEqual(tax.provincial_tax._personal_deduction,
                         Constants.TaxBasicPersonalDeduction['BC'])
        self.assertEqual(tax.provincial_tax._credit_rate,
                         Constants.TaxCreditRate['BC'])

    def test_call(self):
        """ Test TaxCanada.__call__ """
        tax = TaxCanada(self.inflation_adjustments)
        # Test a call on Money:
        taxable_income = Money(100000)
        self.assertEqual(
            tax(taxable_income, self.initial_year),
            tax.federal_tax(taxable_income, self.initial_year) +
            tax.provincial_tax(taxable_income, self.initial_year)
        )

        # Test a call on one Person:
        person1 = Person(
            self.initial_year, "Tester 1", self.initial_year - 20,
            retirement_date=self.initial_year + 45, gross_income=100000)
        account1 = TaxableAccount(
            owner=person1,
            acb=0, balance=Money(1000000), rate=Decimal('0.05'),
            transactions={'start': -Money(1000000)}, nper=1)
        # NOTE: by using an RRSP here, a pension income tax credit will
        # be applied by TaxCanadaJurisdiction. Be aware of this if you
        # want to test this output against a generic Tax object with
        # Canadian brackets.
        account2 = RRSP(
            person1,
            inflation_adjust=self.inflation_adjustments,
            contribution_room=0,
            balance=Money(500000), rate=Decimal('0.05'),
            transactions={'start': -Money(500000)}, nper=1)
        self.assertEqual(
            tax(person1, self.initial_year),
            tax.federal_tax(person1, self.initial_year) +
            tax.provincial_tax(person1, self.initial_year)
        )

        # Should get the same result for a single-person set:
        self.assertEqual(
            tax({person1}, self.initial_year),
            tax(person1, self.initial_year)
        )

        # Finally, test tax treatment of multiple people:
        person2 = Person(
            self.initial_year, "Tester 2", self.initial_year - 18,
            retirement_date=self.initial_year + 47, gross_income=50000)
        account3 = TaxableAccount(
            owner=person2,
            acb=0, balance=Money(10000), rate=Decimal('0.05'),
            transactions={'start': -Money(10000)}, nper=1)
        # Make sure that we're getting the correct result for person2:
        self.assertEqual(
            tax(person2, self.initial_year),
            tax.federal_tax(person2, self.initial_year) +
            tax.provincial_tax(person2, self.initial_year)
        )
        # Now confirm that the Tax object works with both people.
        self.assertEqual(
            tax({person1, person2}, self.initial_year),
            tax.federal_tax({person1, person2}, self.initial_year) +
            tax.provincial_tax({person1, person2}, self.initial_year)
        )

if __name__ == '__main__':
    unittest.main()

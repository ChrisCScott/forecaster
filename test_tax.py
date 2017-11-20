''' Unit tests for `Tax` classes. '''

import unittest
import decimal
from decimal import Decimal
from tax import *
from ledger import *
# Include extra accounts to test handling of different tax* behaviour:
from ledger_Canada import *
from test_helper import *


class TestTax(unittest.TestCase):
    """ Tests the `Tax` class. """

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
        tax = Tax(
            self.tax_brackets,
            inflation_adjust=self.inflation_adjustments,
            personal_deduction=self.personal_deduction,
            credit_rate=self.credit_rate)
        self.assertEqual(tax._tax_brackets, self.tax_brackets)
        self.assertEqual(tax._accum, self.accum)
        self.assertTrue(callable(tax.inflation_adjust))
        self.assertEqual(tax._personal_deduction, self.personal_deduction)
        self.assertEqual(tax._credit_rate, self.credit_rate)

        # Omit optional arguments
        tax = Tax(
            self.tax_brackets,
            inflation_adjust=self.inflation_adjustments)
        self.assertEqual(tax._tax_brackets, self.tax_brackets)
        self.assertEqual(tax._accum, self.accum)
        self.assertTrue(callable(tax.inflation_adjust))
        self.assertEqual(tax._personal_deduction, {
            self.initial_year: Decimal(0)
        })
        self.assertEqual(tax._credit_rate, {
            self.initial_year: Decimal(1)
        })

        # Test type-checking/conversion.
        # Use an all-str dict and confirm that the output is correctly
        # typed
        tax_brackets = {
            str(year): {
                str(bracket.amount): str(self.tax_brackets[year][bracket])
                for bracket in self.tax_brackets[year]
            } for year in self.tax_brackets
        }
        inflation_adjustments = {
            str(year): str(self.inflation_adjustments[year])
            for year in self.inflation_adjustments
        }
        tax = Tax(tax_brackets, inflation_adjust=inflation_adjustments)
        self.assertEqual(tax._tax_brackets, self.tax_brackets)
        self.assertTrue(callable(tax.inflation_adjust))
        # Check types on the outputs
        self.assertTrue(type_check(tax._tax_brackets, {int: {Money: Decimal}}))

    def test_call(self):
        # Set up variables, including some convenience variables.
        tax = Tax(
            self.tax_brackets,
            inflation_adjust=self.inflation_adjustments,
            personal_deduction=self.personal_deduction,
            credit_rate=self.credit_rate)
        year = self.initial_year
        deduction = self.personal_deduction[year]
        # Type-convert
        brackets = sorted({Money(key): self.tax_brackets[year][key]
                           for key in self.tax_brackets[year].keys()})

        # First batch: Money first arg (as opposed to iterable arg)

        # Easiest case: $0 should return $0 in tax owing
        self.assertEqual(tax(0, year), Money(0))
        # If this is less than the person deduction, should return $0
        self.assertEqual(tax(deduction / 2, year), Money(0))
        # Should also return $0 for the full personal deduction.
        self.assertEqual(tax(deduction, year), Money(0))

        # Find a value that's mid-way into the lowest marginal tax rate.
        # (NOTE: brackets[0] is $0; we need something between
        # brackets[0] and brackets[1])
        val = brackets[1] / 2 + deduction
        self.assertEqual(tax(val, year),
                         (val - deduction) *
                         self.tax_brackets[year][brackets[0]])
        # Try again for a value that's at the limit of the lowest tax
        # bracket (NOTE: brackets are inclusive, so brackets[1] is
        # entirely taxed at the rate associated with brackets[0])
        val = brackets[1] + deduction
        self.assertEqual(tax(val, year),
                         self.accum[year][brackets[1]])

        # Find a value that's mid-way into the next (second) bracket.
        # Assuming a person deduction of $100 and tax rates bounded at
        # $0, $100 and $10000 with 10%, 20%, and 30% rates, this gives:
        #   Tax on first $100:  $0
        #   Tax on next $100:   $10
        #   Tax on remaining:   20% of remaining
        # For a $5150 amount, this works out to tax of $1000.
        val = (brackets[1] + brackets[2]) / 2 + deduction
        self.assertEqual(tax(val, year),
                         self.accum[year][brackets[1]] +
                         ((brackets[1] + brackets[2]) / 2 - brackets[1]) *
                         self.tax_brackets[year][brackets[1]])
        # Try again for a value that's at the limit of the lowest tax
        # bracket (NOTE: brackets are inclusive, so brackets[1] is
        # entirely taxed at the rate associated with brackets[0])
        val = brackets[2] + deduction
        self.assertEqual(tax(val, year),
                         self.accum[year][brackets[1]] +
                         (brackets[2] - brackets[1]) *
                         self.tax_brackets[year][brackets[1]])

        # Find a value that's somewhere in the highest (unbounded) bracket.
        bracket = max(brackets)
        val = bracket * 2 + deduction
        self.assertEqual(tax(val, year),
                         self.accum[year][bracket] +
                         bracket * self.tax_brackets[year][bracket])

        # Now move on to testing tax treatment of one person:
        person1 = Person("Tester 1", self.initial_year - 20,
                         retirement_date=self.initial_year + 45,
                         gross_income=100000, initial_year=self.initial_year)
        # Build three accounts: Two for one person and one for the other
        # The entire balance of each account is withdrawn immediately.
        # Half of the taxable account withdrawal is taxable and 100% of
        # the RRSP withdrawal is taxable.
        balance1 = Money(1000000)
        account1 = TaxableAccount(
            acb=0, balance=balance1, rate=Decimal('0.05'),
            transactions={'start': -balance1}, nper=1,
            initial_year=self.initial_year, owner=person1)
        balance2 = Money(500000)
        account2 = RRSP(
            person1, inflation_adjust=self.inflation_adjustments,
            contribution_room=0,
            balance=balance2, rate=Decimal('0.05'),
            transactions={'start': -balance2}, nper=1,
            initial_year=self.initial_year)
        # This is the result we would expect
        taxable_income1 = person1.gross_income + balance1 / 2 + balance2
        self.assertEqual(tax(person1, person1.initial_year),
                         tax(taxable_income1, person1.initial_year))

        # Finally, test tax treatment of multiple people:
        person2 = Person("Tester 2", self.initial_year - 18,
                         retirement_date=self.initial_year + 47,
                         gross_income=50000, initial_year=self.initial_year)
        balance3 = Money(10000)
        account3 = TaxableAccount(
            acb=0, balance=balance3, rate=Decimal('0.05'),
            transactions={'start': -balance3}, nper=1,
            initial_year=self.initial_year, owner=person2)
        taxable_income2 = person2.gross_income + balance3 / 2  # 50% taxable
        # Make sure that we're getting the correct result for person2:
        self.assertEqual(tax(person2, person2.initial_year),
                         tax(taxable_income2, person2.initial_year))

        # Now confirm that the Tax object works with multiple people.
        self.assertEqual(tax({person1, person2}, self.initial_year),
                         tax(taxable_income1, self.initial_year) +
                         tax(taxable_income2, self.initial_year))
        # Try also with a single-member set; should return the same as
        # it would if calling on the person directly.
        self.assertEqual(tax({person1}, person1.initial_year),
                         tax(person1, person1.initial_year))

        # Last thing: Test inflation-adjustment.
        # Start with a baseline result in initial_year. Then confirm
        # that the tax owing on twice that amount in double_year should
        # be exactly double the tax owing on the baseline result.
        # (Anything else suggests that something is not being inflation-
        # adjusted properly, e.g. a bracket or a deduction)
        double_tax = tax(taxable_income1 * 2, self.double_year)
        single_tax = tax(taxable_income1, self.initial_year)
        self.assertEqual(double_tax, single_tax * 2)

if __name__ == '__main__':
    unittest.main()

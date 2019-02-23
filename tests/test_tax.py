''' Unit tests for `Tax` classes. '''

import unittest
from decimal import Decimal
from forecaster import Tax, Money, Person
# Include extra accounts to test handling of different tax* behaviour:
from forecaster.canada import RRSP, TaxableAccount, TFSA
from tests.test_helper import type_check


class TestTax(unittest.TestCase):
    """ Tests the `Tax` class. """

    # We save a number of attributes for convenience in testing later
    # on. We could refactor, but it would complicate the tests, which
    # would be worse.
    # pylint: disable=too-many-instance-attributes

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
        # For convenience, build a sorted, type-converted array of
        # each of the tax bracket thresholds:
        self.brackets = sorted({
            Money(key): self.tax_brackets[self.initial_year][key]
            for key in self.tax_brackets[self.initial_year].keys()})
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

        self.tax = Tax(
            self.tax_brackets,
            inflation_adjust=self.inflation_adjustments,
            personal_deduction=self.personal_deduction,
            credit_rate=self.credit_rate)

        # Set up a simple person with no account-derived taxable income
        self.person = Person(
            self.initial_year, "Tester", self.initial_year - 25,
            retirement_date=self.initial_year + 40, gross_income=0)

        # Set up two people, spouses, on which to do more complex tests
        self.person1 = Person(
            self.initial_year, "Tester 1", self.initial_year - 20,
            retirement_date=self.initial_year + 45, gross_income=100000)
        self.person2 = Person(
            self.initial_year, "Tester 2", self.initial_year - 22,
            retirement_date=self.initial_year + 43, gross_income=50000)

        # Give the first person two accounts, one taxable and one
        # tax-deferred. Withdraw the entirety from the taxable account,
        # so that we don't need to worry about tax on unrealized growth:
        self.taxable_account1 = TaxableAccount(
            owner=self.person1,
            acb=0, balance=50000, rate=Decimal('0.05'), nper=1)
        self.taxable_account1.add_transaction(-50000, when='start')
        self.rrsp = RRSP(
            owner=self.person1,
            inflation_adjust=self.inflation_adjustments,
            contribution_room=0, balance=10000, rate=Decimal('0.05'), nper=1)
        # Employment income is fully taxable, and only half of capital
        # gains (the income from the taxable account) is taxable:
        self.person1_taxable_income = Money(
            self.person1.gross_income + self.taxable_account1.balance / 2)

        # Give the second person two accounts, one taxable and one
        # non-taxable. Withdraw the entirety from the taxable account,
        # so that we don't need to worry about tax on unrealized growth,
        # and withdraw a bit from the non-taxable account (which should
        # have no effect on taxable income):
        self.taxable_account2 = TaxableAccount(
            owner=self.person2,
            acb=0, balance=20000, rate=Decimal('0.05'), nper=1)
        self.taxable_account2.add_transaction(-20000, when='start')
        self.tfsa = TFSA(
            owner=self.person2,
            balance=50000, rate='0.05', nper=1)
        self.tfsa.add_transaction(-20000, when='start')
        # Employment income is fully taxable, and only half of capital
        # gains (the income from the taxable account) is taxable:
        self.person2_taxable_income = Money(
            self.person2.gross_income + self.taxable_account2.balance / 2)

    def test_init_optional(self):
        """ Test Tax.__init__ with all arguments, including optional. """
        tax = Tax(
            self.tax_brackets,
            inflation_adjust=self.inflation_adjustments,
            personal_deduction=self.personal_deduction,
            credit_rate=self.credit_rate)
        for year in self.tax_brackets:
            self.assertEqual(tax.tax_brackets(year), self.tax_brackets[year])
            self.assertEqual(tax.accum(year), self.accum[year])
            self.assertEqual(
                tax.personal_deduction(year), self.personal_deduction[year])
            self.assertEqual(tax.credit_rate(year), self.credit_rate[year])
        self.assertTrue(callable(tax.inflation_adjust))

    def test_init_basic(self):
        """ Test Tax.__init__ with only mandatory arguments. """
        tax = Tax(
            self.tax_brackets,
            inflation_adjust=self.inflation_adjustments)
        for year in self.tax_brackets:
            self.assertEqual(tax.tax_brackets(year), self.tax_brackets[year])
            self.assertEqual(tax.accum(year), self.accum[year])
        self.assertTrue(callable(tax.inflation_adjust))
        self.assertEqual(tax.personal_deduction(self.initial_year), Decimal(0))
        self.assertEqual(tax.credit_rate(self.initial_year), Decimal(1))

    def test_init_type_conv_str(self):
        """ Tests Tax.__init__ with args requiring type-conversion. """
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
        for year in self.tax_brackets:
            self.assertEqual(tax.tax_brackets(year), self.tax_brackets[year])
            self.assertTrue(type_check(
                tax.tax_brackets(year), {Money: Decimal}))
        self.assertTrue(callable(tax.inflation_adjust))

    def test_income_0_money(self):
        """ Call Test on $0 income. """
        # $0 should return $0 in tax owing. This is the easiest test.
        income = Money(0)
        self.assertEqual(self.tax(income, self.initial_year), Money(0))

    def test_income_0_person(self):
        """ Test tax on a person with $0 income. """
        # $0 should return $0 in tax owing. This is the easiest test.
        self.person.gross_income = Money(0)
        self.assertEqual(self.tax(self.person, self.initial_year), Money(0))

    def test_income_under_deduction(self):
        """ Test tax on person with income under personal deduction. """
        self.person.gross_income = (
            self.personal_deduction[self.initial_year] / 2
        )
        # Should return $0
        self.assertEqual(self.tax(self.person, self.initial_year), Money(0))

    def test_income_at_deduction(self):
        """ Call Test on income equal to the personal deduction. """
        self.person.gross_income = self.personal_deduction[self.initial_year]
        # Should return $0
        self.assertEqual(self.tax(self.person, self.initial_year), Money(0))

    def test_income_in_bracket_1_money(self):
        """ Call Test on income mid-way into the lowest tax bracket. """
        # NOTE: brackets[0] is $0; we need something between brackets[0]
        # and brackets[1])
        income = self.brackets[1] / 2
        self.assertEqual(
            self.tax(income, self.initial_year),
            income * self.tax_brackets[self.initial_year][self.brackets[0]])

    def test_income_in_bracket_1_person(self):
        """ Call Test on income mid-way into the lowest tax bracket. """
        # NOTE: brackets[0] is $0; we need something between brackets[0]
        # and brackets[1])
        self.person.gross_income = (
            self.brackets[1] / 2
            + self.personal_deduction[self.initial_year])
        self.assertEqual(
            self.tax(self.person, self.initial_year),
            (
                self.person.gross_income
                - self.personal_deduction[self.initial_year]
            ) * self.tax_brackets[self.initial_year][self.brackets[0]])

    def test_income_at_bracket_1_money(self):
        """ Call Test on income equal to the lowest tax bracket. """
        # Try a value that's at the limit of the lowest tax
        # bracket (NOTE: brackets are inclusive, so brackets[1] is
        # entirely taxed at the rate associated with brackets[0])
        income = self.brackets[1]
        self.assertEqual(
            self.tax(income, self.initial_year),
            self.accum[self.initial_year][self.brackets[1]])

    def test_income_at_bracket_1_person(self):
        """ Call Test on income equal to the lowest tax bracket. """
        # Try a value that's at the limit of the lowest tax
        # bracket (NOTE: brackets are inclusive, so brackets[1] is
        # entirely taxed at the rate associated with brackets[0])
        self.person.gross_income = (
            self.brackets[1] + self.personal_deduction[self.initial_year]
        )
        self.assertEqual(
            self.tax(self.person, self.initial_year),
            self.accum[self.initial_year][self.brackets[1]])

    def test_income_in_bracket_2_money(self):
        """ Call Test on income mid-way into the second tax bracket. """
        # Find a value that's mid-way into the next (second) bracket.
        # Assuming a person deduction of $100 and tax rates bounded at
        # $0, $100 and $10000 with 10%, 20%, and 30% rates, this gives:
        #   Tax on first $100:  $0
        #   Tax on next $100:   $10
        #   Tax on remaining:   20% of remaining
        # For a $5150 amount, this works out to tax of $1000.
        income = (self.brackets[1] + self.brackets[2]) / 2
        self.assertEqual(
            self.tax(income, self.initial_year),
            self.accum[self.initial_year][self.brackets[1]] +
            (
                (self.brackets[1] + self.brackets[2]) / 2
                - self.brackets[1])
            * self.tax_brackets[self.initial_year][self.brackets[1]])

    def test_income_in_bracket_2_person(self):
        """ Call Test on income mid-way into the second tax bracket. """
        # Find a value that's mid-way into the next (second) bracket.
        # Assuming a person deduction of $100 and tax rates bounded at
        # $0, $100 and $10000 with 10%, 20%, and 30% rates, this gives:
        #   Tax on first $100:  $0
        #   Tax on next $100:   $10
        #   Tax on remaining:   20% of remaining
        # For a $5150 amount, this works out to tax of $1000.
        self.person.gross_income = (
            (self.brackets[1] + self.brackets[2]) / 2
            + self.personal_deduction[self.initial_year])
        target = (
            self.accum[self.initial_year][self.brackets[1]]
            + (
                (self.brackets[1] + self.brackets[2]) / 2
                - self.brackets[1]
            ) * self.tax_brackets[self.initial_year][self.brackets[1]]
        )
        self.assertEqual(
            self.tax(self.person, self.initial_year),
            target
        )

    def test_income_at_bracket_2_money(self):
        """ Call Test on income equal to the second tax bracket. """
        # Try again for a value that's at the limit of the second tax
        # bracket (NOTE: brackets are inclusive, so brackets[2] is
        # entirely taxed at the rate associated with brackets[1])
        income = self.brackets[2]
        self.assertEqual(
            self.tax(income, self.initial_year),
            self.accum[self.initial_year][self.brackets[1]]
            + (self.brackets[2] - self.brackets[1])
            * self.tax_brackets[self.initial_year][self.brackets[1]])

    def test_income_at_bracket_2_person(self):
        """ Call Test on income equal to the second tax bracket. """
        # Try again for a value that's at the limit of the second tax
        # bracket (NOTE: brackets are inclusive, so brackets[2] is
        # entirely taxed at the rate associated with brackets[1])
        self.person.gross_income = (
            self.brackets[2] + self.personal_deduction[self.initial_year]
        )
        self.assertEqual(
            self.tax(self.person, self.initial_year),
            self.accum[self.initial_year][self.brackets[1]]
            + (self.brackets[2] - self.brackets[1])
            * self.tax_brackets[self.initial_year][self.brackets[1]])

    def test_income_in_bracket_3_money(self):
        """ Call Test on income in the highest tax bracket. """
        # Find a value that's somewhere in the highest (unbounded) bracket.
        bracket = max(self.brackets)
        income = bracket * 2
        self.assertEqual(
            self.tax(income, self.initial_year),
            self.accum[self.initial_year][bracket] +
            bracket * self.tax_brackets[self.initial_year][bracket])

    def test_income_in_bracket_3_person(self):
        """ Call Test on income in the highest tax bracket. """
        # Find a value that's somewhere in the highest (unbounded) bracket.
        bracket = max(self.brackets)
        self.person.gross_income = (
            bracket * 2 + self.personal_deduction[self.initial_year]
        )
        self.assertEqual(
            self.tax(self.person, self.initial_year),
            self.accum[self.initial_year][bracket] +
            bracket * self.tax_brackets[self.initial_year][bracket])

    def test_taxpayer_single(self):
        """ Call test on a single taxpayer. """
        # The tax paid on the person's income should be the same as if
        # we calculated the tax directly on the money itself (after
        # accounting for the personal deduction amount)
        self.assertEqual(
            self.tax(self.person1, self.initial_year),
            self.tax(
                self.person1_taxable_income
                - self.personal_deduction[self.initial_year],
                self.initial_year))
        # We should get a similar result on the other person:
        self.assertEqual(
            self.tax(self.person2, self.initial_year),
            self.tax(
                self.person2_taxable_income
                - self.personal_deduction[self.initial_year],
                self.initial_year))

    def test_taxpayer_single_set(self):
        """ Call test on a set with a single taxpayer member. """
        # Try with a single-member set; should return the same as
        # it would if calling on the person directly.
        self.assertEqual(
            self.tax({self.person1}, self.initial_year),
            self.tax(self.person1, self.initial_year))

    def test_taxpayer_set(self):
        """ Call Test on a set of two non-spouse taxpayers. """
        # The two test people are set up as spouses; we need to split
        # them up.
        self.person1.spouse = None
        self.person2.spouse = None
        test_result = (
            self.tax({self.person1, self.person2}, self.initial_year))
        test_target = (
            self.tax(self.person1, self.initial_year)
            + self.tax(self.person2, self.initial_year))
        self.assertEqual(test_result, test_target)

    def test_taxpayer_spouses(self):
        """ Call Test on a set of two spouse taxpayers. """
        # NOTE: This test is vulnerable to breakage if special tax
        # credits get implemented for spouses. Watch out for that.
        self.assertEqual(
            self.tax({self.person1, self.person2}, self.initial_year),
            self.tax(self.person1, self.initial_year)
            + self.tax(self.person2, self.initial_year))

    def test_inflation_adjust(self):
        """ Call Test on a future year with inflation effects. """
        # Start with a baseline result in initial_year. Then confirm
        # that the tax owing on twice that amount in double_year should
        # be exactly double the tax owing on the baseline result.
        # (Anything else suggests that something is not being inflation-
        # adjusted properly, e.g. a bracket or a deduction)
        double_tax = self.tax(
            self.person1_taxable_income * 2, self.double_year)
        single_tax = self.tax(
            self.person1_taxable_income, self.initial_year)
        self.assertEqual(
            single_tax * 2,
            double_tax)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

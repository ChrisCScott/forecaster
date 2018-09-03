""" Tests for Canada-specific Tax subclasses. """

import unittest
from decimal import Decimal
from forecaster import Person, Money
from forecaster.canada import TaxCanada, RRSP, TaxableAccount, constants


class TestTaxCanada(unittest.TestCase):
    """ Tests TaxCanada. """

    @classmethod
    def setUpClass(cls):
        """ Sets up immutable constants used across test calls. """
        cls.initial_year = 2000

        # Build 100 years of inflation adjustments.
        growth_factor = 32
        year_range = range(cls.initial_year, cls.initial_year + 100)
        cls.inflation_adjustments = {
            year: 1 + (year - cls.initial_year) / growth_factor
            for year in year_range
        }

        # Build some brackets with nice round numbers:
        constants.TAX_BRACKETS = {
            'Federal': {
                cls.initial_year: {
                    Money(0): Decimal('0.1'),
                    Money('100'): Decimal('0.2'),
                    Money('10000'): Decimal('0.3')
                }
            },
            'BC': {
                cls.initial_year: {
                    Money(0): Decimal('0.25'),
                    Money('1000'): Decimal('0.5'),
                    Money('100000'): Decimal('0.75')
                }
            }
        }
        constants.TAX_PERSONAL_DEDUCTION = {
            'Federal': {cls.initial_year: Money('100')},
            'BC': {cls.initial_year: Money('1000')}
        }
        constants.TAX_CREDIT_RATE = {
            'Federal': {cls.initial_year: Decimal('0.1')},
            'BC': {cls.initial_year: Decimal('0.25')}
        }
        constants.TAX_PENSION_CREDIT = {
            'Federal': {cls.initial_year: Money('100')},
            'BC': {cls.initial_year: Decimal('1000')}
        }
        # It's convenient (and accurate!) to use the same values
        # for the spousal amount and the personal deduction:
        constants.TAX_SPOUSAL_AMOUNT = constants.TAX_PERSONAL_DEDUCTION

    def setUp(self):
        """ Sets up mutable variables for each test call. """
        # Set to default province:
        self.province = 'BC'
        self.tax = TaxCanada(self.inflation_adjustments, province='BC')

        # Set up some people to test on:
        # Person1 makes $100,000/yr, has a taxable account with $500,000
        # taxable income, and an RRSP with $500,000 in taxable income.
        self.person1 = Person(
            self.initial_year, "Tester 1", self.initial_year - 20,
            retirement_date=self.initial_year + 45, gross_income=100000)
        self.taxable_account1 = TaxableAccount(
            owner=self.person1,
            acb=0, balance=Money(1000000), rate=Decimal('0.05'), nper=1)
        self.taxable_account1.add_transaction(-Money(1000000), when='start')
        # NOTE: by using an RRSP here, a pension income tax credit will
        # be applied by TaxCanadaJurisdiction. Be aware of this if you
        # want to test this output against a generic Tax object with
        # Canadian brackets.
        self.rrsp = RRSP(
            self.person1,
            inflation_adjust=self.inflation_adjustments,
            contribution_room=0,
            balance=Money(500000), rate=Decimal('0.05'), nper=1)
        self.rrsp.add_transaction(-Money(500000), when='start')

        # Person2 makes $50,000/yr and has a taxable account with 
        # $5000 taxable income.
        self.person2 = Person(
            self.initial_year, "Tester 2", self.initial_year - 18,
            retirement_date=self.initial_year + 47, gross_income=50000)
        self.taxable_account2 = TaxableAccount(
            owner=self.person2,
            acb=0, balance=Money(10000), rate=Decimal('0.05'), nper=1)
        self.taxable_account2.add_transaction(-Money(10000), when='start')

    def test_init_federal(self):
        """ Test TaxCanada.__init__ for federal jurisdiction. """
        # There's some type-conversion going on, so test the Decimal-
        # valued `amount` of the Tax's tax bracket's keys against the
        # Decimal key object of the Constants tax brackets.
        tax = TaxCanada(self.inflation_adjustments, self.province)
        for year in constants.TAX_BRACKETS['Federal']:
            self.assertEqual(
                tax.federal_tax.tax_brackets(year),
                {
                    Money(bracket): value
                    for bracket, value in
                    constants.TAX_BRACKETS['Federal'][year].items()
                }
            )
            self.assertEqual(
                tax.federal_tax.personal_deduction(year),
                constants.TAX_PERSONAL_DEDUCTION['Federal'][year])
            self.assertEqual(
                tax.federal_tax.credit_rate(year),
                constants.TAX_CREDIT_RATE['Federal'][year])
        self.assertTrue(callable(tax.federal_tax.inflation_adjust))

    def test_init_provincial(self):
        """ Test TaxCanada.__init__ for provincial jurisdiction. """
        tax = TaxCanada(self.inflation_adjustments, self.province)
        for year in constants.TAX_BRACKETS[self.province]:
            self.assertEqual(
                tax.provincial_tax.tax_brackets(year),
                {
                    Money(bracket): value
                    for bracket, value in
                    constants.TAX_BRACKETS[self.province][year].items()
                }
            )
            self.assertEqual(
                tax.provincial_tax.personal_deduction(year),
                constants.TAX_PERSONAL_DEDUCTION[self.province][year])
            self.assertEqual(
                tax.provincial_tax.credit_rate(year),
                constants.TAX_CREDIT_RATE[self.province][year])
        self.assertTrue(callable(tax.provincial_tax.inflation_adjust))

    def test_init_min_args(self):
        """ Test init when Omitting optional arguments. """
        tax = TaxCanada(self.inflation_adjustments)
        for year in constants.TAX_BRACKETS[self.province]:
            self.assertEqual(
                tax.provincial_tax.tax_brackets(year),
                {
                    Money(bracket): value
                    for bracket, value in
                    constants.TAX_BRACKETS[self.province][year].items()
                }
            )
            self.assertEqual(
                tax.provincial_tax.personal_deduction(year),
                constants.TAX_PERSONAL_DEDUCTION[self.province][year])
            self.assertEqual(
                tax.provincial_tax.credit_rate(year),
                constants.TAX_CREDIT_RATE[self.province][year])
        self.assertTrue(callable(tax.provincial_tax.inflation_adjust))

    def test_call_money(self):
        """ Test TaxCanada.__call__ on Money input """
        taxable_income = Money(100000)
        self.assertEqual(
            self.tax(taxable_income, self.initial_year),
            self.tax.federal_tax(taxable_income, self.initial_year) +
            self.tax.provincial_tax(taxable_income, self.initial_year)
        )

    def test_call_person(self):
        """ Test TaxCanada.__call__ on one Person input """
        self.assertEqual(
            self.tax(self.person1, self.initial_year),
            self.tax.federal_tax(self.person1, self.initial_year) +
            self.tax.provincial_tax(self.person1, self.initial_year)
        )

    def test_call_person_set(self):
        """ Test TaxCanada.__call__ on a one-Person set input """
        # Should get the same result as for a setless Person:
        self.assertEqual(
            self.tax({self.person1}, self.initial_year),
            self.tax(self.person1, self.initial_year)
        )

    def test_call_people(self):
        """ Test TaxCanada.__call__ on a set of multiple people. """
        # The people are unrelated, so should get a result which is
        # just the sum of their tax treatments.
        self.assertEqual(
            self.tax({self.person1, self.person2}, self.initial_year),
            self.tax.federal_tax(
                {self.person1, self.person2}, self.initial_year
            ) +
            self.tax.provincial_tax(
                {self.person1, self.person2}, self.initial_year
            )
        )

    def test_spousal_tax_credit(self):
        """ Test spousal tax credit behaviour. """
        # Ensure person 2's net income is less than the federal spousal
        # amount:
        spousal_amount = (
            constants.TAX_SPOUSAL_AMOUNT['Federal'][self.initial_year])
        shortfall = spousal_amount / 2
        deductions = self.tax.federal_tax.deductions(
            self.person2, self.initial_year)
        self.person2.gross_income = deductions + spousal_amount - shortfall

        # Ensure that there are is no taxable income for person2 
        # beyond the above (to stay under spousal amount):
        self.taxable_account2.owner = self.person1

        # Get a tax treatment baseline for unrelated people:
        baseline_tax = self.tax.federal_tax(
            {self.person1, self.person2}, self.initial_year
        )

        # Wed the two people in holy matrimony:
        self.person1.spouse = self.person2

        # Now determine total tax liability federally:
        spousal_tax = self.tax.federal_tax(
            {self.person1, self.person2}, self.initial_year
        )

        target = baseline_tax - (
            shortfall * self.tax.federal_tax.credit_rate(
                self.initial_year)
        )

        # The different between these scenarios should be equal to
        # the amount of the spousal tax credit:
        self.assertEqual(
            spousal_tax,
            target
        )

    def test_pension_tax_credit(self):
        """ Test pension tax credit behaviour. """
        # TODO
        pass

if __name__ == '__main__':
    unittest.main()

""" Tests for Canada-specific Tax subclasses. """

import unittest
from decimal import Decimal
from forecaster import Person
from forecaster.canada import TaxCanada, RRSP, TaxableAccount, constants


class TestTaxCanada(unittest.TestCase):
    """ Tests TaxCanada. """

    def setUp(self):
        """ Sets up mutable variables for each test call. """
        # Set up constants:
        self.initial_year = 2000
        self.constants = constants.ConstantsCanada()

        # Modify constants to make math easier:
        # Build some brackets with nice round numbers:
        self.constants.TAX_BRACKETS = {
            'Federal': {
                self.initial_year: {
                    0: 0.1,
                    100: 0.2,
                    10000: 0.3}},
            'BC': {
                self.initial_year: {
                    0: 0.25,
                    1000: 0.5,
                    100000: 0.75}}}
        self.constants.TAX_PERSONAL_DEDUCTION = {
            'Federal': {self.initial_year: 100},
            'BC': {self.initial_year: 1000}}
        self.constants.TAX_CREDIT_RATE = {
            'Federal': {self.initial_year: 0.1},
            'BC': {self.initial_year: 0.25}}
        self.constants.TAX_PENSION_CREDIT = {
            'Federal': {self.initial_year: 100},
            'BC': {self.initial_year: 1000}}
        # It's convenient (and accurate!) to use the same values
        # for the spousal amount and the personal deduction:
        self.constants.TAX_SPOUSAL_AMOUNT = (
            self.constants.TAX_PERSONAL_DEDUCTION)

        # Build 100 years of inflation adjustments.
        growth_factor = 32
        year_range = range(self.initial_year, self.initial_year + 100)
        self.inflation_adjustments = {
            year: 1 + (year - self.initial_year) / growth_factor
            for year in year_range}

        # Set to default province:
        self.province = 'BC'
        self.tax = TaxCanada(
            self.inflation_adjustments, province='BC', constants=self.constants)

        # Set up some people to test on:
        # Person1 makes $100,000/yr, has a taxable account with $500,000
        # taxable income, and an RRSP with $500,000 in taxable income.
        self.person1 = Person(
            self.initial_year, "Tester 1", self.initial_year - 20,
            retirement_date=self.initial_year + 45, gross_income=100000)
        self.taxable_account1 = TaxableAccount(
            owner=self.person1,
            acb=0, balance=1000000, rate=0.05, nper=1)
        self.taxable_account1.add_transaction(-1000000, when='start')
        # NOTE: by using an RRSP here, a pension income tax credit will
        # be applied by TaxCanadaJurisdiction. Be aware of this if you
        # want to test this output against a generic Tax object with
        # Canadian brackets.
        self.rrsp = RRSP(
            self.person1,
            inflation_adjust=self.inflation_adjustments,
            contribution_room=0,
            balance=500000, rate=0.05, nper=1,
            constants=self.constants)
        self.rrsp.add_transaction(-500000, when='start')

        # Person2 makes $50,000/yr and has a taxable account with
        # $5000 taxable income.
        self.person2 = Person(
            self.initial_year, "Tester 2", self.initial_year - 18,
            retirement_date=self.initial_year + 47, gross_income=50000)
        self.taxable_account2 = TaxableAccount(
            owner=self.person2,
            acb=0, balance=10000, rate=0.05, nper=1)
        self.taxable_account2.add_transaction(-10000, when='start')

    def setUp_decimal(self): # pylint: disable=invalid-name
        """ Sets up mutable variables for each test call. """
        # Set up constants:
        self.initial_year = 2000
        self.constants = constants.ConstantsCanada(high_precision=Decimal)

        # Modify constants to make math easier:
        # Build some brackets with nice round numbers:
        self.constants.TAX_BRACKETS = {
            'Federal': {
                self.initial_year: {
                    Decimal(0): Decimal('0.1'),
                    Decimal(100): Decimal('0.2'),
                    Decimal(10000): Decimal('0.3')}},
            'BC': {
                self.initial_year: {
                    Decimal(0): Decimal('0.25'),
                    Decimal(1000): Decimal('0.5'),
                    Decimal(100000): Decimal('0.75')}}}
        self.constants.TAX_PERSONAL_DEDUCTION = {
            'Federal': {self.initial_year: Decimal('100')},
            'BC': {self.initial_year: Decimal('1000')}}
        self.constants.TAX_CREDIT_RATE = {
            'Federal': {self.initial_year: Decimal('0.1')},
            'BC': {self.initial_year: Decimal('0.25')}}
        self.constants.TAX_PENSION_CREDIT = {
            'Federal': {self.initial_year: Decimal('100')},
            'BC': {self.initial_year: Decimal('1000')}}
        # It's convenient (and accurate!) to use the same values
        # for the spousal amount and the personal deduction:
        self.constants.TAX_SPOUSAL_AMOUNT = (
            self.constants.TAX_PERSONAL_DEDUCTION)

        # Build 100 years of inflation adjustments.
        growth_factor = Decimal(32)
        year_range = range(self.initial_year, self.initial_year + 100)
        self.inflation_adjustments = {
            year: 1 + (year - self.initial_year) / growth_factor
            for year in year_range}

        # Set to default province:
        self.province = 'BC'
        self.tax = TaxCanada(
            self.inflation_adjustments, province='BC', constants=self.constants)

        # Set up some people to test on:
        # Person1 makes $100,000/yr, has a taxable account with $500,000
        # taxable income, and an RRSP with $500,000 in taxable income.
        self.person1 = Person(
            self.initial_year, "Tester 1", self.initial_year - 20,
            retirement_date=self.initial_year + 45, gross_income=100000)
        self.taxable_account1 = TaxableAccount(
            owner=self.person1,
            acb=0, balance=Decimal(1000000), rate=Decimal('0.05'), nper=1)
        self.taxable_account1.add_transaction(-Decimal(1000000), when='start')
        # NOTE: by using an RRSP here, a pension income tax credit will
        # be applied by TaxCanadaJurisdiction. Be aware of this if you
        # want to test this output against a generic Tax object with
        # Canadian brackets.
        self.rrsp = RRSP(
            self.person1,
            inflation_adjust=self.inflation_adjustments,
            contribution_room=0,
            balance=Decimal(500000), rate=Decimal('0.05'), nper=1,
            constants=self.constants)
        self.rrsp.add_transaction(-Decimal(500000), when='start')

        # Person2 makes $50,000/yr and has a taxable account with
        # $5000 taxable income.
        self.person2 = Person(
            self.initial_year, "Tester 2", self.initial_year - 18,
            retirement_date=self.initial_year + 47, gross_income=50000)
        self.taxable_account2 = TaxableAccount(
            owner=self.person2,
            acb=0, balance=Decimal(10000), rate=Decimal('0.05'), nper=1)
        self.taxable_account2.add_transaction(-Decimal(10000), when='start')

    def test_init_federal(self):
        """ Test TaxCanada.__init__ for federal jurisdiction. """
        # There's some type-conversion going on, so test the Decimal-
        # valued `amount` of the Tax's tax bracket's keys against the
        # Decimal key object of the Constants tax brackets.
        tax = TaxCanada(
            self.inflation_adjustments, self.province, constants=self.constants)
        for year in self.constants.TAX_BRACKETS['Federal']:
            self.assertEqual(
                tax.federal_tax.tax_brackets(year),
                self.constants.TAX_BRACKETS['Federal'][year])
            self.assertEqual(
                tax.federal_tax.personal_deduction(year),
                self.constants.TAX_PERSONAL_DEDUCTION['Federal'][year])
            self.assertEqual(
                tax.federal_tax.credit_rate(year),
                self.constants.TAX_CREDIT_RATE['Federal'][year])
        self.assertTrue(callable(tax.federal_tax.inflation_adjust))
        # Test that the default timings for CRA refunds/payments have
        # been set:
        self.assertEqual(
            set(tax.payment_timing), {self.constants.TAX_PAYMENT_TIMING})
        self.assertEqual(
            set(tax.refund_timing), {self.constants.TAX_REFUND_TIMING})

    def test_init_provincial(self):
        """ Test TaxCanada.__init__ for provincial jurisdiction. """
        tax = TaxCanada(
            self.inflation_adjustments, self.province, constants=self.constants)
        for year in self.constants.TAX_BRACKETS[self.province]:
            self.assertEqual(
                tax.provincial_tax.tax_brackets(year),
                {
                    bracket: value
                    for bracket, value in
                    self.constants.TAX_BRACKETS[self.province][year].items()})
            self.assertEqual(
                tax.provincial_tax.personal_deduction(year),
                self.constants.TAX_PERSONAL_DEDUCTION[self.province][year])
            self.assertEqual(
                tax.provincial_tax.credit_rate(year),
                self.constants.TAX_CREDIT_RATE[self.province][year])
        self.assertTrue(callable(tax.provincial_tax.inflation_adjust))

    def test_init_min_args(self):
        """ Test init when Omitting optional arguments. """
        tax = TaxCanada(self.inflation_adjustments, constants=self.constants)
        for year in self.constants.TAX_BRACKETS[self.province]:
            self.assertEqual(
                tax.provincial_tax.tax_brackets(year),
                {
                    bracket: value
                    for bracket, value in
                    self.constants.TAX_BRACKETS[self.province][year].items()})
            self.assertEqual(
                tax.provincial_tax.personal_deduction(year),
                self.constants.TAX_PERSONAL_DEDUCTION[self.province][year])
            self.assertEqual(
                tax.provincial_tax.credit_rate(year),
                self.constants.TAX_CREDIT_RATE[self.province][year])
        self.assertTrue(callable(tax.provincial_tax.inflation_adjust))

    def test_call_money(self):
        """ Test TaxCanada.__call__ on Decimal input """
        taxable_income = 100000
        self.assertEqual(
            self.tax(taxable_income, self.initial_year),
            self.tax.federal_tax(taxable_income, self.initial_year) +
            self.tax.provincial_tax(taxable_income, self.initial_year))

    def test_call_person(self):
        """ Test TaxCanada.__call__ on one Person input """
        self.assertEqual(
            self.tax(self.person1, self.initial_year),
            self.tax.federal_tax(self.person1, self.initial_year) +
            self.tax.provincial_tax(self.person1, self.initial_year))

    def test_call_person_set(self):
        """ Test TaxCanada.__call__ on a one-Person set input """
        # Should get the same result as for a setless Person:
        self.assertEqual(
            self.tax({self.person1}, self.initial_year),
            self.tax(self.person1, self.initial_year))

    def test_call_people(self):
        """ Test TaxCanada.__call__ on a set of multiple people. """
        # The people are unrelated, so should get a result which is
        # just the sum of their tax treatments.
        self.assertEqual(
            self.tax({self.person1, self.person2}, self.initial_year),
            self.tax.federal_tax(
                {self.person1, self.person2}, self.initial_year)
            + self.tax.provincial_tax(
                {self.person1, self.person2}, self.initial_year))

    def test_spousal_tax_credit(self):
        """ Test spousal tax credit behaviour. """
        # Ensure person 2's net income is less than the federal spousal
        # amount:
        spousal_amount = (
            self.constants.TAX_SPOUSAL_AMOUNT['Federal'][self.initial_year])
        shortfall = spousal_amount / 2
        deduction = self.tax.federal_tax.deduction(
            self.person2, self.initial_year)
        self.person2.gross_income = deduction + spousal_amount - shortfall

        # Ensure that there is no taxable income for person2 beyond the
        # above (to stay under spousal amount):
        self.taxable_account2.owner = self.person1

        # Get a tax treatment baseline for unrelated people:
        baseline_tax = self.tax.federal_tax(
            {self.person1, self.person2}, self.initial_year)

        # Wed the two people in holy matrimony:
        self.person1.spouse = self.person2

        # Now determine total tax liability federally:
        spousal_tax = self.tax.federal_tax(
            {self.person1, self.person2}, self.initial_year)

        # Tax should be reduced (relative to baseline) by the shortfall
        # of person2's income (relative to the spousal amount, after
        # applying deductions), scaled down by the credit rate.
        # That is, for every dollar that person2 earns _under_ the
        # spousal amount, tax is reduced by (e.g.) 15 cents (assuming
        # a credit rate of 15%)
        target = baseline_tax - (
            shortfall * self.tax.federal_tax.credit_rate(self.initial_year))

        # The different between these scenarios should be equal to
        # the amount of the spousal tax credit:
        self.assertEqual(spousal_tax, target)

    def test_pension_tax_credit(self):
        """ Test pension tax credit behaviour. """
        # TODO Implement pension tax credit, then test it.
        pass

if __name__ == '__main__':
    unittest.main()

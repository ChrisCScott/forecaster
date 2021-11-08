""" Unit tests for `TaxForecast`. """

import unittest
from decimal import Decimal
from forecaster import (
    Person, TaxForecast, Tax, Account, Timing)


class TestTaxForecast(unittest.TestCase):
    """ Tests TaxForecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Decimal(0): Decimal(0.5)}})
        # A person who is paid $1000 gross ($500 withheld):
        timing = Timing(frequency='BW')
        self.person1 = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2045",
            gross_income=Decimal(1000),
            tax_treatment=tax,
            payment_timing=timing)
        # A person who is paid $500 gross ($250 withheld):
        self.person2 = Person(
            initial_year=self.initial_year,
            name="Test 2",
            birth_date="1 January 1982",
            retirement_date="31 December 2047",
            gross_income=Decimal(500),
            tax_treatment=tax,
            payment_timing=timing)
        # An account owned by person1 with $100 to withdraw
        self.account1 = Account(
            owner=self.person1,
            balance=Decimal(100),
            rate=0)
        # An account owned by person2 with $200 to withdraw
        self.account2 = Account(
            owner=self.person2,
            balance=Decimal(100),
            rate=0)
        # An account that belongs in some sense to both people
        # with $50 to withdraw
        self.account_joint = Account(
            owner=self.person1,
            balance=Decimal(100),
            rate=0)
        self.person2.accounts.add(self.account_joint)

        self.forecast = TaxForecast(
            initial_year=self.initial_year,
            people={self.person1, self.person2},
            tax_treatment=tax)

    def test_tax_withheld(self):
        """ Test withholding taxes for two people. """
        # Tax is never withheld by the base Account type,
        # so assign withholdings manually:
        self.account1.tax_withheld = Decimal(1)
        self.account2.tax_withheld = Decimal(1)
        self.account_joint.tax_withheld = Decimal(1)
        # Each account should be counted once, plus the $750
        # withheld on employment income, for a total of $753:
        self.assertEqual(
            self.forecast.tax_withheld,
            Decimal(753))

    def test_tax_owing(self):
        """ Test an amount carried over from previous year. """
        # The base Account type never has taxable income,
        # so assign some manually for testing:
        self.account1.taxable_income = Decimal(60)
        self.account2.taxable_income = Decimal(40)
        # The people earn $1500 from employment, plus $100 from their
        # accounts, for a total of $1600. At a 50% tax rate, $800
        # should be owing:
        self.assertEqual(
            self.forecast.tax_owing,
            Decimal(800))

    def test_update_available(self):
        """ Test update_available, which should have no effect. """
        # Whatever `available` is, it should be unchanged, so keep
        # a copy to compare against after the method call:
        available = {Decimal(0.5): Decimal(100)}
        compare = dict(available)
        self.forecast.__call__(available)
        # Should be no change:
        self.assertEqual(
            available,
            compare)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

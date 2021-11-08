""" Unit tests for `IncomeForecast`. """

import unittest
from decimal import Decimal
from forecaster import Person, IncomeForecast, Tax, Timing


class TestIncomeForecast(unittest.TestCase):
    """ Tests IncomeForecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Decimal(0): Decimal(0.5)}})
        # A person who is paid $200 gross ($100 net) every 2 weeks:
        timing = Timing(frequency='BW')
        self.person1 = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2045",
            gross_income=Decimal(5200),
            tax_treatment=tax,
            payment_timing=timing)
        # A person who is paid $100 gross ($50 net) every 2 weeks:
        self.person2 = Person(
            initial_year=self.initial_year,
            name="Test 2",
            birth_date="1 January 1982",
            retirement_date="31 December 2047",
            gross_income=Decimal(2600),
            tax_treatment=tax,
            payment_timing=timing)
        self.forecast = IncomeForecast(
            initial_year=self.initial_year,
            people={self.person1, self.person2})

    def test_gross_income(self):
        """ Test gross income for two people. """
        self.assertEqual(
            self.forecast.gross_income,
            self.person1.gross_income + self.person2.gross_income)

    def test_net_income(self):
        """ Test net income for two people. """
        self.assertEqual(
            self.forecast.net_income,
            self.person1.net_income + self.person2.net_income)

    def test_tax_withheld(self):
        """ Test net income for two people. """
        self.assertEqual(
            self.forecast.tax_withheld,
            self.person1.tax_withheld + self.person2.tax_withheld)

    def test_carryover(self):
        """ Test an amount carried over from previous year. """
        carryover = Decimal(100)
        available = {Decimal(0.5): carryover}
        self.forecast(available)
        self.assertEqual(
            self.forecast.carryover,
            carryover)

    def test_update_available(self):
        """ Test recording of cash inflows from employment. """
        available = {}
        self.forecast(available)
        # There should be at least 26 inflows for the 26 biweekly
        # pay periods:
        self.assertGreaterEqual(
            len(self.forecast.transactions[available]),
            26)
        # Assuming there are no other inflows or outflows (and, since
        # this is the first year, there shouldn't be as there are no
        # carryovers), the sum of inflows should be 150*26=3900
        self.assertAlmostEqual(
            sum(self.forecast.transactions[available].values()),
            Decimal(3900),
            places=2)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

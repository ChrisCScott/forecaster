""" Tests `HistoricalReturnReader`. """

import os
import unittest
from decimal import Decimal
from datetime import datetime
from forecaster.scenario.historical_value_reader import HistoricalValueReader

DIR_PATH = os.path.dirname(__file__)
TEST_PATH_PORTFOLIO = os.path.join(DIR_PATH, 'test_portfolio_values.csv')
TEST_PATH_PERCENTAGES = os.path.join(DIR_PATH, 'test_percentages.csv')
# Both CSV files correspond to this series of percentage returns:
PORTFOLIO_VALUES = {
    datetime(1999,1,1): 100,
    datetime(2000,1,1): 100,
    datetime(2001,1,1): 200,
    datetime(2002,1,1): 150}

class TestHistoricalReturnReader(unittest.TestCase):
    """ Tests the `HistoricalReturnReader` class. """

    def test_read_portfolio_values_default(self):
        """ Reads from test_portfolio_values.csv """
        reader = HistoricalValueReader(TEST_PATH_PORTFOLIO)
        self.assertEqual(reader.values, PORTFOLIO_VALUES)

    def test_read_portfolio_values(self):
        """ Reads from test_portfolio_values.csv with explicit args. """
        reader = HistoricalValueReader(
            TEST_PATH_PORTFOLIO, return_values=False)
        self.assertEqual(reader.values, PORTFOLIO_VALUES)

    def test_read_percentage_values(self):
        """ Reads from test_percentage.csv """
        reader = HistoricalValueReader(
            TEST_PATH_PERCENTAGES, return_values=True)
        self.assertEqual(reader.values, PORTFOLIO_VALUES)

    def test_decimal(self):
        """ Tests Decimal high-precision conversion on read. """
        reader = HistoricalValueReader(
            TEST_PATH_PORTFOLIO, return_values=False, high_precision=Decimal)
        # Convert values to Decimal for comparison:
        vals = {key: Decimal(val) for (key, val) in PORTFOLIO_VALUES.items()}
        self.assertEqual(reader.values, vals)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

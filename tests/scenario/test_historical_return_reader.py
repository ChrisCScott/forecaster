""" Tests `HistoricalReturnReader`. """

import os
import unittest
from decimal import Decimal
from datetime import datetime
from forecaster.scenario.historical_return_reader import HistoricalReturnReader

DIR_PATH = os.path.dirname(__file__)
TEST_PATH_PORTFOLIO = os.path.join(DIR_PATH, 'test_portfolio_values.csv')
TEST_PATH_PERCENTAGES = os.path.join(DIR_PATH, 'test_percentages.csv')
# Both CSV files correspond to this series of percentage returns:
PERCENTAGE_VALUES = {
    datetime(2000,1,1): 0,
    datetime(2001,1,1): 1,
    datetime(2002,1,1): -0.25}

class TestHistoricalReturnReader(unittest.TestCase):
    """ Tests the `HistoricalReturnReader` class. """

    def test_read_portfolio_values(self):
        """ Tests reading from test_portfolio_values.csv """
        reader = HistoricalReturnReader(
            TEST_PATH_PORTFOLIO, portfolio_values=True)
        self.assertEqual(reader.returns, PERCENTAGE_VALUES)

    def test_read_percentage_values(self):
        """ Tests reading from test_percentage.csv """
        reader = HistoricalReturnReader(
            TEST_PATH_PERCENTAGES, portfolio_values=False)
        self.assertEqual(reader.returns, PERCENTAGE_VALUES)

    def test_read_portfolio_values_implicit(self):
        """ Tests reading from test_portfolio_values.csv without hints. """
        # Reader needs to infer that the file provides portfolio values
        # and not percentage values:
        reader = HistoricalReturnReader(TEST_PATH_PORTFOLIO)
        self.assertEqual(reader.returns, PERCENTAGE_VALUES)

    def test_decimal(self):
        """ Tests Decimal high-precision conversion on read. """
        reader = HistoricalReturnReader(
            TEST_PATH_PORTFOLIO, portfolio_values=True, high_precision=Decimal)
        # Convert values to Decimal for comparison:
        vals = {key: Decimal(val) for (key, val) in PERCENTAGE_VALUES.items()}
        self.assertEqual(reader.returns, vals)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

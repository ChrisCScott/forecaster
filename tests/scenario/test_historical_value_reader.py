""" Tests `HistoricalReturnReader`. """

import os
import unittest
from decimal import Decimal
from datetime import datetime
from forecaster.scenario.historical_value_reader import (
    HistoricalValueReader, HistoricalValueReaderArray)

DIR_PATH = os.path.dirname(__file__)
TEST_PATH_PORTFOLIO = os.path.join(DIR_PATH, 'test_portfolio_values.csv')
TEST_PATH_PERCENTAGES = os.path.join(DIR_PATH, 'test_percentages.csv')
# Both CSV files correspond to this series of percentage returns:
PORTFOLIO_VALUES = {
    datetime(1999,1,1): 100,
    datetime(2000,1,1): 100,
    datetime(2001,1,1): 200,
    datetime(2002,1,1): 150}
RETURNS_VALUES = {
    datetime(2000,1,1): 0,
    datetime(2001,1,1): 1,
    datetime(2002,1,1): -.25}
# The same series again, but make them ~*~arrays~*~
PORTFOLIO_VALUES_ARRAY = (
    [
        datetime(1999,1,1),
        datetime(2000,1,1),
        datetime(2001,1,1),
        datetime(2002,1,1)],
    [
        100, 100, 200, 150])
RETURNS_VALUES_ARRAY = (
    [
        datetime(2000,1,1),
        datetime(2001,1,1),
        datetime(2002,1,1)],
    [
        0, 1, -.25])

class TestHistoricalReturnReader(unittest.TestCase):
    """ Tests the `HistoricalReturnReader` class. """

    def test_read_read(self):
        """ Reads from real-world CSV files """
        # Just ensure that we're reading in the right number of columns;
        # this test is mostly about confirming that we can read a file
        # with big numbers without raising an exception:
        reader = HistoricalValueReader('msci_world.csv')
        self.assertEqual(len(reader.data), 1)

    def test_read_values_default(self):
        """ Reads from test_portfolio_values.csv """
        reader = HistoricalValueReader(TEST_PATH_PORTFOLIO)
        vals = reader.values()
        self.assertEqual(vals[0], PORTFOLIO_VALUES)

    def test_read_values_explicit(self):
        """ Reads from test_portfolio_values.csv with explicit args. """
        reader = HistoricalValueReader(TEST_PATH_PORTFOLIO, returns=False)
        vals = reader.values()
        self.assertEqual(vals[0], PORTFOLIO_VALUES)

    def test_read_returns(self):
        """ Reads from test_percentage.csv """
        reader = HistoricalValueReader(TEST_PATH_PERCENTAGES)
        vals = reader.returns()
        self.assertEqual(vals[0], RETURNS_VALUES)

    def test_read_returns_explicit(self):
        """ Reads from test_percentage.csv with explicit args """
        reader = HistoricalValueReader(TEST_PATH_PERCENTAGES, returns=True)
        vals = reader.returns()
        self.assertEqual(vals[0], RETURNS_VALUES)

    def test_convert_values_to_returns(self):
        """ Converts portfolio value data to returns data """
        reader = HistoricalValueReader(TEST_PATH_PORTFOLIO)
        vals = reader.returns()
        self.assertEqual(vals[0], RETURNS_VALUES)

    def test_convert_returns_to_values(self):
        """ Converts returns data to portfolio value data """
        reader = HistoricalValueReader(TEST_PATH_PERCENTAGES)
        vals = reader.values()
        self.assertEqual(vals[0], PORTFOLIO_VALUES)

    def test_decimal(self):
        """ Tests Decimal high-precision conversion on read. """
        reader = HistoricalValueReader(
            TEST_PATH_PORTFOLIO, returns=False, high_precision=Decimal)
        vals = reader.values()
        # Convert values to Decimal for comparison:
        compare_vals = {
            key: Decimal(val) for (key, val) in PORTFOLIO_VALUES.items()}
        self.assertEqual(vals[0], compare_vals)

class TestHistoricalReturnReaderArray(unittest.TestCase):
    """ Tests the `HistoricalReturnReaderArray` class. """

    def test_read_read(self):
        """ Reads from real-world CSV files """
        # Just ensure that we're reading in the right number of columns;
        # this test is mostly about confirming that we can read a file
        # with big numbers without raising an exception:
        reader = HistoricalValueReaderArray('msci_world.csv')
        self.assertEqual(len(reader.data), 1)

    def test_read_values_default(self):
        """ Reads from test_portfolio_values.csv """
        reader = HistoricalValueReaderArray(TEST_PATH_PORTFOLIO)
        vals = reader.values()
        self.assertEqual(vals[0], PORTFOLIO_VALUES_ARRAY)

    def test_read_values_explicit(self):
        """ Reads from test_portfolio_values.csv with explicit args. """
        reader = HistoricalValueReaderArray(TEST_PATH_PORTFOLIO, returns=False)
        vals = reader.values()
        self.assertEqual(vals[0], PORTFOLIO_VALUES_ARRAY)

    def test_read_returns(self):
        """ Reads from test_percentage.csv """
        reader = HistoricalValueReaderArray(TEST_PATH_PERCENTAGES)
        vals = reader.returns()
        self.assertEqual(vals[0], RETURNS_VALUES_ARRAY)

    def test_read_returns_explicit(self):
        """ Reads from test_percentage.csv with explicit args """
        reader = HistoricalValueReaderArray(TEST_PATH_PERCENTAGES, returns=True)
        vals = reader.returns()
        self.assertEqual(vals[0], RETURNS_VALUES_ARRAY)

    def test_convert_values_to_returns(self):
        """ Converts portfolio value data to returns data """
        reader = HistoricalValueReaderArray(TEST_PATH_PORTFOLIO)
        vals = reader.returns()
        self.assertEqual(vals[0], RETURNS_VALUES_ARRAY)

    def test_convert_returns_to_values(self):
        """ Converts returns data to portfolio value data """
        reader = HistoricalValueReaderArray(TEST_PATH_PERCENTAGES)
        vals = reader.values()
        self.assertEqual(vals[0], PORTFOLIO_VALUES_ARRAY)

    def test_decimal(self):
        """ Tests Decimal high-precision conversion on read. """
        reader = HistoricalValueReaderArray(
            TEST_PATH_PORTFOLIO, returns=False, high_precision=Decimal)
        vals = reader.values()
        # Convert values to Decimal for comparison:
        compare_vals = (
            PORTFOLIO_VALUES_ARRAY[0],
            [Decimal(val) for val in PORTFOLIO_VALUES_ARRAY[1]])
        self.assertEqual(vals[0], compare_vals)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

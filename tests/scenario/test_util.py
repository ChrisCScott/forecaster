""" Unit tests for `forecaster.scenario.util` functions. """

import unittest
from datetime import datetime
from decimal import Decimal
import dateutil
from forecaster.scenario import util

class TestInterpolateValue(unittest.TestCase):
    """ A test suite for `util.interpolate_value`. """

    def setUp(self):
        # Build two equivalent (annual) datasets, one expressed as
        # absolute portfolio values and the other expressed as relative
        # returns. This will make comparisons a bit easier:
        self.values = {
            datetime(1999,1,1): 100,
            datetime(2000,1,1): 100,
            datetime(2001,1,1): 200,
            datetime(2002,1,1): 150}
        self.returns = {
            datetime(2000,1,1): 0,
            datetime(2001,1,1): 1,
            datetime(2002,1,1): -.25}

    def test_date_exact(self):
        """ Test `date` being a key in `returns` """
        # The easy case: `date` is in returns, so return the exact value
        date = datetime(2000,1,1)
        val = util.interpolate_value(self.values, date)
        self.assertEqual(val, 100)

    def test_date_out_of_bounds(self):
        """ Test `date` being out of bounds of the dataset """
        date = datetime(1998,1,1)
        with self.assertRaises(KeyError):
            _ = util.interpolate_value(self.values, date)

    def test_date_before_start(self):
        """ Test `date` being a bit earlier than the start date """
        date = datetime(1999,1,1)
        val = util.interpolate_value(self.values, date)
        self.assertEqual(val, 100)

    def test_date_between(self):
        """ Test `date` being between two represented dates """
        date = datetime(2000,7,1)
        val = util.interpolate_value(self.values, date)
        # Resulting value can be calculated various ways, but should be
        # somewhere between the starting and ending value:
        self.assertGreater(val, 100)
        self.assertLess(val, 250)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

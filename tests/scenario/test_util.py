""" Unit tests for `forecaster.scenario.util` functions. """

import unittest
from datetime import datetime
from decimal import Decimal
import dateutil
import forecaster.scenario.util

class TestInterpolateValue(unittest.TestCase):
    """ A test suite for `util.interpolate_value`. """

    def setUp(self):
        # Generate a dataset with mean 1.5 for each variable
        # and covariance matrix [[0.25, -0.25], [-0.25, 0.25]]:
        self.data_x = {
            datetime(2000, 1, 1): 1,
            datetime(2001, 1, 1): 2}
        self.data_y = {
            datetime(2000, 1, 1): 2,
            datetime(2001, 1, 1): 1}
        self.data = (self.data_x, self.data_y)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

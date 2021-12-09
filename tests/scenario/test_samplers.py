""" Unit tests for `forecaster.scenario.samplers` classes. """

import unittest
from datetime import datetime
from decimal import Decimal
from forecaster.scenario.samplers import MultivariateSampler, WalkForwardSampler

class TestMultivariateSampler(unittest.TestCase):
    """ A test suite for the `MultivariateSampler` class """

    def setUp(self):
        # Generate a dataset with mean 1.5 for each variable
        # and covariance matrix [[0.5, -0.5], [-0.5, 0.5]]:
        self.data_x = {
            datetime(2000, 1, 1): 1,
            datetime(2001, 1, 1): 2}
        self.data_y = {
            datetime(2000, 1, 1): 2,
            datetime(2001, 1, 1): 1}
        self.data = (self.data_x, self.data_y)

    def test_means(self):
        """ Test calculation of means from data input. """
        sampler = MultivariateSampler(self.data)
        self.assertEqual(sampler.means, [1.5, 1.5])

    def test_means_explicit(self):
        """ Test overriding mean from data by providing it explicitly. """
        # Override the mean for just the second var:
        sampler = MultivariateSampler(self.data, means=(None, 10))
        self.assertEqual(sampler.means, [1.5, 10])

    def test_covariances(self):
        """ Test calculation of covariances from data input. """
        sampler = MultivariateSampler(self.data)
        self.assertEqual(sampler.covariances, [[0.5, -0.5], [-0.5, 0.5]])

    def test_covariances_explicit(self):
        """ Test overriding covariances by providing it explicitly. """
        # Override the covariance for (data_x, data_y):
        sampler = MultivariateSampler(
            self.data, covariances=[[None, 1], [1, None]])
        self.assertEqual(sampler.covariances, [[0.5, 1], [1, 0.5]])

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

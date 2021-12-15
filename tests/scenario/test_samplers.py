""" Unit tests for `forecaster.scenario.samplers` classes. """

import unittest
from unittest import mock
from datetime import datetime
from decimal import Decimal
import numpy
import dateutil
from forecaster.scenario.samplers import MultivariateSampler, WalkForwardSampler

# Use constant seed for tests that rely on randomness:
RANDOM_TEST = numpy.random.default_rng(0)

class TestMultivariateSampler(unittest.TestCase):
    """ A test suite for the `MultivariateSampler` class. """

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
        self.assertEqual(sampler.covariances, [[0.25, -0.25], [-0.25, 0.25]])

    def test_covariances_explicit(self):
        """ Test overriding covariances by providing it explicitly. """
        # Override the covariance for (data_x, data_y):
        sampler = MultivariateSampler(
            self.data, covariances=[[None, 1], [1, None]])
        self.assertEqual(sampler.covariances, [[0.25, 1], [1, 0.25]])

    # Patch the random number generator to use the same seed in tests:
    @mock.patch.object(MultivariateSampler, 'random', RANDOM_TEST)
    def test_sample_statistics(self):
        """ Test `sample` to see if it produces the correct statistics. """
        sampler = MultivariateSampler(self.data)
        # Collect 40 samples of random variables X and Y, where each
        # random variable has mean 1.5, variance 0.25, and pairwise
        # covariance -0.25:
        samples = sampler.sample(40)
        # Conveniently represent samples and source data for each of
        # the random variables X and Y for testing:
        samples_x = [sample[0] for sample in samples]
        samples_y = [sample[1] for sample in samples]
        data_x = list(self.data_x.values())
        data_y = list(self.data_y.values())
        # Check to see if samples have the right statistical properties:
        # Mean
        self.assertAlmostEqual(
            numpy.mean(samples_x), numpy.mean(data_x),
            delta=0.1)
        self.assertAlmostEqual(
            numpy.mean(samples_y), numpy.mean(data_y),
            delta=0.1)
        # Variance
        self.assertAlmostEqual(
            numpy.var(samples_x), numpy.var(data_x),
            delta=0.02)
        self.assertAlmostEqual(
            numpy.var(samples_y), numpy.var(data_y),
            delta=0.02)
        # Covariance
        # Use `ddof=0` to get `numpy.cov` to agree with `numpy.var`.
        # See here for more:
        # https://stackoverflow.com/questions/21030668/why-do-numpy-cov-diagonal-elements-and-var-functions-have-different-values
        self.assertAlmostEqual(
            numpy.cov(samples_x, samples_y, ddof=0)[1][0],
            numpy.cov(data_x, data_y, ddof=0)[1][0],
            delta=0.02)

class TestWalkForwardSampler(unittest.TestCase):
    """ A test suite for the `WalkForwardSampler` class. """

    def setUp(self):
        # Generate a dataset where values double annually and another
        # where they halve annually:
        self.data_x = {
            datetime(2000, 1, 1): 1,
            datetime(2001, 1, 1): 2,
            datetime(2002, 1, 1): 4}
        self.data_y = {
            datetime(2000, 1, 1): 1,
            datetime(2001, 1, 1): 0.5,
            datetime(2002, 1, 1): 0.25}
        self.data = (self.data_x, self.data_y)

    def test_sample_basic(self):
        """ Tests a basic walk-forward sample. """
        # Get a 2-year walk-forward sequence:
        sampler = WalkForwardSampler(self.data)
        sample = sampler.sample(2)
        sample1, sample2 = sample  # separate sampled vars
        # No matter the sequence, the first variable should double and
        # the second variable should halve year-over-year.
        sample1_growth = sample1[1] / sample1[0]
        sample2_growth = sample2[1] / sample2[0]
        self.assertEqual(sample1_growth, 2)
        self.assertEqual(sample2_growth, 0.5)

    def test_sample_synchronize(self):
        """ Tests a walk-forward sample with synchronized dates. """
        # Get 100 one-year walk-forward sequences
        # (Use the the same data for each variable to simply asserts):
        sampler = WalkForwardSampler(
            (self.data_x, self.data_x), synchronize=True)
        sample = sampler.sample(1, 100)
        # We should have the same values for each variable, since we're
        # requiring use of the same start dates:
        for val1, val2 in sample:
            self.assertEqual(val1, val2)

    def test_sample_wrap_data(self):
        """ Tests a walk-forward sample with wrapped data. """
        # We only have 3 datapoints, so if we get three samples of
        # length 2 we are guaranteed to have a sample that consists of
        # the last entry followed by the first entry (i.e. (4,1))
        sampler = WalkForwardSampler((self.data_x,), wrap_data=True)
        samples = sampler.sample(2, num_samples=3)
        self.assertIn([[4,1]], samples)

    def test_sample_interval_easy(self):
        """ Tests a walk-forward sample with easily regularized dates. """
        data = {
            datetime(2000, 1, 1): 1,
            datetime(2000, 7, 1): 1,
            datetime(2001, 1, 1): 1,
            datetime(2001, 7, 1): 1}
        # `data` spans 2 years with semi-annual datapoints. Use an
        # interval of 1 year to require recalculation and to make the
        # math easy - the only length 2 sequence will have returns of
        # 300% for each year (as there's growth of 100% semiannually).
        interval = dateutil.relativedelta.relativedelta(years=1)
        sampler = WalkForwardSampler((data,), interval=interval)
        sample = sampler.sample(2)
        self.assertEqual(sample, [[3, 3]])

    def test_sample_interval_hard(self):
        """ Tests a walk-forward sample with hard-to-regularize dates. """
        data = {
            datetime(2000, 1, 1): 1,
            datetime(2001, 1, 1): 1,
            datetime(2002, 1, 1): 1}
        # `data` spans 3 years with annual datapoints. Use an interval
        # of 1.5 years to require recalculation. There is only one
        # length 2 sequence of dates covering this period (with dates on
        # 2002-01-01 and 2000-07-01). The exact calculation of returns
        # is an implementation detail, but the total return over the
        # three years should be retained: 800% (i.e. a return of 7).
        interval = dateutil.relativedelta.relativedelta(years=1, months=6)
        sampler = WalkForwardSampler((data,), interval=interval)
        sample = sampler.sample(2)
        returns = sample[0]
        total_return = (1 + returns[0]) * (1 + returns[1]) - 1
        self.assertAlmostEqual(total_return, 7)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

""" Unit tests for `ScenarioSampler`. """

import unittest
from decimal import Decimal
import numpy
from forecaster.scenario import ScenarioSampler, Scenario, ReturnsTuple
from tests.scenario.test_historical_value_reader import (
    PORTFOLIO_VALUES, RETURNS_VALUES,
    TEST_PATH_PERCENTAGES, TEST_PATH_PORTFOLIO)

# Use constant seed for tests that rely on randomness:
RANDOM_TEST = numpy.random.default_rng(0)

class TestScenarioSampler(unittest.TestCase):
    """ A test suite for the `ScenarioSampler` class. """

    def setUp(self):
        # Copy values that get read from the `test_*.csv` files:
        self.values = dict(PORTFOLIO_VALUES)
        self.returns = dict(RETURNS_VALUES)
        self.data = ReturnsTuple(
            self.returns, self.returns, self.returns, self.returns)
        # Read in the same values for each variable:
        self.filenames = ReturnsTuple(
            TEST_PATH_PORTFOLIO, TEST_PATH_PORTFOLIO,
            TEST_PATH_PORTFOLIO, TEST_PATH_PORTFOLIO)
        # Use different values than the defaults so we can check:
        self.initial_year = 2000
        self.num_years = 2
        self.scenario = Scenario(
            self.initial_year, self.num_years, 1, 1, 1, 1, 1)

    def setUp_decimal(self):
        """ Convert numerical values to `Decimal` """
        # pylint: disable=invalid-name
        # `setUp` is the name used by `unittest`, it's not our fault!
        self.values = {
            key: Decimal(value) for (key, value) in self.values.items()}
        self.returns = {
            key: Decimal(value) for (key, value) in self.returns.items()}

class TestScenarioSamplerWF(TestScenarioSampler):
    """ A test suite for walk-forward methods of `ScenarioSampler`. """

    def test_num_samples(self):
        """ Test walk-forward sampler with `num_samples=2` """
        sampler = ScenarioSampler(
            ScenarioSampler.sampler_walk_forward, 2,
            self.scenario, filenames=None)
        sampler.data = self.data  # Use test data
        # Convert to list so we can count scenarios:
        scenarios = list(sampler)
        # There are only two valid walk-forward returns of length 2
        # with this dataset (which has only 3 datapoints)
        self.assertEqual(len(scenarios), 2)

    def test_basic(self, **kwargs):
        """ Test walk-forward sampler scenario generation. """
        # Simplify this test by generating only a single scenario
        # from a dataset where only one scenario is possible
        # by asking for 3-year scenarios from a 3-year dataset:
        self.scenario.num_years = 3
        sampler = ScenarioSampler(
            ScenarioSampler.sampler_walk_forward, 1, self.scenario,
            filenames=None, **kwargs)
        sampler.data = self.data  # Use test data
        expected_returns = {
            key.year: val for (key, val) in self.returns.items()}
        for scenario in sampler:
            # Check values for each of stock/bonds/other/inflation,
            # which all use the same data:
            asset_returns = (
                scenario.stock_return, scenario.bond_return,
                scenario.other_return, scenario.inflation)
            # Confirm that values for each asset class/inflation are
            # walk-forward sequences with the expected values:
            for returns in asset_returns:
                self.assertEqual(returns, expected_returns)

    def test_real(self):
        """ Test walk-forward sampler with real data.

        This is more of an integration test than a unit test. It's
        included (for now) for two reasons. One: It's helpful for
        profiling, as this test provides some insight into bottlenecks.
        Two: Running in non-exponential time is a fairly important
        requirement for this method. Early versions would hang and crash
        on real-world data. After opimization, this test now runs in a
        few seconds - still slow, but tractable.
        """
        num_samples = 1000
        # Omit filenames to load default dataset:
        sampler = ScenarioSampler(
            ScenarioSampler.sampler_walk_forward, 1000, self.scenario,
            # This is the slowest test in the entire project.
            # We can speed things up by using well-formatted data and
            # skipping pre-processing (which is tested elsewhere):
            fast_read=True)
        # If the test doesn't hang here, that's a success!
        # Confirm that the returned values have the structure expected,
        # which is `num_samples` Scenarios:
        scenarios = list(sampler) # Convert to list to count scenarios
        self.assertEqual(len(scenarios), num_samples)

    def test_missing_filename(self):
        """ Test walk-forward sampler with `None` entries in `filenames` """
        self.scenario.num_years = 3
        sampler = ScenarioSampler(
            ScenarioSampler.sampler_walk_forward, 2, self.scenario,
            filenames=(None,)*4)
        for scenario in sampler:
            # all attrs should match the default scenario:
            self.assertEqual(scenario.stock_return, self.scenario.stock_return)
            self.assertEqual(scenario.bond_return, self.scenario.bond_return)
            self.assertEqual(scenario.other_return, self.scenario.other_return)
            self.assertEqual(scenario.inflation, self.scenario.inflation)

    def test_missing_data(self):
        """ Test walk-forward sampler with `None` entries in `data`. """
        self.scenario.num_years = 3
        sampler = ScenarioSampler(
            ScenarioSampler.sampler_walk_forward, 2, self.scenario,
            filenames=None)
        # Use test data that omits some variables:
        data = ReturnsTuple(self.data.stocks, None, None, None)
        sampler.data = data
        expected_stock_returns = {
            key.year: val for (key, val) in self.returns.items()}
        for scenario in sampler:
            # `stocks` shouldn't match the default scenario, but the
            # rest should:
            self.assertEqual(scenario.stock_return, expected_stock_returns)
            self.assertEqual(scenario.bond_return, self.scenario.bond_return)
            self.assertEqual(scenario.other_return, self.scenario.other_return)
            self.assertEqual(scenario.inflation, self.scenario.inflation)

    def test_returns(self):
        """ Test walk-forward sampler with `returns=True` """
        # Use 3 years to simplify testing (only one possible sample):
        self.scenario.num_years = 3
        filenames = (TEST_PATH_PERCENTAGES,)*4
        sampler = ScenarioSampler(
            ScenarioSampler.sampler_walk_forward, 1, self.scenario,
            filenames=filenames, returns=True)
        expected_returns = {
            key.year: val for (key, val) in self.returns.items()}
        for scenario in sampler:
            # Check values for each of stock/bonds/other/inflation,
            # which all use the same data:
            asset_returns = (
                scenario.stock_return, scenario.bond_return,
                scenario.other_return, scenario.inflation)
            # Confirm that values for each asset class/inflation are
            # walk-forward sequences with the expected values:
            for returns in asset_returns:
                self.assertEqual(returns, expected_returns)

    def test_values(self):
        """ Test walk-forward sampler with `returns=False` """
        # Use the same logic as in `test_wf_basic`, but read in a file
        # of portfolio values:
        self.scenario.num_years = 3
        filenames = (TEST_PATH_PORTFOLIO,)*4
        sampler = ScenarioSampler(
            ScenarioSampler.sampler_walk_forward, 1, self.scenario,
            filenames=filenames, returns=False)
        expected_returns = {
            key.year: val for (key, val) in self.returns.items()}
        for scenario in sampler:
            # Check values for each of stock/bonds/other/inflation,
            # which all use the same data:
            asset_returns = (
                scenario.stock_return, scenario.bond_return,
                scenario.other_return, scenario.inflation)
            # Confirm that values for each asset class/inflation are
            # walk-forward sequences with the expected values:
            for returns in asset_returns:
                self.assertEqual(returns, expected_returns)

    def test_decimal(self):
        """ Test Decimal support for walk-forward sampler """
        self.setUp_decimal()
        # We can call `test_wf_basic` directly:
        self.test_basic(high_precision=Decimal)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

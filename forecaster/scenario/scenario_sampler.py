""" Provides a ScenarioSampler class for producing Scenario objects. """

import functools
from forecaster.scenario.historical_return_reader import HistoricalReturnReader
from forecaster.utility.precision import HighPrecisionOptional

DEFAULT_STOCK_FILENAME = 'msci_world.csv'
DEFAULT_BOND_FILENAME = 'treasury_bond_1-3_years.csv'
DEFAULT_OTHER_FILENAME = 'nareit.csv'
DEFAULT_INFLATION_FILENAME = 'inflation.csv'

class ScenarioSampler(HighPrecisionOptional):
    """ A generator for `Scenario` objects.

    Arguments:
        TODO

    Attributes:
        TODO
    """

    def __init__(
            self, sampler, num_samples, scenario_args,
            stock_filename=DEFAULT_STOCK_FILENAME,
            bond_filename=DEFAULT_BOND_FILENAME,
            other_filename=DEFAULT_OTHER_FILENAME,
            inflation_filename=DEFAULT_INFLATION_FILENAME,
            *, high_precision=None, **kwargs):
        super().__init__(high_precision=high_precision, **kwargs)
        # Declare instance variables:
        self.sampler = sampler
        self.num_samples = num_samples
        self.scenario_args = scenario_args
        # Read in historical return/inflation data from CSV files:
        self.stock_returns = HistoricalReturnReader(
            stock_filename, high_precision=high_precision).returns
        self.bond_returns = HistoricalReturnReader(
            bond_filename, high_precision=high_precision).returns
        self.other_returns = HistoricalReturnReader(
            other_filename, high_precision=high_precision).returns
        self.inflation = HistoricalReturnReader(
            inflation_filename, high_precision=high_precision).returns

# TODO: Implement __iter__ to yield num_samples samples, calling
# a method indicated by `sampler`. (Consider borrowing code from
# `StrategyType`/`strategy_method` to create a generic framework
# for registering selectable methods and inherit from that here?)

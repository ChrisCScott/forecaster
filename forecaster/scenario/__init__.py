""" A package for providing scenarios. """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'scenario', 'scenario_sampler', 'samplers',
    'historical_value_reader', 'util'
]

from forecaster.scenario.scenario import Scenario, InflationAdjust
from forecaster.scenario.scenario_sampler import ScenarioSampler
from forecaster.scenario.samplers import MultivariateSampler, WalkForwardSampler
from forecaster.scenario.historical_value_reader import HistoricalValueReader
from forecaster.scenario.util import (
    regularize_returns, return_for_date_from_values, return_over_period,
    returns_for_dates_from_values, values_from_returns, infer_interval)

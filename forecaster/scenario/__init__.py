""" A package for providing scenarios. """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'scenario', 'historical_value_reader'
]

from forecaster.scenario.scenario import Scenario, InflationAdjust
from forecaster.scenario.historical_value_reader import HistoricalValueReader

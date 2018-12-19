""" A package for providing a `Forecast` with various features. """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'base', 'income', 'contribution', 'reduction', 'withdrawal', 'tax'
]

from forecaster.forecast.base import Forecast
from forecaster.forecast.income import IncomeForecast
from forecaster.forecast.contribution import ContributionForecast
from forecaster.forecast.reduction import ReductionForecast
from forecaster.forecast.withdrawal import WithdrawalForecast
from forecaster.forecast.tax import TaxForecast

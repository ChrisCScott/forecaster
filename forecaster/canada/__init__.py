""" Extends ForecastBuilder to process Canadian personal finance data. """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'accounts', 'forecaster', 'settings', 'tax'
]

from forecaster.canada.accounts import (
    RegisteredAccount, RRSP, TFSA, TaxableAccount, PrincipleResidence)
from forecaster.canada.tax import TaxCanada
from forecaster.canada.settings import SettingsCanada
from forecaster.canada.forecaster import ForecastBuilderCanada

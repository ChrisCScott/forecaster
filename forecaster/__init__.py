""" A package for generating forecasts of personal finance data. """

__all__ = [
    'forecaster', 'forecast', 'ledger', 'scenario', 'settings',
    'strategy', 'tax'
]

__version__ = '0.0.1'
__author__ = 'Christopher Scott'
__copyright__ = 'Copyright (C) 2017 Christopher Scott'
__license__ = 'All rights reserved'

from forecaster.ledger import Money
from forecaster.person import Person
from forecaster.scenario import Scenario
from forecaster.accounts import Account, ContributionLimitAccount, Debt
from forecaster.strategy import (
    ContributionStrategy, WithdrawalStrategy, TransactionStrategy,
    AllocationStrategy, DebtPaymentStrategy)
from forecaster.tax import Tax
from forecaster.settings import Settings
from forecaster.forecast import (
    Forecast, SubForecast, IncomeForecast, ContributionForecast,
    ReductionForecast, WithdrawalForecast, TaxForecast)
from forecaster.forecaster import Forecaster

""" A package for generating forecasts of personal finance data. """

__all__ = [
    'forecaster', 'forecast', 'ledger', 'scenario', 'settings',
    'strategy', 'tax'
]

__version__ = '0.0.1'
__author__ = 'Christopher Scott'
__copyright__ = 'Copyright (C) 2019 Christopher Scott'
__license__ = 'All rights reserved'

from forecaster.ledger import (
    Ledger, Money, recorded_property, recorded_property_cached)
from forecaster.person import Person
from forecaster.scenario import Scenario
from forecaster.accounts import (
    Account, LinkedLimitAccount, Debt, AccountLink,
    LimitTuple, LIMIT_TUPLE_FIELDS)
from forecaster.strategy import (
    LivingExpensesStrategy, LivingExpensesStrategySchedule,
    AllocationStrategy, DebtPaymentStrategy,
    TransactionStrategy, TransactionTraversal, TransactionNode,
    AVALANCHE_KEY, SNOWBALL_KEY, PRIORITY_METHODS)
from forecaster.tax import Tax
from forecaster.settings import Settings
from forecaster.forecast import (
    Forecast, SubForecast, IncomeForecast, LivingExpensesForecast,
    SavingForecast, WithdrawalForecast, TaxForecast)
from forecaster.forecaster import ForecastBuilder, Parameter
from forecaster.utility import Timing, transactions_from_timing

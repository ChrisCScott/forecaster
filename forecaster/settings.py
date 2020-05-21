""" This module provides user-modifiable settings for the application.

It provides the `Settings` class, which contains various `*Defaults`
classes. They provide default values for aspects of the application.
"""

import datetime
from typing import Dict, Union
from forecaster.typing import Real, MoneyConvertible


class Settings:
    """ Container for variables used to control application settings.

    This class can be instantiated as an object and, where supported,
    passed to other objects to provide defaults for initialization.
    However, it also provides sensible defaults at the class level, so
    one might equivalently call Settings (the class) or Settings()
    (an object).
    """

    # We use triple-quoted strings as comments to group sets of related
    # settings. It's nice to have a format for heading-style comments
    # that's distinct from #-prefixed comments (which we also use.)
    # pylint: disable=pointless-string-statement
    # Settings is really just a data container right now, but the plan
    # is to encapsulate some file-reading logic.
    # pylint: disable=too-few-public-methods

    # TODO: Read defaults from a file, fall back to the below values
    # where the .ini doesn't provide a value. (This sounds like a good
    # role for an __init__ function...)
    """ Application-level and UI defaults """
    initial_year: int = datetime.datetime.now().year  # Start with this year
    display_year: int = initial_year  # Year for display of real-valued amounts
    currency: str = 'CAD'  # Use Canadian dollars as the default currency

    """ Defaults for `Scenario`  """
    inflation: Real = 0.02
    stock_return: Real = 0.07
    bond_return: Real = 0.04
    other_return: Real = 0.03
    management_fees: Real = 0.005
    num_years: int = 100  # Model this number of years from the initial_year

    ''' LivingExpensesStrategy defaults '''
    living_expenses_strategy: str = 'Constant living expenses'
    living_expenses_base_amount: Real = 60000
    living_expenses_rate: Real = 0.2
    living_expenses_inflation_adjust: bool = True

    ''' SavingStrategy defaults '''
    saving_strategy: str = "Ordered"
    saving_weights: Dict[str, Real] = {"Account": 1}

    ''' WithdrawalStrategy defaults '''
    withdrawal_strategy: str = "Ordered"
    withdrawal_weights: Dict[str, Real] = {"Account": 1}

    ''' AllocationStrategy defaults '''
    allocation_strategy: str = 'n-age'
    allocation_min_equity: Real = 0.3
    allocation_max_equity: Real = 0.3
    allocation_std_retirement_age: int = 65
    allocation_target: int = 65
    allocation_risk_trans_period: int = 20
    allocation_adjust_retirement: bool = True

    ''' DebtPaymentStrategy defaults '''
    debt_payment_strategy: str = 'Avalanche'

    ''' Tax defaults '''
    tax_brackets: Dict[int, Dict[MoneyConvertible, Real]] = {
        initial_year: {0: 0}}
    tax_personal_deduction: Dict[int, MoneyConvertible] = {initial_year: 0}
    tax_credit_rate: Dict[int, Real] = {initial_year: 0}
    tax_payment_timing: Union[str, Real] = 'start'

""" This module provides user-modifiable settings for the application.

It provides the `Settings` class, which contains various `*Defaults`
classes. They provide default values for aspects of the application.
"""

import datetime
from decimal import Decimal


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
    initial_year = datetime.datetime.now().year  # Model starts with this year
    display_year = initial_year  # Base year for displaying real-valued amounts
    currency = 'CAD'  # Use Canadian dollars as the default currency

    """ Defaults for `Scenario`  """
    inflation = 0.02
    stock_return = 0.07
    bond_return = 0.04
    other_return = inflation + 0.01
    management_fees = 0.005
    num_years = 100  # Model this number of years from the initial_year

    ''' LivingExpensesStrategy defaults '''
    living_expenses_strategy = 'Constant living expenses'
    living_expenses_base_amount = Decimal('60000')
    living_expenses_rate = Decimal('0.2')
    living_expenses_inflation_adjust = True

    ''' ContributionStrategy defaults '''
    contribution_strategy = 'Ordered'
    contribution_weights = {'Account': 1}
    contribution_timing = 'end'

    ''' WithdrawalStrategy defaults '''
    withdrawal_strategy = 'Ordered'
    withdrawal_weights = {'Account': 1}
    withdrawal_timing = 'end'

    ''' AllocationStrategy defaults '''
    allocation_strategy = 'n-age'
    allocation_min_equity = Decimal('0.3')
    allocation_max_equity = Decimal('0.3')
    allocation_std_retirement_age = 65
    allocation_target = 65
    allocation_risk_trans_period = 20
    allocation_adjust_retirement = True

    ''' DebtPaymentStrategy defaults '''
    debt_payment_strategy = 'Avalanche'
    debt_payment_timing = 'end'

    ''' Tax defaults '''
    tax_brackets = {Decimal(0): Decimal(0)}
    tax_personal_deduction = Decimal(0)
    tax_credit_rate = Decimal(0)
    tax_payment_timing = 'start'

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
    num_children = 3  # How many children may be represented
    currency = 'CAD'  # Use Canadian dollars as the default currency

    """ Defaults for `Scenario`  """
    inflation = 0.02
    stock_return = 0.07
    bond_return = 0.04
    other_return = inflation + 0.01
    management_fees = 0.005
    num_years = 100  # Model this number of years from the initial_year

    """ Defaults for `Person` instances. """
    person1_name = 'Person 1'
    person1_birth_date = '1 January 1980'
    person1_retirement_date = '31 December 2045'
    person1_gross_income = Decimal('50000')
    person1_raise_rate = inflation + 0.01
    person2_name = None
    person2_birth_date = None
    person2_retirement_date = None
    person2_gross_income = None
    person2_raise_rate = None

    ''' ContributionStrategy defaults '''
    contribution_strategy = 'Percentage of net income'
    contribution_base_amount = Decimal('20000')
    contribution_rate = Decimal('0.2')
    contribution_reinvestment_rate = 1
    contribution_inflation_adjusted = True

    ''' TransactionStrategy defaults for inflows/contributions '''
    transaction_in_strategy = 'Ordered'
    transaction_in_weights = {'Account': 1}
    transaction_in_timing = 'end'

    ''' WithdrawalStrategy defaults '''
    withdrawal_strategy = 'Constant withdrawal'
    withdrawal_base_amount = Decimal('100000')
    withdrawal_rate = Decimal('0.04')
    withdrawal_income_adjusted = True
    withdrawal_inflation_adjusted = True

    ''' TransactionStrategy defaults for outflows/withdrawals '''
    transaction_out_strategy = 'Ordered'
    transaction_out_weights = {'Account': 1}
    transaction_out_timing = 'end'

    ''' AllocationStrategy defaults '''
    allocation_strategy = 'n-age'
    allocation_min_equity = Decimal('0.3')
    allocation_max_equity = Decimal('0.3')
    allocation_std_retirement_age = 65
    allocation_const_target = 65
    allocation_trans_target = Decimal('0.5')
    allocation_risk_trans_period = 20
    allocation_adjust_retirement = True

    ''' DebtPaymentStrategy defaults '''
    debt_payment_strategy = 'Avalanche'
    debt_payment_timing = 'end'

    ''' Debt defaults '''
    debt_savings_rate = 1
    debt_accelerated_payment = 0

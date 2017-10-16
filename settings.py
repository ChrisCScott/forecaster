""" This module provides user-modifiable settings for the application.
It provides the `Settings` class, which contains various `*Defaults`
classes. They provide default values for aspects of the application. """
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
    # TODO: Read defaults from a file, fall back to the below values
    # where the .ini doesn't provide a value. (This sounds like a good
    # role for an __init__ function...)
    initial_year = datetime.datetime.now().year  # Model starts with this year
    display_year = initial_year  # Base year for displaying real-valued amounts
    num_years = 100  # Model this number of years from the initial_year
    num_children = 3  # How many children may be represented
    currency = 'CAD'  # Use Canadian dollars as the default currency

    """ Defaults for `Scenario`  """
    inflation = 0.02
    stock_return = 0.07
    bond_return = 0.04
    other_return = inflation + 0.01
    management_fees = 0.005
    person1_raise_rate = inflation + 0.01
    person2_raise_rate = inflation + 0.01

    """ Defaults for `Strategy` instances. """
    # TODO: update to match an actual Person data model
    person1_name = 'Person 1'
    person1_birth_date = datetime.datetime.now().replace(
        year=datetime.datetime.now().year-30)
    person1_retirement_date = 65
    person2_name = 'Person 2'
    person2_birth_date = datetime.datetime.now().replace(
        year=datetime.datetime.now().year-30)
    person2_retirement_date = 65

    ''' ContributionStrategy defaults '''
    contribution_strategy = 'Percentage of net income'
    contribution_rate = Decimal('0.2')
    contribution_refund_reinvestment_rate = 1
    contribution_inflation_adjusted = True

    ''' TransactionStrategy defaults for inflows/contributions '''
    transaction_in_strategy = 'Ordered'
    transaction_in_weights = {
        'RRSP': 1, 'TFSA': 2, 'SavingsAccount': 3
        }
    transaction_in_timing = 'end'

    ''' WithdrawalStrategy defaults '''
    # TODO: Update to correspond to WithdrawalStrategy implementation
    withdrawal_strategy = 'Constant withdrawal'
    withdrawal_rate = Money('100000')
    withdrawal_min_living_standard = Money('50000')
    withdrawal_inflation_adjusted = True

    ''' TransactionStrategy defaults for outflows/withdrawals '''
    transaction_out_strategy = 'Ordered'
    transaction_out_weights = {
        'RRSP': 1, 'TFSA': 2, 'SavingsAccount': 3
        }
    transaction_out_timing = 'end'

    ''' AllocationStrategy defaults '''
    allocation_strategy = 'n-age'
    allocation_min_equity = Decimal('0.3')
    allocation_max_equity = Decimal('0.3')
    allocation_standard_retirement_age = 65
    allocation_constant_strategy_target = 65
    allocation_transition_strategy_target = Decimal('0.5')
    allocation_risk_transition_period = 20
    allocation_adjust_for_early_retirement = True

""" This module provides user-modifiable settings for the application.
It provides the `Settings` class, which contains various `*Defaults`
classes. They provide default values for aspects of the application. """
import datetime
from moneyed import Currency


class Settings:
    """ Container for variables used to control application settings """
    initial_year = datetime.datetime.now().year  # Model starts with this year
    display_year = initial_year  # Base year for displaying real-valued amounts
    num_years = 100  # Model this number of years from the initial_year
    num_children = 3  # How many children may be represented
    currency = Currency("CAD")

    # TODO: Replace these with an instance of `Scenario`, etc.?
    class ScenarioDefaults:
        """ Defaults for `Scenario`  """
        inflation = 0.02
        stock_return = 0.07
        bond_return = 0.04
        other_return = inflation + 0.01
        management_fees = 0.005
        raise_rate = inflation + 0.01

    class StrategyDefaults:
        """ Defaults for `Strategy` instances. """
        # TODO: update to match an actual contribution strategy
        contribution_rate_strategy = 1
        contribution_rate = 0.5
        # TODO: update to match an actual allocation strategy
        allocation_model = 1
        adjust_allocation_for_early_retirement = True
        refund_reinvestment_rate = 1

        # TODO: update to match an actual withdrawal strategy
        withdrawal_strategy = 2
        withdrawal_rate = 100000

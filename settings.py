''' This module provides the `Settings` class, which provides user-modifiable settings
for the application '''
import datetime
import locale

locale.setlocale(locale.LC_ALL, '') # Set the locale to the system default

class Settings:
    ''' Provides a container for global variables used to control application settings '''
    initial_year = datetime.datetime.now().year # The model starts with this year
    display_year = initial_year # Determines the year in which real-valued amounts are expressed
    num_years = 100 # Model this number of years from the initialYear
    num_children = 3 # How many children may be represented

    class ScenarioDefaults:
        ''' Defaults for `Scenario`  '''
        inflation = 0.02
        stock_return = 0.07
        bond_return = 0.04
        other_return = inflation + 0.01
        management_fees = 0.005
        raise_rate = inflation + 0.01

    class StrategyDefaults:
        ''' Defaults for `Strategy` instances. '''
        contribution_rate_strategy = 1 # TODO: update to match an actual contribution strategy
        contribution_rate = 0.5
        allocation_model = 1 # TODO: update to match an actual allocation strategy
        adjust_allocation_for_early_retirement = True
        refund_reinvestment_rate = 1

        withdrawal_strategy = 2 # TODO: update to match an actual withdrawal strategy
        withdrawal_rate = 100000

    # locale-specific settings are supported in the following code

    @staticmethod
    def setlocale(locale_):
        ''' Sets the locale for currency and date formatting '''
        locale.setlocale(locale_)

    @staticmethod
    def getavailablelocales():
        ''' Provides a dictionary of locales installed on the local machine '''
        ''' NOTE: There are several issues with this. First, locale.locale_alias does
        not necessarily contain all available locales. Second, some "installed" locales
        may not be fully installed by the system (which may result in an error).
        Third, locale names are OS-dependent; for Windows, these locale names may not
        work (and it may be necessary to translate them to forms provided via MSDN).
        See here for more info:
        https://stackoverflow.com/questions/19709026/how-can-i-list-all-available-windows-locales-in-python-console ''' # pylint: disable=line-too-long
        return locale.locale_alias

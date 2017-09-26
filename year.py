''' This module provides a Year class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
'''

from scenario import Scenario
from strategy import Strategy


class Year(object):
    ''' A year in a multi-year forecast.

    A Year object contains various Account balances. It manages inflows
    to and outflows from (or between) accounts based on Strategy and
    Scenario information.

    Attributes:
        people (list): The people for whom the financial forecast is
            being generated. May be either 1 or 2 married people.
            The purpose of the two-person constraint is to allow for
            the modelling of certain spousal tax credits and account
            options. If you want to model unmarried people or more than
            2 people, build multiple Year objects.
        gross_income (Money): 
        net_income (Money): 
        gross_contribution (Money): 
        contribution_reduction (Money): 
        net_contribution (Money):
        contributions (dict): 
        withdrawals_total (Money): 
        withdrawals (dict): 
        benefits_total (Money): 
        benefits (dict): 
        tax_owed (Money): 
        tax_carryforward (Money): 
        tax_paid (Money): 
        savings_accounts (list): 
        debts (list): 
    '''

    def __init__(self, last_year=None, scenario=None, strategy=None,
                 inputs=None):
        ''' Constructs an instance of class Year.

        Args:
            last_year (Year): The previous year, used to initialize account
                balances and carry forward tax information.
                May be None (generally when constructing the first year)
            scenario (Scenario): Economic information for the year (e.g.
                inflation and stock market returns)
            strategy (Strategy): Defines the behaviour of the investor, such
                as their approach to making contributions or withdrawals,
                and asset allocation/investment choices.
            inputs (InputYear): Any values provided in this InputYear
                will override any projection logic (i.e. the
                corresponding values of last_year will be ignored).
                This is useful to mapping out specific plans (e.g.
                taking a leave from work, buying a home) or for
                providing the initial conditions for the first year.
                Optional.
                If `last_year` is None, all values not provided by
                `inputs` will be initialized to the value provided by
                `settings` (where possible), set to 0 (for balances), or
                based on default tax rules assuming no prior activity
                (for RRSP/TFSA/RESP contribution room, CPP, etc.).
        '''
        self.last_year = last_year
        self.scenario = scenario

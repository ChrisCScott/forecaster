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

    The Year object is built around either a single person or a family.
    The reason for this is that married people have specific tax
    treatment.

    Attributes:
        person1 (Person): A person for whom the financial forecast is
            being generated.
        person2 (Person): The spouse of person1. Optional.
        person1_gross_income (Money): The gross income of person1.
        person2_gross_income (Money): The gross income of person2.
            Optional.
        gross_income (Money): The gross income for the family.
        net_income (Money): The net income for the family.
        gross_contribution (Money): The amount available to contribute
            to savings, before any reductions. This is drawn from
            net income and inter-year rollovers.
        contribution_reduction (Money): Amounts diverted from savings,
            such as certain debt repayments or childcare.
        contributions_total (Money): The total amount contributed to
            savings.
        contributions (dict): The contributions to each account, stored
            as {Account: Money} pairs.
        withdrawals_total (Money): The total amount withdrawn from
            savings.
        withdrawals (dict): The withdrawals from each account, stored
            as {Account: Money} pairs.
        benefits_total (Money): The total amount of benefits recieved.
        benefits (dict): The benefits received from each source, stored
            as {Benefit: Money} pairs.
        tax_owed (Money): The amount of tax owed on income for this year
        tax_paid (Money): The amount of tax paid this year. This
            includes withholding taxes and payments of the previous
            year's carryforward.
        tax_carryforward (Money): The amount of tax remaining unpaid
            from this year (to be paid next year).
        savings_accounts (list): All savings accounts.
        debts (list): All debts.
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

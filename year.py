''' This module provides a Year class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
'''

from scenario import Scenario
from strategy import Strategy
from settings import Settings


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
        contribution_strategy (ContributionStrategy): TODO
        withdrawal_strategy (WithdrawalStrategy): TODO
        contribution_transaction_strategy (TransactionStrategy): TODO
        withdrawal_transaction_strategy (WithdrawalTransactionStrategy): TODO
        allocation_strategy (AllocationStrategy): TODO
        person1_gross_income (Money): The gross income of person1.
        person1_tax_payable (Money): The taxes payable on the income of
            person1.
        person2_gross_income (Money): The gross income of person2.
            Optional.
        person2_tax_payable (Money): The taxes payable on the income of
            person1. Optional.
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
    # TODO: Redesign this class to be "Forecast", turn all Money-class
    # objects into dicts. Otherwise the overall logic is basically the
    # same. (Note that Account objects are getting a similar overhaul)

    def __init__(self, last_year=None, scenario=None, strategy=None,
                 inputs=None, settings=Settings):
        ''' Constructs an instance of class Year.

        Starts with the end-of-year values from `last_year` and builds
        out another year. Generally, if `last_year` is provided, the
        same `scenario`, `strategy`, and `settings` values will be used
        (although it is possible to explicitly provide new ones if you
        want.)

        Any values in `inputs` will override values in any other
        argument. Thus, the order of precedence is `inputs` >
        `scenario`, `strategy`, `settings` > `last_year`.

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
                This is useful for mapping out specific plans (e.g.
                taking a leave from work, buying a home) or for
                providing the initial conditions for the first year.
                Optional.
                If `last_year` is None, all values not provided by
                `inputs` will be initialized to the value provided by
                `settings` (where possible), set to 0 (for balances), or
                based on default tax rules assuming no prior activity
                (for RRSP/TFSA/RESP contribution room, CPP, etc.).
            settings (Settings): A settings object to provide various
                default values/behaviours. Optional.
        '''
        self.last_year = last_year

        # Initialize settings/scenario/strategy attributes based on the
        # order of precedence explicit argument > last_year attribute >
        # default value (according to the settings object, if provided.)
        if settings is not None:
            self.settings = settings
        elif last_year is not None:
            self.settings = last_year.settings
        else:
            self.settings = Settings()

        if scenario is not None:
            self.scenario = scenario
        elif last_year is not None:
            self.scenario = last_year.scenario
        else:
            self.scenario = Scenario(settings=self.settings)

        if strategy is not None:
            self.strategy = strategy
        elif last_year is not None:
            self.strategy = last_year.strategy
        else:
            self.strategy = Strategy(settings=self.settings)

        # TODO: Test whether person1 is retired and use this to
        # determine whether any employment income should be generated.
        # NOTE: The people are defined in the Strategy object, not
        # last_year. Check strategy to see whether person2 is defined.
        pass

    @staticmethod
    def personal_gross_income(person, income, raise_rate,
                              retired=False):
        """ The gross rate of income for this year, after raises.

        Args:
            person (Person): The person.
                If None, this method returns None.
            income (Money): The person's income for last year.
            raise_rate (Decimal): The person's raise for this year, as a
                percentage (e.g. a 3% raise is `Decimal(0.03)`)
            retired (bool): True if the person is retired
        """
        # TODO: Consider adding a semi-retired status? Income could be
        # reduced and constant in real terms (i.e. raises = inflation).
        # This would require adding a scenario or inflation term.
        if person is None:
            return None
        if retired:
            return Money(0)
        return income * (1 + raise_rate)

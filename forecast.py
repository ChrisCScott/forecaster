''' This module provides a Forecast class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
'''

from scenario import Scenario
from strategy import Strategy
from settings import Settings


class Forecast(object):
    ''' A financial forecast spanning multiple years.

    A `Forecast` contains various `Account`s with balances that grow
    (or shrink) from year to year. The `Forecast` object also contains
    `Person` objects describing the plannees, `Scenario` information
    describing economic conditions over the course of the forecast, and
    `Strategy` objects to describe the plannee's behaviour.

    The `Forecast` manages inflows to and outflows from (or between)
    accounts based on `Strategy` and `Scenario` information.

    The `Forecast` is built around either a single person or a spousal
    couple (since spouses have specific tax treatment).

    Attributes:
        person1 (Person): A person for whom the financial forecast is
            being generated.
        person2 (Person): The spouse of person1. Optional.
        contribution_strategy (ContributionStrategy): TODO
        withdrawal_strategy (WithdrawalStrategy): TODO
        contribution_transaction_strategy (TransactionStrategy): TODO
        withdrawal_transaction_strategy (WithdrawalTransactionStrategy): TODO
        allocation_strategy (AllocationStrategy): TODO

        TODO: Move the below to `Person`?
        person1_gross_income (Money): The gross income of person1.
        person1_tax_payable (Money): The taxes payable on the income of
            person1.
        person2_gross_income (Money): The gross income of person2.
            Optional.
        person2_tax_payable (Money): The taxes payable on the income of
            person1. Optional.
        gross_income (dict): The gross income for the family, as
            {year: Money} pairs.
        net_income (dict): The net income for the family, as
            {year: Money} pairs.
        gross_contribution (dict): The amount available to contribute
            to savings, before any reductions, as {year: Money} pairs.
            This is drawn from net income and inter-year rollovers.
        contribution_reduction (dict): Amounts diverted from savings,
            such as certain debt repayments or childcare, as
            {year: Money} pairs.
        contributions (Money): The total amount contributed to savings
            accounts, as {year, Money} pairs.
        withdrawals (dict): The total amount withdrawn from savings
            accounts, as {year, Money} pairs.
        benefits (dict): The total amount of benefits recieved,
            as {year: Money} pairs.
        tax_payable (dict): The amount of tax owed on income for each
            year, as {year: Money} pairs.
        tax_withheld (dict): The amount of tax withheld on income each
            year, as {year: Money} pairs.
        tax_carryforward (dict): The amount of tax remaining unpaid
            from each year (to be paid in the next year), as
            {year: Money} pairs.
        assets (list): All savings accounts, residences, etc. (all of
            which must be subclasses of `Account`)
        debts (list): All debts (all of which must be `Debt` accounts or
            subclasses thereof).
    '''
    # TODO: Consider how to implement benefits/tax logic - should these
    # be built by the Forecast? Passed as inputs?

    def __init__(self, assets=None, debts=None, scenario=None,
                 strategy=None,
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
        TODO: Update this documentation
            assets (iterable): A set/list/etc. of Account objects.
            debts (iterable): A set/list/etc. of Debt objects.
            scenario (Scenario): Economic information for the year (e.g.
                inflation and stock market returns)
            contribution_strategy (ContributionStrategy): TODO
            withdrawal_strategy (WithdrawalStrategy): TODO
            contribution_transaction_strategy (TransactionStrategy): TODO
            withdrawal_transaction_strategy (WithdrawalTransactionStrategy): TODO
            allocation_strategy (AllocationStrategy): TODO
            strategy (Strategy): Defines the behaviour of the investor, such
                as their approach to making contributions or withdrawals,
                and asset allocation/investment choices.
            inputs (InputYear): Any values provided in this `InputYear`
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

    # TODO: Implement this in `Person`
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

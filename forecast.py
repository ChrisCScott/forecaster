''' This module provides a Forecast class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
'''

from scenario import *
from strategy import *
from ledger import *
from tax import *


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
        people (iterable): One or more `Person` objects for whom the
            financial forecast is being generated. Typically a single
            person or a person and their spouse.
        assets (iterable): A set/list/etc. of `Account` objects.
            All Person objects, assets, and debts must have the same
            `this_year` attribute.
        debts (iterable): A set/list/etc. of `Debt` objects.
            All Person objects, assets, and debts must have the same
            `this_year` attribute.

        scenario (Scenario): Economic information for the forecast
            (e.g. inflation and stock market returns for each year)

        contribution_strategy (ContributionStrategy): A callable
            object that determines the gross contribution for a
            year. See the documentation for `ContributionStrategy` for
            acceptable args when calling this object.
        withdrawal_strategy (WithdrawalStrategy): A callable
            object that determines the amount to withdraw for a
            year. See the documentation for `WithdrawalStrategy` for
            acceptable args when calling this object.
        contribution_transaction_strategy (TransactionStrategy): A
            callable object that determines the schedule of
            transactions for any contributions during the year.
            See the documentation for `TransactionStrategy` for
            acceptable args when calling this object.
        withdrawal_transaction_strategy
            (WithdrawalTransactionStrategy):
            A callable object that determines the schedule of
            transactions for any contributions during the year.
            See the documentation for `TransactionStrategy` for
            acceptable args when calling this object.
        allocation_strategy (AllocationStrategy): A callable object
            that determines the allocation of stocks vs. bonds for
            a given year. See the documentation for
            `AllocationStrategy` for acceptable args when calling this
            object.

        tax_treatment (Tax): A callable object that determines the total
            amount of tax owing in a year. See the documentation for
            `Tax` for acceptable args when calling this object.

        gross_income (dict): The gross income for the family, as
            {year: Money} pairs.
        taxes_withheld_on_income (dict): Taxes deducted at source (or
            paid by installment during the year) on employment income.
        net_income (dict): The net income for the family, as
            {year: Money} pairs.

        contributions_from_income (dict): The amount to be contributed
            to savings from employment income in each year, as
            {year: Money} pairs.
        contributions_from_carryover (dict): The amount to be
            contributed to savings from inter-year carryovers (e.g. tax
            refunds, recontributing excess withdrawals, etc.), as
            {year: Money} pairs.
        contributions_from_asset_sales (dict): The amount to be
            contributed to savings from asset sales in each year, as
            {year: Money} pairs.
        gross_contributions (dict): The amount available to contribute
            to savings, before any reductions, as {year: Money} pairs.
            This is the sum of net income and the various
            contributions_from_* values.
        reduction_from_debt (dict): The amount to be diverted from
            contributions to debt repayment in each year, as
            {year: Money} pairs.
        reduction_from_other (dict): The amount to be diverted from
            contributions for other spending purposes in each year, as
            {year: Money} pairs.
        contribution_reductions (dict): Amounts diverted from savings,
            such as certain debt repayments or childcare, as
            {year: Money} pairs.
        net_contributions (dict): The total amount contributed to
            savings accounts, as {year, Money} pairs.

        principal (dict): The total value of all savings accounts (but
            not other property) at the start of each year, as
            {year: Money} pairs.
        gross_return (dict): The total return on principal (only for the
            amounts included in `principal`) by the end of the year, as
            {year: Money} pairs.
        tax_withheld_on_return (dict): Taxes deducted at source
            on the returns on investments, as {year: Money} pairs.
        net_return (dict): The total return on principal (only for the
            amounts included in `principal`) by the end of the year, net
            of withholding taxes, as {year: Money} pairs.

        withdrawals_from_retirement_accounts (dict): The total value of
            all withdrawals from retirement savings accounts over the
            year, as {year: Money} pairs.
        withdrawals_from_other_accounts (dict): The total value of all
            withdrawals from other savings accounts (e.g. education or
            health accounts, if provided) over the year, as
            {year: Money} pairs.
        gross_withdrawals (dict): The total amount withdrawn from all
            accounts, as {year, Money} pairs.
        tax_withheld_on_withdrawals (dict): Taxes deducted at source
            on withdrawals from savings, as {year: Money} pairs.
        net_withdrawals (dict): The total amount withdrawn from all
            accounts, net of withholding taxes, as {year, Money} pairs.

        total_tax_withheld (dict): The total amount of tax owing for
            this year which was paid during this year (as opposed to
            being paid in the following year the next year).
            Note that this is not necessarily the same as the sum of
            other `tax_withheld_on_*` attributes, since the tax
            authority may require additional withholding taxes (or
            payment by installments) based on the person's overall
            circumstances.
        total_tax_owing (dict): The total amount of tax owing for this
            year (some of which may be paid in the following year). Does
            not include outstanding amounts which became owing but were
            not paid in the previous year.

        living_standard (dict): The total amount of money available for
            spending, net of taxes, contributions, debt payments, etc.
    '''
    # TODO (v2): Implement benefits logic.

    def __init__(self, people, assets, debts, scenario, contribution_strategy,
                 withdrawal_strategy, contribution_transaction_strategy,
                 withdrawal_transaction_strategy, allocation_strategy,
                 tax_treatment, inputs=None, display_year=None):
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
            people (iterable): A set/list/etc. of Person objects.
                All Person objects, assets, and debts must have the same
                `this_year` attribute.
            assets (iterable): A set/list/etc. of Account objects.
                All Person objects, assets, and debts must have the same
                `this_year` attribute.
            debts (iterable): A set/list/etc. of Debt objects.
                All Person objects, assets, and debts must have the same
                `this_year` attribute.
            scenario (Scenario): Economic information for the forecast
                (e.g. inflation and stock market returns for each year)
            contribution_strategy (ContributionStrategy): A callable
                object that determines the gross contribution for a
                year. See the documentation for ContributionStrategy for
                acceptable args when calling this object.
            withdrawal_strategy (WithdrawalStrategy): A callable
                object that determines the amount to withdraw for a
                year. See the documentation for WithdrawalStrategy for
                acceptable args when calling this object.
            contribution_transaction_strategy (TransactionStrategy): A
                callable object that determines the schedule of
                transactions for any contributions during the year.
                See the documentation for TransactionStrategy for
                acceptable args when calling this object.
            withdrawal_transaction_strategy
                (WithdrawalTransactionStrategy):
                A callable object that determines the schedule of
                transactions for any contributions during the year.
                See the documentation for TransactionStrategy for
                acceptable args when calling this object.
            allocation_strategy (AllocationStrategy): A callable object
                that determines the allocation of stocks vs. bonds for
                a given year. See the documentation for
                AllocationStrategy for acceptable args when calling this
                object.
            tax_treatment (Tax): A callable object that determines the
                total amount of tax owing in a year. See documentation
                for `Tax` for acceptable args when calling this object.
            inputs (dict): A dict of `{object: {year: input}}` pairs,
                where `object` is an object with a `next_year` method
                (e.g. a `Person` or `Account`) and `input` is a dict of
                keywords args that is passed to next_year as `**input`.
                Optional.

                The keys in `input` are attributes of the object and
                the values are inputs (e.g. Money or Decimal objects)
                that override any projection logic.

                These values are applied to the next year. This is
                useful for mapping out specific plans (e.g. taking a
                leave from work, buying a home) or for providing the
                initial conditions for the first year.
        '''
        # Store input values
        self.people = people
        self.assets = assets
        self.debts = debts
        self.scenario = scenario
        self.contribution_strategy = contribution_strategy
        self.withdrawal_strategy = withdrawal_strategy
        self.contribution_transaction_strategy = \
            contribution_transaction_strategy
        self.withdrawal_transaction_strategy = withdrawal_transaction_strategy
        self.allocation_strategy = allocation_strategy
        self.tax_treatment = tax_treatment
        self.inputs = inputs

        # Prepare output dicts:
        self.gross_income = {}
        self.taxes_withheld_on_income = {}
        self.net_income = {}

        self.contributions_from_income = {}
        self.contributions_from_carryover = {}
        self.contributions_from_asset_sales = {}
        self.gross_contributions = {}
        self.reduction_from_debt = {}
        self.reduction_from_other = {}
        self.contribution_reductions = {}
        self.net_contributions = {}

        self.principal = {}
        self.gross_return = {}
        self.tax_withheld_on_return = {}
        self.net_return = {}

        self.withdrawals_from_retirement_accounts = {}
        self.withdrawals_from_other_accounts = {}
        self.gross_withdrawals = {}
        self.tax_withheld_on_withdrawals = {}
        self.net_withdrawals = {}

        self.total_tax_withheld = {}
        self.total_tax_owing = {}

        self.living_standard = {}

        # Record the values for the initial year:
        self.record_year()

        # Build the forecast year-by-year:
        for year in self.scenario:
            self.next_year()
            self.record_year(year)

    def next_year(self):
        """ Adds a year to the forecast. """
        # TODO
        pass

    def record_year(self, year):
        """ Stores high-level values across accounts for this year."""
        self.gross_income[year] = sum(
            person.gross_income for person in self.people)
        self.taxes_withheld_on_income[year] = sum(
            person.tax_withheld for person in self.people)
        self.net_income[year] = sum(
            person.net_income for person in self.people)

        # TODO: Determine refunds and other contributions
        self.contributions_from_income[year] = self.contribution_strategy(
            refund=0, other_contributions=0, net_income=self.net_income[year],
            gross_income=self.gross_income[year],
            inflation_adjustment=self.scenario.inflation_adjustment()
        )
        self.contributions_from_carryover[year] = 
        self.contributions_from_asset_sales[year] = 
        self.gross_contributions[year] = 
        self.reduction_from_debt[year] = 
        self.reduction_from_other[year] = 
        self.contribution_reductions[year] = 
        self.net_contributions[year] = 

        self.principal[year] = 
        self.gross_return[year] = 
        self.tax_withheld_on_return[year] = 
        self.net_return[year] = 

        self.withdrawals_from_retirement_accounts[year] = 
        self.withdrawals_from_other_accounts[year] = 
        self.gross_withdrawals[year] = 
        self.tax_withheld_on_withdrawals[year] = 
        self.net_withdrawals[year] = 

        self.total_tax_withheld[year] = 
        self.total_tax_owing[year] = 

        self.living_standard[year] = 

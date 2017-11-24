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
        debt_payment_strategy (DebtPaymentStrategy): A callable object
            that determines the schedule of debt payments, including
            accelerated debt payments drawn from gross contributions.
            See the documentation for `DebtPaymentStrategy` for
            acceptable args when calling this object.

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

    def __init__(self, people, assets, debts, scenario, contribution_strategy,
                 withdrawal_strategy, contribution_transaction_strategy,
                 withdrawal_transaction_strategy, allocation_strategy,
                 debt_payment_strategy, tax_treatment, inputs=None):
        ''' Constructs an instance of class Forecast.

        Iteratively advances `people`, `assets`, and `debts` to the next
        year until all years of the `scenario` have been modelled.

        Any values in `inputs` will be passed to the associated object's
        next_year method as an `inputs` keyword argument. This will
        cause the object to override the value of the corresponding
        property in that year.

        Example:
            `inputs = {account: {2000: {'balance': 0}}}`
            `account.next_year(inputs[account])`
            If `account.this_year` is advanced from `1999` to `2000` by
            `next_year`, `account.balance` will be $0 for the year 2000
            regardless of its balance or other activity in 1999.

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
            debt_payment_strategy (DebtPaymentStrategy): A callable
                object that determines the schedule of debt payments,
                including accelerated debt payments drawn from gross
                contributions. See the documentation for
                `DebtPaymentStrategy` for acceptable args when calling
                this object.
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
        self.debt_payment_strategy = debt_payment_strategy
        self.tax_treatment = tax_treatment
        self.inputs = inputs

        # Prepare output dicts:
        # Income
        self.gross_income = {}
        self.taxes_withheld_on_income = {}
        self.net_income = {}

        # Gross contribution
        self.refund = {}
        self.carryover = {}
        self.asset_sale = {}
        self.gross_contributions = {}

        # Contribution reductions
        self.reduction_from_debt = {}
        self.reduction_from_other = {}
        self.contribution_reductions = {}
        self.net_contributions = {}

        # Principal (and return on principal)
        self.principal = {}
        self.gross_return = {}
        self.tax_withheld_on_return = {}
        self.net_return = {}

        # Withdrawals
        self.withdrawals_from_retirement_accounts = {}
        self.withdrawals_from_other_accounts = {}
        self.gross_withdrawals = {}
        self.tax_withheld_on_withdrawals = {}
        self.net_withdrawals = {}

        # Total tax
        self.total_tax_withheld = {}
        self.total_tax_owing = {}

        # Living standard
        self.living_standard = {}

        # Record the values for the initial year:
        self.record_year(scenario.initial_year)

        # Build the forecast year-by-year:
        for year in self.scenario:
            self.next_year()
            self.record_year(year)

    def next_year(self):
        """ Adds a year to the forecast. """
        for person in self.people:
            person.next_year()

        for account in self.assets:
            account.next_year()

        for account in self.debts:
            account.next_year()

    def record_income(self, year):
        # Determine gross/net income for the family:
        self.gross_income[year] = sum(
            person.gross_income for person in self.people)
        self.taxes_withheld_on_income[year] = sum(
            person.tax_withheld for person in self.people)
        self.net_income[year] = sum(
            person.net_income for person in self.people)

    def record_gross_contribution(self, year):
        # TODO: Determine refunds and other contributions
        # Determine gross contributions:
        self.refund[year] = 0  # TODO: refund amounts
        self.carryover[year] = 0  # TODO
        self.asset_sale[year] = 0  # TODO
        self.gross_contributions[year] = self.contribution_strategy(
            year=year,
            refund=self.refund[year],
            other_contributions=self.carryover[year] + self.asset_sale[year],
            net_income=self.net_income[year],
            gross_income=self.gross_income[year]
        )

    def record_contribution_reductions(self, year):
        # Determine contribution reductions:
        # TODO: Include reduced contributions to pay for last year's
        # outstanding taxes?
        # NOTE: We'll add another reduction dict for childcare expenses
        # in a future version.
        # First determine miscellaneous other reductions (these take
        # priority because they're generally user-input):
        self.reduction_from_other[year] = 0
        # Then determine reductions due to debt payments:
        debt_payments = self.debt_payment_strategy(
            self.gross_contributions[year] - self.reduction_from_other[year],
            self.debts
        )
        self.reduction_from_debt[year] = sum(
            debt_payments[debt] * debt.reduction_rate for debt in debt_payments
        )
        # Now determine the total reductions across all reduction dicts:
        self.contribution_reductions[year] = (
            self.reduction_from_debt[year] +
            self.reduction_from_other[year]
        )

        # Apply debt payment transactions
        for debt in debt_payments:
            debt.add_transaction(
                debt_payments[debt],
                self.debt_payment_strategy.timing
            )

    def record_net_contributions(self, year):

        # Reductions can potentially exceed gross_contributions (e.g.
        # due to minimum debt payments or childcare expenses).
        # Ensure the net_contributions is not negative:
        self.net_contributions[year] = max(
            self.gross_contributions[year] -
            self.contribution_reductions[year],
            Money(0)
        )

        # Add inflow transactions to debts and accounts based on our
        # net contributions and debt payments:
        contributions = self.contribution_transaction_strategy(
                self.net_contributions[year],
                self.assets
        )
        for account in contributions:
            account.add_transaction(
                contributions[account],
                self.contribution_transaction_strategy.timing
            )

    def record_principal(self, year):
        self.principal[year] = sum(
            account.balance for account in self.assets)

    def record_returns(self, year):
        self.gross_return[year] = sum(a.returns for a in self.assets)
        # TODO: Figure out what to do with tax_withheld_on_return.
        # Right now there's no way to distinguish between tax withheld
        # in an account due to returns vs. due to withdrawals.
        # IDEA: Eliminate disctinction between tax withheld on returns
        # vs. withdrawals and only consider tax withheld on accounts?
        # This will generally be paid from the accounts themselves, so
        # it probably makes sense to consider it all together.
        self.tax_withheld_on_return[year] = 0  # TODO
        self.net_return[year] = (
            self.gross_return[year] - self.tax_withheld_on_return[year]
        )

    def record_withdrawals(self, year):
        # TODO: Find a more graceful way to handle retirement_year.
        # Should we pick the earlier year? The later year?
        # Should we instead forego the all-at-once model of retirement
        # and base withdrawals instead on a target living standard
        # (i.e. reduce withdrawals based on family income?)
        # This probably calls for a separate method and a redesign
        # of withdrawal_strategy.
        retirement_year = max((
            person.retirement_date for person in self.people
            if person.retirement_date is not None),
            default=None).year

        self.withdrawals_from_retirement_accounts[year] = \
            self.withdrawal_strategy(
            benefits=Money(0),
            net_income=self.net_income[year],
            gross_income=self.gross_income[year],
            principal=self.principal[year],
            retirement_year=retirement_year,
            year=year
        )
        self.withdrawals_from_other_accounts[year] = 0  # TODO
        self.gross_withdrawals[year] = (
            self.withdrawals_from_retirement_accounts[year] +
            self.withdrawals_from_other_accounts[year]
        )
        self.tax_withheld_on_withdrawals[year] = sum(
            account.tax_withheld for account in self.assets
        )
        self.net_withdrawals[year] = (
            self.gross_withdrawals[year] -
            self.tax_withheld_on_withdrawals[year]
        )

    def record_total_tax(self, year):

        self.total_tax_withheld[year] = (
            self.taxes_withheld_on_income[year] +
            self.tax_withheld_on_return[year] +
            self.tax_withheld_on_withdrawals[year]
        )
        self.total_tax_owing[year] = self.tax_treatment(self.people, year)

    def record_living_standard(self, year):
        # TODO: Check Excel spreadsheet for calculation of this.
        # As currently shown, this deducts all taxes owing from the
        # living standard - even if some of those taxes are attributable
        # to activity within a savings account (and not withdrawal/etc.
        # activity that funds the living standard)
        self.living_standard[year] = (  # inflows
            self.gross_income[year] +
            self.gross_withdrawals[year] +
            self.refund[year] *
            (1 - self.contribution_strategy.refund_reinvestment_rate)
        ) - (  # outflows
            self.total_tax_owing[year] +  # TODO: Use tax_withheld?
            self.net_contributions[year] +
            self.contribution_reductions[year]
        )

    def record_year(self, year):
        """ Stores high-level values across accounts for this year."""
        # NOTE: Order is important here. This method is only split into
        # its various sub-methods for readability - it really is just
        # one long chain of procedural logic.
        self.record_income(year)
        self.record_gross_contribution(year)
        self.record_contribution_reductions(year)
        self.record_net_contributions(year)
        self.record_principal(year)
        self.record_withdrawals(year)
        self.record_returns(year)
        self.record_total_tax(year)
        self.record_living_standard(year)

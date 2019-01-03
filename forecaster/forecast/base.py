""" This module provides a Forecast class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
"""

from collections import defaultdict
from decimal import Decimal
from forecaster.ledger import (
    Ledger, Money,
    recorded_property, recorded_property_cached
)

class Forecast(Ledger):
    """ A financial forecast spanning multiple years.

    A `Forecast` is a container for various `*Forecast` objects, such
    as `IncomeForecast` and `WithdrawalForecast`. Those objects contain
    various `Account` objects with balances that grow (or shrink) from
    year to year,  `Person` objects describing the plannees, `Scenario`
    information describing economic conditions over the course of the
    forecast, and `Strategy` objects to describe the plannees' behaviour.

    `Forecast` provides a high-level model for annual cashflows as they
    relate to retirement savings. In particular, it uses this model:
    * Determine total (net) income for the year.
    * Determine the portion of net income not used for ordinary living
        expenses. Call this "available"; it is the pool of money available
        for retirement savings, lifecycle expenses, and debt repayment.
        # TODO: Revise the semantics of this to instead determine (base)
        # living expenses for the year? Can then deduct living expenses
        # and lifestyle expenses to get gross contributions - seems more
        # intuitive than this "available" rubric.
    * Determine the portion of available money which will be used
        on "lifecycle" expenses. These are expenditures on top of
        ordinary living expenses which vary over time. Inflows to
        retirement savings accounts are reduced to pay for these.
        This can include, e.g., childcare, contributions to education
        accounts, home purchase costs, and so on.

        Deducting lifecycle expenses from available money yields
        "gross contributions" - the total amount saved, including
        debt repayments as a form of savings.
    * Determine per-account debt repayments based on gross contributions.
        Deducting debt repayments from gross contributions yields
        "net contributions" - the total amount contributed to retirement
        accounts.
    * Determine per-account retirement contributions based on net
        contributions.
    * Determine the total amount withdrawn from retirement savings
        accounts.
    * Determine per-account withdrawals based on total withdrawals.
    * Determine total tax liability for the year; if necessary, adjust
        withdrawals accordingly and repeat.
    * Determine statistics for the year (e.g. living standard.)

    The `Forecast` can be built around any number of people, but is
    ordinarily built around either a single person or a spousal
    couple (since spouses have specific tax treatment). Otherwise, it's
    better practice to build separate `Forecast` objects for separate
    people.

    Note that each of the below `Money` attributes has an associated
    `dict[int, Money]` that stores the value of the attribute for each
    year of the forecast. (Key values are years.) The dicts are named
    `*_history`; e.g. `income` is associated with `income_history` and
    `income_history[2001]` gives the value of `income` for year `2001`.

    Attributes:
        income_forecast (IncomeForecast):
            A callable object that returns the net income for each
            year.
        contribution_forecast (ContributionForecast):
            A callable object that returns the (gross) contributions
            for each year.
        contribution_reduction_forecast (ContributionReductionForecast):
            A callable object that returns the contribution
            reductions for each year.
        contribution_strategy (TransactionStrategy):
            A callable object that returns the schedule of
            transactions for any contributions during the year.
            See the documentation for `TransactionStrategy` for
            acceptable args when calling this object.
        withdrawal_forecast (WithdrawalForecast):
            A callable object that returns the total withdrawals for
            each year.
        withdrawal_strategy (TransactionStrategy):
            A callable object that returns the schedule of
            transactions for any withdrawals during the year.
            See the documentation for `TransactionStrategy` for
            acceptable args when calling this object.
        tax_forecast (TaxForecast):
            A callable object that returns the total taxes owed for
            each year.

        scenario (Scenario): Economic information for the forecast
            (e.g. inflation and stock market returns for each year)

        income (dict[int, Money]): The net income for the plannees.
        gross_contributions (dict[int, Money]): The amount available to
            contribute to savings, before any reductions. This is the
            sum of net income and various contributions_from_* values.
        contribution_reductions (dict[int, Money]): Amounts diverted
            from savings, such as certain debt repayments or childcare.
        net_contributions (dict[int, Money]): The total amount
            contributed to savings accounts.
        principal (dict[int, Money]): The total value of all savings
            accounts (but not other property) at the start of each year.
        withdrawals (dict[int, Money]): The total amount withdrawn
            from all accounts.
        tax (dict[int, Money]): The total tax liability for the year
            (some of which might not be payable unti the next year).
            Does not include outstanding amounts which became owing
            but were not paid in the previous year.

        living_standard (dict[int, Money]): The total amount of money
            available for spending, net of taxes, contributions, debt
            payments, etc.
    """

    def __init__(
        self, income_forecast, contribution_forecast, reduction_forecast,
        withdrawal_forecast, tax_forecast, scenario
    ):
        """ Constructs an instance of class Forecast.

        Iteratively advances `people` and various accounts to the next
        year until all years of the `scenario` have been modelled.

        Args:
            income_forecast (IncomeForecast):
                Determines net income for each year.
            gross_contribution_forecast (GrossContributionForecast):
                Determines the gross contributions for each year.
            contribution_reduction_forecast (ContributionReductionForecast):
                Determines the contribution reductions for each year.
            withdrawal_forecast (WithdrawalForecast):
                A callable object that returns the total withdrawals for
                each year.
            tax_forecast (TaxForecast):
                Determines taxes owed for the year.
            scenario (Scenario): Provides an `initial_year` and a
                `num_year` property.
        """
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # TODO #53 removes this requirement.
        super().__init__(initial_year=scenario.initial_year)

        # Store input values
        self.income_forecast = income_forecast
        self.contribution_forecast = contribution_forecast
        self.reduction_forecast = reduction_forecast
        self.withdrawal_forecast = withdrawal_forecast
        self.tax_forecast = tax_forecast
        self.scenario = scenario

        # We'll keep track of cash flows over the course of the year, but
        # we don't save it as a recorded_property, so init it here:
        self._transactions = defaultdict(lambda: Money(0))

        # Arrange forecasts in order so it'll be easy to call them
        # in the correct order later:
        self.forecasts = [
            self.income_forecast, self.contribution_forecast,
            self.reduction_forecast, self.withdrawal_forecast,
            self.tax_forecast
        ]

        # Use the `Scenario` object to determine the range of years
        # to iterate over.
        last_year = max(self.scenario)
        while self.this_year < last_year:
            self.next_year()

    @property
    def people(self):
        """ The `Person` plannees for the forecast. """
        return self.income_forecast.people

    @property
    def assets(self):
        """ A set of `Asset` objects for the forecast, excluding debts. """
        return self.withdrawal_forecast.assets

    @property
    def debts(self):
        """ A set of `Debt` objects for the forecast. """
        return self.reduction_forecast.debts

    def next_year(self):
        """ Adds a year to the forecast. """
        # Advance the people and accounts first:
        for person in self.people:
            while person.this_year <= self.this_year:
                person.next_year()

        for account in self.assets.union(self.debts):
            while account.this_year <= self.this_year:
                account.next_year()

        # Clear out transactions for the new year:
        self._transactions = {}

        # Then update all of the recorded_property attributes
        # based on the new annual figures:
        super().next_year()

    @property
    def retirement_year(self):
        """ Determines the retirement year for the plannees.

        TODO: This approach forces `Forecast` to assume that all
        plannees retire at the same time, which is often inaccurate.
        We should use per-retiree retirement dates, meaning that this
        method should be removed and the calling code refactored.
        """
        return max(
            (
                person.retirement_date for person in self.people
                if person.retirement_date is not None
            ),
            default=None
        ).year

    @recorded_property_cached
    def income(self):
        """ Total net income for the year. """
        return self.income_forecast()

    @recorded_property_cached
    def gross_contributions(self):
        """ Gross contributions for the year, before reductions. """
        return self.contribution_forecast()

    @recorded_property_cached
    def contribution_reductions(self):
        """ Total contribution reductions for the year. """
        return self.reduction_forecast()

    @recorded_property_cached
    def net_contributions(self):
        """ Contributions to savings for the year. """
        # Never contribute a negative amount:
        return max(
            self.gross_contributions - self.contribution_reductions,
            Money(0)
        )

    @recorded_property_cached
    def principal(self):
        """ Total principal in accounts as of the start of the year. """
        return sum(
            (account.balance for account in self.assets),
            Money(0))

    @recorded_property
    def withdrawals(self):
        """ Total withdrawals for the year. """
        return self.withdrawal_forecast()

    @recorded_property
    def tax(self):
        """ Total tax liability for the year. """
        return self.tax_forecast()

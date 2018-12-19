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
from forecaster.utility import when_conv

class Forecast(Ledger):
    """ A financial forecast spanning multiple years.

    A `Forecast` is a container for various `*Forecast` objects, such
    as `IncomeForecast` and `WithdrawalForecast`. Those objects contain
    various `Account` objects with balances that grow (or shrink) from
    year to year,  `Person` objects describing the plannees, `Scenario`
    information describing economic conditions over the course of the
    forecast, and `Strategy` objects to describe the plannees' behaviour.

    The `Forecast` manages high-level cashflows each year. In particular,
    it uses this model:
    * Determine total (net) income for the year.
    * Determine the portion of net income not used as living expenses;
        this is called "gross contributions".
    * Determine the portion of gross contributions which will be used
        on non-retirement-savings expenditures (e.g. debt repayment,
        childcare, contributions to education accounts). These are
        "contribution reductions" and the remainder are "net
        contributions".
    * Determine per-account contributions based on net contributions.
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
        contribution_strategy, withdrawal_forecast, withdrawal_strategy,
        tax_forecast, scenario
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
                Determines taxes owed for the year.
            scenario (Scenario): Provides an `initial_year` and a
                `num_year` property.
        """
        # Store input values
        self.income_forecast = income_forecast
        self.contribution_forecast = contribution_forecast
        self.reduction_forecast = reduction_forecast
        self.contribution_strategy = contribution_strategy
        self.withdrawal_forecast = withdrawal_forecast
        self.withdrawal_strategy = withdrawal_strategy
        self.tax_forecast = tax_forecast
        self.scenario = scenario

        # We'll keep track of cash flows over the course of the year, but
        # we don't save it as a recorded_property, so init it here:
        self._transactions = defaultdict(lambda: Money(0))

        # Bundle forecasts together for each iterating:
        self.forecasts = {
            self.income_forecast, self.contribution_forecast,
            self.reduction_forecast, self.withdrawal_forecast,
            self.tax_forecast
        }

        # Use the `Scenario` object to determine the range of years
        # to iterate over.
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        super().__init__(initial_year=self.scenario.initial_year)
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

    def _add_transaction(
        self, transaction, when, account=None, account_transaction=None
    ):
        """ Helper method for `add_transaction`. """
        # Record to the dict:
        self._transactions[when] += transaction
        # Also add to the account, if passed:
        if account is not None:
            # Use the account_transaction amount, if passed,
            # otherwise fall back to `transaction`
            if account_transaction is None:
                account_transaction = transaction
            account.add_transaction(
                account_transaction,
                when=when)

    def _recurse_transaction(
        self, transaction, frequency,
        account=None, account_transaction=None
    ):
        """ Records multiple transactions with a given frequency. """
        # Split up transaction amounts based on the number of payments:
        transaction = transaction / frequency
        if account_transaction is not None:
            account_transaction = account_transaction / frequency

        # Add `frequency` number of transactions, with equal amounts
        # and even spacing, each transaction occurring at the end of
        # a period of length equal to `frequency`.
        for when in range(1, frequency + 1):
            self.add_transaction(
                transaction,
                when=when/frequency,
                account=account,
                account_transaction=account_transaction)

    def add_transaction(
        self, transaction, when=None, frequency=None,
        account=None, account_transaction=None
    ):
        """ Records a transaction at a time that balances the books.

        This method will always add the transaction at or after `when`
        (or at or after the implied timing provided by `frequency`).
        It tries to find a time where adding the transaction would
        avoid going cash-flow negative.

        In particular, it tries to find the _earliest_ such time.
        Thus, the timing will be equal to `when` if that timing
        meets this constraint. `when` is also used if no such
        time can be found.

        At least one of `when` and `frequency` must be provided.
        If `frequency` is provided, then `transaction` is split
        up into `frequency` equal amounts and each amount is
        contributed at the end of `frequency` payment periods.

        Example:
            `self.add_transaction(Money(1000), 'start')`
            `self.add_transaction(Money(1000), Decimal(0.5))`
            `self.add_transaction(Money(-2000), Decimal(0.25))`
            `# The transaction is added at when=0.5`
        
        Args:
            transaction (Money): The transaction to be added.
                Positive for inflows, negative for outflows.
            when (Decimal): The time at which the transaction occurs.
                Expressed as a value in [0,1]. Optional.
            frequency (int): The number of transactions made in the
                year. Must be positive. Optional.
            account (Account): An account to which the transaction
                is to be added. Optional.
            account_transaction (Money): If provided, this amount
                will be added to `Account` instead of `transaction`.

        Example:
            `f.add_transaction(Money(10), Decimal(0.5))`
            `# f._transactions = {0.5: Money(10)}`
            `f.add_transaction(Money(-10), Decimal(0.5))`
            `# f._transactions = {0.5: Money(0)}`
        """
        # If this is a `frequency` scenario, iterate
        if when is None:
            if frequency is not None:
                self._recurse_transaction(
                    transaction, frequency=frequency,
                    account=account,
                    account_transaction=account_transaction
                )
                return
            # If neither are provided, that's an error:
            else:
                raise ValueError(
                    'At least one of `when` and `frequency` must be provided.')

        # Sanitize input:
        when = when_conv(when)

        # Inflows are easy: We can accept those any time:
        if transaction >= 0:
            self._add_transaction(
                transaction, when,
                account=account, account_transaction=account_transaction)
            return

        # Outflows are a bit trickier.
        # First, figure out how much money is available
        # at each point in time, starting with `when`:
        available = {
            t: sum(
                # For each point in time `t`, find the sum of all
                # transactions up to this point:
                self._transactions[r] for r in self._transactions if r <= t)
            # We don't need to look at times before `when`:
            for t in self._transactions if t >= when
        }
        # If `when` isn't already represented in self_transactions,
        # add it manually to `available`
        if when not in available:
            # The amount available at `when` is just the sum of all
            # prior transactions (or $0, if there are none).
            available[when] = sum(
                (
                    self._transactions[t]
                    for t in self._transactions if t < when
                ),
                Money(0)
            )

        # Find the set of points in time where subtracting
        # `transaction` would not put any future point in time
        # into negative balance.
        # (Not really a set - it's a generator expression)
        eligible_times = (
            t for t in available if all(
                available[r] >= -transaction for r in available if r >= t
            )
        )
        # Find the earliest time that satisfies our requirements
        # (or, if none exists, use the time requested by the user)
        earliest_time = min(eligible_times, default=when)

        # We've found the time; now add the transaction!
        self._add_transaction(
            transaction, earliest_time,
            account=account, account_transaction=account_transaction)

    def record_debt_payments(self, total):
        """ TODO """
        pass  # TODO: How to address encapsulation in ReductionForecast?

    def record_contributions(self, total):
        """ TODO """
        # Determine the amount to contribute to each account:
        transactions = self.contribution_strategy(
            total=total, accounts=self.assets)
        # Contribute the appropriate amount to each account, deducting the
        # amount contributed from our available cashflow:
        for account in transactions:
            self.add_transaction(
                transaction=transactions[account],
                # Contribute monthly. TODO: Refine this?
                frequency='M',
                account=account
                )

    def record_withdrawals(self, total):
        """ TODO """
        # Determine the amount to withdraw from each account:
        transactions = self.withdrawal_strategy(
            total=total, accounts=self.assets)
        # Contribute the appropriate amount to each account, deducting the
        # amount contributed from our available cashflow:
        for account in transactions:
            self.add_transaction(
                transaction=transactions[account],
                # Contribute monthly. TODO: Refine this?
                frequency='M',
                account=account
                )

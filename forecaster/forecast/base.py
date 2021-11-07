""" This module provides a Forecast class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
"""

from collections import defaultdict
from forecaster.ledger import (
    Ledger, recorded_property, recorded_property_cached)
from forecaster.utility import Timing, add_transactions

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
    * Determine the portion of net income used for ordinary living
      expenses. This is the pool of money available for retirement
      savings and lifecycle expenses.

      Deducting living expenses from income yields "gross
      contributions" - the total amount available to be saved.
    * Determine the portion of available money which will be used
      on "lifecycle" expenses. These are expenditures on top of
      ordinary living expenses which vary over time. Inflows to
      retirement savings accounts are reduced to pay for these.
      This can include, e.g., childcare, contributions to education
      accounts, home purchase costs, debt repayment, and so on.

      Where lifecycle expenses involve contributions to
      non-retirement accounts (like education savings accounts or
      debt accounts), per-account contributions are also determined
      at this step.

      Deducting lifecycle expenses from gross contributions yields
      "net contributions" - the total amount actually saved.
    * Determine per-account retirement contributions based on net
      contributions.
    * Determine the amount withdrawn from retirement savings accounts.
      Allocate portions of that to each retirement account.
    * Determine total tax liability for the year; if necessary, adjust
      withdrawals accordingly and repeat.
    * Determine statistics for the year (e.g. living standard.)

    The `Forecast` can be built around any number of people, but is
    ordinarily built around either a single person or a spousal
    couple (since spouses have specific tax treatment). Otherwise, it's
    better practice to build separate `Forecast` objects for separate
    people.

    Note that each of the below `float` attributes has an associated
    `dict[int, float]` that stores the value of the attribute for each
    year of the forecast. (Key values are years.) The dicts are named
    `*_history`; e.g. `income` is associated with `income_history` and
    `income_history[2001]` gives the value of `income` for year `2001`.

    Attributes:
        income_forecast (IncomeForecast): A callable object that takes
            a cashflow time series (called `available`) and mutates it
            to include net income for each year.
        living_expenses_forecast (LivingExpensesForecast): A callable
            object that takes a cashflow time series (called
            `available`) and mutates it to include  ordinary living
            expenses for each year.
        saving_forecast (SavingForecast): A callable object that takes
            a cashflow time series (called `available`) and mutates it
            to include amounts contributed to savings for each year.
        withdrawal_forecast (WithdrawalForecast): A callable object that
            takes a cashflow time series (called `available`) and
            mutates it to include total withdrawals for each year.
        tax_forecast (TaxForecast): A callable object that takes
            a cashflow time series (called `available`) and mutates it
            to include total taxes owed within the each year, if any.
            It also provides attributes which help `Forecast` to
            determine whether any tax liability should be reflected in
            next year's cashflow.

        scenario (Scenario): Economic information for the forecast
            (e.g. inflation and stock market returns for each year)

        income (float): The net income for the plannees for the year.
        living_expenses (float): The amount that the plannees live off
            of for the year.
        gross_contributions (float): The amount available to
            contribute to savings, before any reductions. This is the
            amount left over after living expenses.
        contribution_reductions (float): Amounts diverted from
            savings, such as certain debt repayments or childcare.
        net_contributions (float): The total amount contributed to
            savings accounts for the year.
        principal (float): The total value of all savings accounts
            (but not other property) at the start of the year.
        withdrawals (float): The total amount withdrawn from all
            accounts for the year.
        tax (float): The total tax liability for the year (some of
            which might not be payable unti the next year).
            Does not include tax liability from previous years which
            is paid in this year, but does include tax liability
            arising in this year which won't be repaid until a
            future year.
    """

    def __init__(
            self, income_forecast, living_expenses_forecast,
            saving_forecast, withdrawal_forecast,
            tax_forecast, scenario):
        """ Constructs an instance of class Forecast.

        Args:
            income_forecast (IncomeForecast):
                Determines net income for each year.
            living_expenses_forecast (LivingExpensesForecast):
                Determines the living expenses for each year.
            saving_forecast (SavingForecast):
                Determines the savings for each year.
            withdrawal_forecast (WithdrawalForecast):
                Determines the total withdrawals for each year.
            tax_forecast (TaxForecast):
                Determines taxes owed for the year.
            scenario (Scenario): Provides `initial_year` and `num_year`
                properties.
        """
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # NOTE: Issue #53 removes this requirement.
        super().__init__(initial_year=scenario.initial_year)

        # Store input values
        self.income_forecast = income_forecast
        self.living_expenses_forecast = living_expenses_forecast
        self.saving_forecast = saving_forecast
        self.withdrawal_forecast = withdrawal_forecast
        self.tax_forecast = tax_forecast
        self.scenario = scenario

        # We'll keep track of cash flows over the course of the year, but
        # we don't save it as a recorded_property, so init it here:
        self.available = defaultdict(lambda: 0) # Money value

        # Arrange forecasts in order so it'll be easy to call them
        # in the correct order later:
        self.forecasts = [
            self.income_forecast,
            self.living_expenses_forecast,
            self.saving_forecast,
            self.withdrawal_forecast,
            self.tax_forecast]

        # Use the `Scenario` object to determine the range of years
        # to iterate over.
        last_year = max(self.scenario)
        while self.this_year < last_year:
            self.call_subforecasts()
            self.next_year()
        self.call_subforecasts()

    @property
    def people(self):
        """ The `Person` plannees for the forecast. """
        return self.income_forecast.people

    @property
    def assets(self):
        """ A set of non-Debt `Account` objects for the forecast. """
        return self.withdrawal_forecast.accounts

    @property
    def debts(self):
        """ A set of `Debt` objects for the forecast. """
        return self.saving_forecast.debt_accounts

    def call_subforecasts(self):
        """ Calls each SubForecast in order. """
        for forecast in self.forecasts:
            forecast(self.available)

    def next_year(self):
        """ Adds a year to the forecast. """
        # Store the values from this year that will be needed to
        # determine carryover amounts:
        available_previous = dict(self.available)
        tax_adjustment_previous = self._get_tax_adjustment()

        # First, record the state of all recorded_property attributes:
        super().next_year()
        # The do the same for all SubForecast objects, so they can
        # record their state before underlying objects get updated:
        for forecast in self.forecasts:
            while forecast.this_year < self.this_year:
                forecast.next_year()

        # Now advance the underlying Ledger objects:
        for person in self.people:
            while person.this_year < self.this_year:
                person.next_year()
        for account in self.assets.union(self.debts):
            while account.this_year < self.this_year:
                account.next_year()

        # It's a new year! Empty out `available` and then add any
        # applicable carryover amounts:
        self.available.clear()
        self._carrover_overflow(available_previous)
        self._carryover_tax(tax_adjustment_previous)

    def _get_tax_adjustment(self):
        """ The tax adjustment for this year, payable next year. """
        # Don't carry over taxes if the objects involved aren't set up
        # to tell us how much tax is owing!
        if (
                not hasattr(self, "tax_forecast")
                or not hasattr(self.tax_forecast, "tax_adjustment")):
            return None

        # Tax refunds/payments are not reflected in `available`; add
        # them here based on what's in `tax_treatment`:
        return self.tax_forecast.tax_adjustment

    def _carrover_overflow(self, available_previous):
        """ Roll over unused monies from one year to the next. """
        # Keep track of cash flows over the course of the year,
        # rolling over unused monies to the start of next year:
        self.available[0] += sum(available_previous.values())

    def _carryover_tax(self, tax_adjustment_previous):
        """ Add tax refunds/payments arising from last year's taxes. """
        # Nothing to carry over is there's no known tax adjustment:
        if tax_adjustment_previous is None:
            return

        # Determine the time series of transactions as appropriate:
        if tax_adjustment_previous > 0:  # refund
            if hasattr(self.tax_forecast, "tax_refund_timing"):
                timing = self.tax_forecast.tax_refund_timing
            else:
                timing = Timing(0)
        elif tax_adjustment_previous < 0:  # payment owing
            if hasattr(self.tax_forecast, "tax_payment_timing"):
                timing = self.tax_forecast.tax_payment_timing
            else:
                timing = Timing(0)
        else:  # no adjustment
            return  # No need to proceed on to add_transactions
        # Add the time-series of transactions to `available`:
        transactions = timing.time_series(tax_adjustment_previous)
        add_transactions(self.available, transactions)

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
        return self.income_forecast.net_income

    @recorded_property_cached
    def living_expenses(self):
        """ Total amount spent on living expenses for the year. """
        return self.living_expenses_forecast.living_expenses

    @recorded_property_cached
    def savings(self):
        """ Contributions to savings for the year. """
        # Never contribute a negative amount:
        return max(
            self.income - self.living_expenses,
            0) # Money value

    @recorded_property_cached
    def principal(self):
        """ Total principal in accounts as of the start of the year. """
        return sum(
            (account.balance for account in self.assets),
            0) # Money value

    @recorded_property
    def withdrawals(self):
        """ Total withdrawals for the year. """
        return self.withdrawal_forecast.gross_withdrawals

    @recorded_property
    def tax(self):
        """ Total tax liability for the year. """
        return self.tax_forecast.tax_owing

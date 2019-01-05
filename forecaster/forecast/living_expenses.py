""" Provides a LivingExpensesForecast class for use by Forecast. """

from forecaster.ledger import Money, recorded_property
from forecaster.forecast.subforecast import SubForecast

class LivingExpensesForecast(SubForecast):
    """ A forecast of each year's living expenses.

    Attributes:
        living_expenses_strategy (LivingExpensesStrategy): A callable
            object that determines the living expenses for the
            plannees for a year.
            See the documentation for `LivingExpensesStrategy` for
            acceptable args when calling this object.

        tax_carryover (dict[int, Money]): The amount of any refund or
            outstanding tax payable, based on the previous year's
            tax withholdings.
        other_carryover (dict[int, Money]): The amount of inter-year
            carryover (other than tax refunds), such as excess
            withdrawals being recontributed.
        contributions_from_income (dict[int, Money]): The amount to be
            contributed to savings from employment income in each year.
        contributions_from_carryover (dict[int, Money]): The amount to
            be contributed to savings from tax_carryover and
            other_carryover.
        contributions_from_asset_sales (dict[int, Money]): The amount to
            be contributed to savings from asset sales in each year.
        gross_contributions (dict[int, Money]): The amount available to
            contribute to savings, before any reductions. This is the
            sum of net income and various contributions_from_* values.
    """

    def __init__(
        self, initial_year, people, living_expenses_strategy
    ):
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # TODO #53 removes this requirement.
        super().__init__(initial_year)

        self.living_expenses_strategy = living_expenses_strategy
        self.people = people

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # NOTE, TODO: This code assumes `contribution_strategy`
        # returns the amount that will be _spent_ on living expenses,
        # _not_ the amount saved after living expenses. This conforms
        # with the proposals of #40 and #32.
        # Assume living expenses are incurred at the start of each
        # month.
        self.add_transaction(
            value=self.living_expenses, when=0, frequency=12,
            from_account=available, to_account=None)

    @recorded_property
    def living_expenses(self):
        """ TODO """
        # Prepare arguments for call to `contribution_strategy`
        # TODO: Determine retirement year from `Person` objects
        retirement_year = None  # TODO
        return self.living_expenses_strategy(
            year=self.this_year,
            people = self.people,
            retirement_year=retirement_year  # TODO
        )

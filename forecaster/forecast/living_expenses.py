""" Provides a LivingExpensesForecast class for use by Forecast. """

from forecaster.ledger import (
    Money, recorded_property, recorded_property_cached)
from forecaster.forecast.subforecast import SubForecast

class LivingExpensesForecast(SubForecast):
    """ A forecast of each year's living expenses.

    Args:
        initial_year (int): The first year of the forecast.
        people (Iterable[Person]): The people for whom the financial
            forecast is being generated. Typically a single person or
            a person and their spouse.

            Note that all `Person` objects must have the same
            `this_year` attribute, as must their various accounts.
        living_expenses_strategy (LivingExpensesStrategy): A callable
            object that determines the living expenses for the
            plannees for a year.
            See the documentation for `LivingExpensesStrategy` for
            acceptable args when calling this object.

    Attributes:
        living_expenses (Money): The amount spent on living expenses
            (i.e. money not available to be saved).
    """

    def __init__(
        self, initial_year, people, living_expenses_strategy
    ):
        """ Initializes an instance of LivingExpensesForecast. """
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

        # Assume living expenses are incurred at the start of each
        # month. Make this strict, since we can't defer living
        # expenses to a more convenient time.
        self.add_transaction(
            value=self.living_expenses, when=0, frequency=12,
            from_account=available, to_account=None, strict_timing=True)

    @recorded_property_cached
    def living_expenses(self):
        """ Living expenses for the year. """
        # Prepare arguments for call to `living_expenses_strategy`
        # NOTE: This is a pretty brittle way to determine the
        # retirement year. Issues #15 and #28 will require this
        # code to be changed in a future version.
        retirement_year = min(
            person.retirement_date.year for person in self.people)
        return self.living_expenses_strategy(
            year=self.this_year,
            people = self.people,
            retirement_year=retirement_year
        )

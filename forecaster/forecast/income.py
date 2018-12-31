""" Provides an IncomeForecast class for use by Forecast. """

from forecaster.ledger import Money, recorded_property
from forecaster.forecast.subforecast import SubForecast

class IncomeForecast(SubForecast):
    """ A forecast of income over the years.

    Attributes:
        people (Iterable[Person]): The people for whom the financial
            forecast is being generated. Typically a single person or a
            person and their spouse.

            Note that all `Person` objects must have the same
            `this_year` attribute, as must their various accounts.
    """

    def __init__(
        self, initial_year, people
    ):
        """ Constructs an instance of class IncomeForecast.

        Args:
            people (Iterable[Person]): The people for whom a forecast
                is being generated.
        """
        super().__init__(initial_year)
        # Invoke Ledger's __init__ or pay the price!
        # Store input values
        self.people = people

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # Record income monthly.
        # NOTE: This code assumes income is received at the end of
        # each payment period. Consider whether some cases (like
        # biweekly payments) might justify using the midpoint of
        # each period.
        for person in self.people:
            self.add_transaction(
                person.net_income, when=0.5,
                frequency=person.payment_frequency,
                from_account=None, to_account=available)

    @recorded_property
    def gross_income(self):
        """ Gross income for all plannees for the year. """
        return sum(
            (person.gross_income for person in self.people),
            Money(0))

    @recorded_property
    def tax_withheld_on_income(self):
        """ Tax withheld on income for all plannees for the year. """
        return sum(
            (person.tax_withheld for person in self.people),
            Money(0))

    @recorded_property
    def net_income(self):
        """ Net income for all plannees for the year. """
        return sum(
            (person.net_income for person in self.people),
            Money(0))

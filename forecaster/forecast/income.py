""" Provides an IncomeForecast class for use by Forecast. """

from forecaster.ledger import recorded_property
from forecaster.forecast.subforecast import SubForecast

class IncomeForecast(SubForecast):
    """ A forecast of income over the years.

    Args:
        initial_year (int): The first year of the forecast.
        people (Iterable[Person]): The people for whom the financial
            forecast is being generated. Typically a single person or
            a person and their spouse.

            Note that all `Person` objects must have the same
            `this_year` attribute, as must their various accounts.
        asset_sale_timing (Timing): The timing of asset sales.
            Optional.

    Attributes:
        asset_sale (float): The proceeds from a sale of property.
            TODO: Determine if asset sale belongs here or elsewhere.
        carryover (float): Money carried over from last year to
            the current year.
        gross_income (float): Total income for all plannees for the
            year, before taxes.
        tax_withheld (float): Total tax withheld on plannees' income
            at source.
        net_income (float): Total income for all plannees for the
            year, net of taxes.
    """

    def __init__(
            self, initial_year, people, asset_sale_timing=None):
        """ Initializes an instance of IncomeForecast. """
        super().__init__(initial_year, default_timing=asset_sale_timing)
        # Invoke Ledger's __init__ or pay the price!
        # Store input values
        self.people = people

    def __call__(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().__call__(available)

        # TODO: Move money into available from an `Asset` account  #32
        self.add_transaction(
            value=self.asset_sale,
            from_account=None,  # TODO Move money from asset account #32
            to_account=available
        )

        # Record income according to the Persons' payment schedules:
        for person in self.people:
            self.add_transaction(
                person.net_income,
                timing=person.payment_timing,
                from_account=None, to_account=available)

    @recorded_property
    def asset_sale(self):
        """ Proceeds of sale of an asset. """
        # TODO Implement asset sale #32
        return 0 # Money value

    @recorded_property
    def carryover(self):
        """ Excess funds carried over from last year. """
        # Money is carried over when there's more money remaining
        # than is required for living expenses - e.g. because
        # we withdrew more than necessary or because we accrued
        # interest on the pool of available money.
        # This is the same as checking how much is in `available`
        # before `IncomeForecast` mutates it - which is what
        # `total_available` gives us!
        return self.total_available

    @recorded_property
    def gross_income(self):
        """ Gross income for all plannees for the year. """
        return sum(
            (person.gross_income for person in self.people),
            0) # Money value

    @recorded_property
    def tax_withheld(self):
        """ Tax withheld on income for all plannees for the year. """
        return sum(
            (person.tax_withheld for person in self.people),
            0) # Money value

    @recorded_property
    def net_income(self):
        """ Net income for all plannees for the year. """
        return sum(
            (person.net_income for person in self.people),
            0) # Money value

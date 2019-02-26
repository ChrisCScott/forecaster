""" Provides an IncomeForecast class for use by Forecast. """

from forecaster.ledger import Money, recorded_property
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

    Attributes:
        asset_sale (Money): The proceeds from a sale of property.
            TODO: Determine if asset sale belongs here or elsewhere.
        carryover (Money): Money carried over from last year to
            the current year.
        gross_income (Money): Total income for all plannees for the
            year, before taxes.
        tax_withheld (Money): Total tax withheld on plannees' income
            at source.
        net_income (Money): Total income for all plannees for the
            year, net of taxes.
    """

    def __init__(
            self, initial_year, people):
        """ Initializes an instance of IncomeForecast. """
        super().__init__(initial_year)
        # Invoke Ledger's __init__ or pay the price!
        # Store input values
        self.people = people

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # TODO: Determine timing of asset sale. (see #32)
        # Also: should this receive an Account (e.g. other_assets)
        # as the `from_account`?
        self.add_transaction(
            value=self.asset_sale,
            when=0.5,  # TODO Determine timing of asset sale #32
            from_account=None,  # TODO Move money from asset account #32
            to_account=available
        )

        # Record income according to the Persons' payment schedules:
        for person in self.people:
            self.add_transaction(
                person.net_income,
                when=person.payment_timing,
                frequency=person.payment_frequency,
                from_account=None, to_account=available)

    @recorded_property
    def asset_sale(self):
        """ Proceeds of sale of an asset. """
        return Money(0)  # TODO Implement asset sale #32

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
            Money(0))

    @recorded_property
    def tax_withheld(self):
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

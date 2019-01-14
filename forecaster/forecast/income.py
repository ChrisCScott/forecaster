""" Provides an IncomeForecast class for use by Forecast. """

from forecaster.ledger import Money, recorded_property
from forecaster.accounts import Account
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

        # Assume tax carryovers occur at the start of the year.
        # TODO: Tax refund/payment dates should be provided by
        # a Tax object and used here.
        # NOTE: We distinguish between carryovers from tax and
        # carryovers from other sources. Would it instead make
        # more sense to treat all carryovers the same? People
        # do sometimes treat tax refunds differently than other
        # carryovers, but perhaps we can deal with that in
        # `Forecast`?
        self.add_transaction(
            self.tax_carryover,
            when=0,  # TODO #31
            from_account=None, to_account=available)
        # TODO: Determine timing of asset sale. (see #32)
        # Also: should this receive an Account (e.g. other_assets)
        # as the `from_account`?
        self.add_transaction(
            value=self.asset_sale,
            when=0.5,  # TODO #32
            from_account=None,  # TODO #32
            to_account=available
        )

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
    def tax_carryover(self):
        """ Tax refund or amount owing due to last year's income. """
        if self.this_year == self.initial_year:
            # In the first year, carryovers are $0:
            return Money(0)
        else:
            # If more was withheld than was owed, we have a refund
            # (positive), otherwise we have an amount owing (negative)
            # TODO: Need to determine the difference between tax
            # withheld and tax owing *in the previous year*.
            # There's currently no mechanism for this class to talk
            # to talk to `TaxForecast`; consider how to address this.
            '''
            self.tax_carryover = (
                self.total_tax_withheld_history[self.this_year - 1]
                - self.total_tax_owing_history[self.this_year - 1]
            )
            '''
            return Money(0)  # TODO #54

    @recorded_property
    def asset_sale(self):
        """ Proceeds of sale of an asset. """
        return Money(0)  # TODO #32

    @recorded_property
    def other_carryover(self):
        """ Excess funds carried over from last year. """
        # Money is carried when there's more money remaining
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

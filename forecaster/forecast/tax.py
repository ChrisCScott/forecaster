""" Provides a TaxForecast class for use by Forecast. """

from forecaster.forecast import SubForecast
from forecaster.ledger import recorded_property_cached

class TaxForecast(SubForecast):
    """ A forecast of total tax owing for each year.

    Args:
        initial_year (int): The first year of the forecast.
        people (Iterable[Person]): The plannees.
        tax_treatment (Tax): A callable object that determines the total
            amount of tax owing in a year. See the documentation for
            `Tax` for acceptable args when calling this object.

    Attributes:
        tax_withheld (Money): The total amount of tax owing for this
            year which was paid during this year (as opposed to being
            paid in the following year via `tax_adjustment`).
        tax_owing (Money): The total amount of tax owing for this year
            (some of which may be paid in the following year). Does
            not include any amounts paid this year which became owing
            last year (i.e. doesn't include the `tax_adjustment` from
            last year.)
        tax_adjustment (Money): The amount of tax to be refunded (if
            positive) or paid (if negative) in next year's tax season
            due to excess/insufficient withholding taxes during this
            year.
    """

    def __init__(
            self, initial_year, people, tax_treatment):
        """ Initializes an instance of TaxForecast. """
        # Call the superclass method or suffer the consequences!
        super().__init__(initial_year)
        # Store input values
        self.people = people
        self.tax_treatment = tax_treatment

    # TODO: Add __call__ method to apply tax_adjustment?
    # One option would be to clear `available` and add
    # appropriately-timed inflows/outflows for rebates/amounts owing,
    # on the assumption that this is the last subforecast to be called.
    # At present that doesn't seem necessary.

    @recorded_property_cached
    def tax_withheld(self):
        """ Total taxes withheld on income for the year. """
        # Need to sum up both tax withheld on income and also tax
        # withheld from accounts for each person:
        withheld = sum(person.tax_withheld for person in self.people)
        # To avoid double-counting (if an account is associated with
        # two people), build a set of all accounts and sum over that.
        accounts = set.union(*(person.accounts for person in self.people))
        withheld += sum(account.tax_withheld for account in accounts)
        return withheld

    @recorded_property_cached
    def tax_owing(self):
        """ Total taxes owing on income for the year. """
        return self.tax_treatment(self.people, self.this_year)

    @recorded_property_cached
    def tax_adjustment(self):
        """ Total amount owing or refunded at tax time next year.

        Negative values are amounts owing, positive are refunds.
        """
        return self.tax_withheld - self.tax_owing

""" Provides a TaxForecast class for use by Forecast. """

from forecaster.forecast import SubForecast
from forecaster.ledger import Money, recorded_property_cached

class TaxForecast(SubForecast):
    """ A forecast of total tax owing for each year.

    Attributes:
        people (Iterable[Person]): The plannees.
        tax_treatment (Tax): A callable object that determines the total
            amount of tax owing in a year. See the documentation for
            `Tax` for acceptable args when calling this object.

        total_tax_withheld (Money): The total amount of tax
            owing for this year which was paid during this year (as
            opposed to being paid in the following year the next year).
        total_tax_owing (Money): The total amount of tax
            owing for this year (some of which may be paid in the
            following year). Does not include outstanding amounts which
            became owing but were not paid in the previous year.
    """

    def __init__(
        self, people, tax_treatment
    ):
        """ Constructs an instance of class Forecast.

        Iteratively advances `people` and various accounts to the next
        year until all years of the `scenario` have been modelled.

        Args:
            people (Iterable[Person]): The people for whom a forecast
                is being generated.
            tax_treatment (Tax): A callable object that determines the
                total amount of tax owing in a year. See the documentation
                for `Tax` for acceptable args when calling this object.
        """
        # Store input values
        self.people = people
        self.tax_treatment = tax_treatment

    @recorded_property_cached
    def tax_withheld(self):
        """ TODO """
        # Need to sum up both tax withheld on income and also tax
        # withheld from accounts for each person:
        withheld = sum(person.tax_withheld for person in self.people)
        # To avoid double-counting (if an account is assocaited with
        # two people), build a set of all accounts and sum over that.
        accounts = set.union(person.accounts for person in self.people)
        withheld += sum(account.tax_withheld for account in accounts)
        return withheld

    @recorded_property_cached
    def tax_owing(self):
        """ TODO """
        return self.tax_treatment(self.people, self.this_year)

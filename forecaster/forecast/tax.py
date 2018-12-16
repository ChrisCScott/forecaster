""" This module provides a Forecast class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
"""

from collections import defaultdict
from decimal import Decimal
from forecaster.ledger import Money
from forecaster.utility import when_conv

# pylint: disable=too-many-instance-attributes
# This object has a complex state. We could store the records for each
# year in some sort of pandas-style frame or table, but for now each
# data column is its own named attribute.
class TaxForecast(object):
    """ A forecast of total tax owing for each year.

    Attributes:
        people (Iterable[Person]): The people for whom the financial
            forecast is being generated. Typically a single person or a
            person and their spouse.

            Note that all `Person` objects must have the same
            `this_year` attribute, as must their various accounts.

        tax_treatment (Tax): A callable object that determines the total
            amount of tax owing in a year. See the documentation for
            `Tax` for acceptable args when calling this object.

        total_tax_withheld (dict[int, Money]): The total amount of tax
            owing for this year which was paid during this year (as
            opposed to being paid in the following year the next year).

            Note that this is not necessarily the same as the sum of
            other `tax_withheld_on_\\*` attributes, since the tax
            authority may require additional withholding taxes (or
            payment by installments) based on the person's overall
            circumstances.
        total_tax_owing (dict[int, Money]): The total amount of tax
            owing for this year (some of which may be paid in the
            following year). Does not include outstanding amounts which
            became owing but were not paid in the previous year.
    """

    # pylint: disable=too-many-arguments
    # NOTE: Consider combining the various strategy objects into a dict
    # or something (although it's not clear how this benefits the code.)
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

        # Prepare output dicts:
        # Total tax
        self.tax_withheld = {}
        self.tax_owing = {}

    def record_tax(self, year):
        """ Records total tax withheld and payable in the year.

        TODO: Deal with tax owing but not withheld - arrange to pay this
        in the following year? Apply against investment balances? Draw
        a portion from income (i.e. as a living expense)?

        Note that in Canada, if more than $3000 or so of tax is owing
        but not withheld, the CRA will put you on an instalments plan,
        so you can't really defer your total tax liability into the next
        year.
        """
        self.tax_withheld[year] = (
            self.tax_withheld_on_income[year] +
            self.tax_withheld_on_return[year] +
            self.tax_withheld_on_withdrawals[year]
        )
        self.tax_owing[year] = self.tax_treatment(self.people, year)

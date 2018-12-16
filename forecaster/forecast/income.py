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
class IncomeForecast(object):
    """ A forecast of income over the years.

    Attributes:
        people (Iterable[Person]): The people for whom the financial
            forecast is being generated. Typically a single person or a
            person and their spouse.

            Note that all `Person` objects must have the same
            `this_year` attribute, as must their various accounts.
    """

    # pylint: disable=too-many-arguments
    # NOTE: Consider combining the various strategy objects into a dict
    # or something (although it's not clear how this benefits the code.)
    def __init__(
        self, people
    ):
        """ Constructs an instance of class IncomeForecast.

        Args:
            people (Iterable[Person]): The people for whom a forecast
                is being generated.
        """
        # Store input values
        self.people = people

        # Prepare output dicts:
        # Income
        self.gross_income = {}
        self.tax_withheld_on_income = {}
        self.net_income = {}

    def record_income(self, year):
        """ Records gross and net income, as well as taxes withheld. """
        # Determine gross/net income for the family:
        self.gross_income[year] = sum(
            (person.gross_income for person in self.people),
            Money(0))
        self.tax_withheld_on_income[year] = sum(
            (person.tax_withheld for person in self.people),
            Money(0))
        self.net_income[year] = sum(
            (person.net_income for person in self.people),
            Money(0))

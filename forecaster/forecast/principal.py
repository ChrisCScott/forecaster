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
class PrincipalForecast(object):
    """ A forecast of a portfolio's principal over time.

    Attributes:
        assets (Iterable[Account]): Assets of the `people`.
        scenario (Scenario): Economic information for the forecast
            (e.g. inflation and stock market returns for each year)

        contribution_transaction_strategy (TransactionStrategy): A
            callable object that determines the schedule of
            transactions for any contributions during the year.
            See the documentation for `TransactionStrategy` for
            acceptable args when calling this object.

        principal (dict[int, Money]): The total value of all savings
            accounts (but not other property) at the start of each year.
        gross_return (dict[int, Money]): The total return on principal
            (only for the amounts included in `principal`) by the end of
            the year.
        tax_withheld_on_return (dict[int, Money]): Taxes deducted at
            source on the returns on investments.
        net_return (dict[int, Money]): The total return on principal
            (only for the amounts included in `principal`) by the end of
            the year, net of withholding taxes.
    """

    # pylint: disable=too-many-arguments
    # NOTE: Consider combining the various strategy objects into a dict
    # or something (although it's not clear how this benefits the code.)
    def __init__(
        self, assets, scenario, contribution_transaction_strategy
    ):
        self.assets = assets
        self.scenario = scenario
        self.contribution_transaction_strategy = contribution_transaction_strategy

        # Principal (and return on principal)
        self.principal = {}
        self.gross_return = {}
        self.tax_withheld_on_return = {}
        self.net_return = {}

    def record_principal(self, year):
        """ Records principal balance and returns for the year. """
        self.principal[year] = sum(
            (account.balance for account in self.assets),
            Money(0))
        self.gross_return[year] = sum(
            (a.returns for a in self.assets),
            Money(0))
        # TODO: Figure out what to do with tax_withheld_on_return.
        # Right now there's no way to distinguish between tax withheld
        # in an account due to returns vs. due to withdrawals.
        # IDEA: Eliminate disctinction between tax withheld on returns
        # vs. withdrawals and only consider tax withheld on accounts?
        # This will generally be paid from the accounts themselves, so
        # it probably makes sense to consider it all together.
        self.tax_withheld_on_return[year] = Money(0)  # TODO
        self.net_return[year] = (
            self.gross_return[year] - self.tax_withheld_on_return[year]
        )

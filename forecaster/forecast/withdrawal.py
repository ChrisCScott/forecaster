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
class WithdrawalForecast(object):
    """ A forecast of withdrawals from a portfolio over time.

    Attributes:
        assets (Iterable[Account]): Assets of the `people`.
        scenario (Scenario): Economic information for the forecast
            (e.g. inflation and stock market returns for each year)

        withdrawal_strategy (WithdrawalStrategy): A callable
            object that determines the amount to withdraw for a
            year. See the documentation for `WithdrawalStrategy` for
            acceptable args when calling this object.
        withdrawal_transaction_strategy
            (WithdrawalTransactionStrategy):
            A callable object that determines the schedule of
            transactions for any contributions during the year.
            See the documentation for `TransactionStrategy` for
            acceptable args when calling this object.

        withdrawals_from_retirement_accounts (dict[int, Money]): The
            total value of all withdrawals from retirement savings
            accounts over the year.
        withdrawals_from_other_accounts (dict[int, Money]): The total
            value of all withdrawals from other savings accounts (e.g.
            education or health accounts, if provided) over the year.
        gross_withdrawals (dict[int, Money]): The total amount withdrawn
            from all accounts.
        tax_withheld_on_withdrawals (dict[int, Money]): Taxes deducted
            at source on withdrawals from savings.
        net_withdrawals (dict[int, Money]): The total amount withdrawn
            from all accounts, net of withholding taxes.
    """

    # pylint: disable=too-many-arguments
    # NOTE: Consider combining the various strategy objects into a dict
    # or something (although it's not clear how this benefits the code.)
    def __init__(
        self, assets, scenario,
        withdrawal_strategy, withdrawal_transaction_strategy
    ):
        """ Constructs an instance of class WithdrawalForecast.

        Iteratively advances `people` and various accounts to the next
        year until all years of the `scenario` have been modelled.

        Args:
            assets (Iterable[Account]): The assets of the people.
            scenario (Scenario): Economic information for the forecast
                (e.g. inflation and stock market returns for each year)
            withdrawal_strategy (WithdrawalStrategy): A callable
                object that determines the amount to withdraw for a
                year. See the documentation for `WithdrawalStrategy` for
                acceptable args when calling this object.
            withdrawal_transaction_strategy
                (WithdrawalTransactionStrategy):
                A callable object that determines the schedule of
                transactions for any contributions during the year.
                See the documentation for `TransactionStrategy` for
                acceptable args when calling this object.
        """
        # Store input values
        self.assets = assets
        self.scenario = scenario
        self.withdrawal_strategy = withdrawal_strategy
        self.withdrawal_transaction_strategy = withdrawal_transaction_strategy

        # Prepare output dicts:
        self.withdrawals_for_retirement = {}
        self.withdrawals_for_tax = {}
        self.withdrawals_for_other = {}
        self.gross_withdrawals = {}
        self.tax_withheld_on_withdrawals = {}
        self.net_withdrawals = {}

    def record_withdrawals(self, year):
        """ Records withdrawals for the year.

        Withdrawals are divided into retirement and other withdrawals.
        Taxes on withdrawals are determined to produce a figure for
        net withdrawals.
        """
        retirement_year = self.retirement_year()

        self.withdrawals_for_retirement[year] = (
            self.withdrawal_strategy(
                benefits=Money(0),
                net_income=self.net_income[year],
                gross_income=self.gross_income[year],
                principal=self.principal[year],
                retirement_year=retirement_year,
                year=year
            )
        )

        # If we have a tax balance to pay off, add that here.
        if self.tax_carryover[year] < 0:
            self.withdrawals_for_tax[year] = -(
                self.reduction_from_tax[year] + self.tax_carryover[year]
            )
        else:
            self.withdrawals_for_tax[year] = Money(0)

        self.withdrawals_for_other[year] = Money(0)  # TODO
        self.gross_withdrawals[year] = (
            self.withdrawals_for_retirement[year]
            + self.withdrawals_for_tax[year]
            + self.withdrawals_for_other[year]
        )

        self.tax_withheld_on_withdrawals[year] = sum(
            (account.tax_withheld for account in self.assets),
            Money(0)
        )
        # TODO: Lumping net withdrawals together doesn't seem very
        # useful. Consider splitting apart tax withholdings by
        # withdrawal type and finding net withdrawals independently.
        self.net_withdrawals[year] = (
            self.gross_withdrawals[year] -
            self.tax_withheld_on_withdrawals[year]
        )

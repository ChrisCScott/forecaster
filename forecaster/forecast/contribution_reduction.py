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
class ContributionReductionsForecast(object):
    """ A forecast of each year's contribution reductions.

    Attributes:
        debts (Iterable[Debt]): Debts of the `people`.
        reduction_from_debt (dict[int, Money]): The amount to be
            diverted from contributions to debt repayment in each year.
        reduction_from_other (dict[int, Money]): The amount to be
            diverted from contributions for other spending purposes in
            each year.
        contribution_reductions (dict[int, Money]): Amounts diverted
            from savings, such as certain debt repayments or childcare.
        net_contributions (dict[int, Money]): The total amount
            contributed to savings accounts.
    """

    def __init__(
        self, debts, debt_payment_strategy
    ):
        self.debts = debts
        self.debt_payment_strategy = debt_payment_strategy

        self.reduction_from_debt = {}
        self.reduction_from_other = {}
        self.contribution_reductions = {}
        self.net_contributions = {}

    def record_contribution_reductions(self, year):
        """ Records contribution reductions for the year.

        This method determines total debt payments and applies per-debt
        payments to debt accounts.
        """
        # Determine contribution reductions:
        # TODO: Include reduced contributions to pay for last year's
        # outstanding taxes?
        # NOTE: We'll add another reduction dict for childcare expenses
        # in a future version.
        # First determine miscellaneous other reductions (these take
        # priority because they're generally user-input):
        self.reduction_from_other[year] = Money(0)  # TODO
        # Assume we make `other` reductions at the end of the year:
        self.add_transaction(
            transaction=-self.reduction_from_other[year],
            when=1
        )

        # Then determine reductions due to debt payments:
        # Start with gross debt payments:
        debt_payments = self.debt_payment_strategy(
            self.debts,
            self.gross_contributions[year] - self.reduction_from_other[year]
        )
        # Then determine what portion was drawn from savings:
        debt_payments_from_savings = {
            debt: debt.payment_from_savings(
                amount=debt_payments[debt],
                base=debt.inflows
            ) for debt in debt_payments
        }
        # Then reduce savings by that amount (simple, right?):
        self.reduction_from_debt[year] = sum(
            debt_payments_from_savings.values(),
            Money(0)
        )
        # Apply (gross) debt payment transactions
        for debt in debt_payments:
            # Track the savings portion against net savings in/outflows:
            # (Currently we model all debt payments as lump sums
            # at a time given by the `DebtPaymentStrategy` class.)
            # TODO: Enable debt payments to be split up between multiple
            # timings:
            self.add_transaction(
                transaction=-debt_payments_from_savings[debt],
                when=self.debt_payment_strategy.timing,
                account=debt,
                account_transaction=debt_payments[debt]
            )

        # Now determine the total reductions across all reduction dicts:
        self.contribution_reductions[year] = (
            self.reduction_from_debt[year] +
            self.reduction_from_other[year]
        )

        # If there's contribution room left, use it to pay for any taxes
        # outstanding:
        # TODO: Determine whether tax liability should be assessed first.
        # And should it always come 100% from savings? Should this be 
        # configurable behaviour (e.g. via a `reinvest_tax_refund` value
        # stored... somewhere)?
        if self.tax_carryover[year] < 0:
            available = (
                self.gross_contributions[year]
                - self.contribution_reductions[year]
            )
            reduction = min(-self.tax_carryover[year], available)
            self.reduction_from_tax[year] = max(reduction, Money(0))
            # Update contribution reductions:
            self.contribution_reductions[year] += self.reduction_from_tax[year]
            # Add the net transaction:
            # NOTE: In addition to the TODO comment above re: allowing for
            # tax amounts from savings to be configured, we should allow
            # tax _timing_ to be configurable (presumably via the `Tax` class
            # and its subclasses, likely with a corresponding setting)
            # Currently, we record it as owing on the first day of the year.
            self.add_transaction(
                transaction=-self.reduction_from_tax[year],
                when=0
            )
        else:
            self.reduction_from_tax[year] = Money(0)

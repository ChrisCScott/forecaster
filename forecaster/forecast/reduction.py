""" This module provides a Forecast class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
"""

from forecaster.ledger import Money, recorded_property
from forecaster.accounts import Account, Debt
from forecaster.forecast.subforecast import SubForecast

class ReductionForecast(SubForecast):
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

        self.debt_payments = {}
        self.debt_payments_from_savings = {}

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        if isinstance(available, Account):
            total_available = available.max_outflow()
        else:
            total_available = sum(available)

        self.debt_payments = self.debt_payment_strategy(
            self.debts,
            total_available - self.reduction_from_other
        )
        # Then determine what portion was drawn from savings:
        self.debt_payments_from_savings = {
            debt: debt.payment_from_savings(
                amount=self.debt_payments[debt],
                base=debt.inflows
            ) for debt in self.debt_payments
        }

        # Apply debt payment transactions:
        for debt in self.debt_payments:
            # Track the savings portion against `available`:
            self.add_transaction(
                value=self.debt_payments_from_savings[debt],
                when=0.5,
                frequency=debt.payment_frequency,
                from_account=available,
                to_account=debt
            )
            # Track the non-savings portion as well, but don't deduct
            # from `available`
            self.add_transaction(
                value=
                    self.debt_payments[debt]
                     - self.debt_payments_from_savings[debt],
                when=0.5,
                frequency=debt.payment_frequency,
                from_account=None,
                to_account=debt
            )

        # Assume we make `other` reductions monthly:
        self.add_transaction(
            value=self.reduction_from_other,
            when=0.5,
            frequency=12,
            from_account=available,
            to_account=None
        )

    @recorded_property
    def reduction_from_debt(self):
        """ TODO """
        return sum(
            self.debt_payments_from_savings.values(),
            Money(0)
        )

    @recorded_property
    def reduction_from_other(self):
        """ TODO """
        # TODO: Include reduced contributions to pay for last year's
        # outstanding taxes?
        # NOTE: We'll add another reduction dict for childcare expenses
        # in a future version.
        # First determine miscellaneous other reductions (these take
        # priority because they're generally user-input):
        return Money(0)  # TODO

    @recorded_property
    def contribution_reductions(self):
        """ TODO """
        return self.reduction_from_debt + self.reduction_from_other

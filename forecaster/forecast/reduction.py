""" Provides a ReductionForecast class for use by Forecast. """

from forecaster.ledger import (
    Money, recorded_property, recorded_property_cached)
from forecaster.forecast.subforecast import SubForecast

class ReductionForecast(SubForecast):
    """ A forecast of each year's contribution reductions.

    Args:
        initial_year (int): The first year of the forecast.
        debts (Iterable[Debt]): Debts of the `people`.
        debt_payment_strategy (DebtPaymentStrategy):
            A callable object that determines the schedule of
            transactions for any debt payments during the year.
            See the documentation for `DebtPaymentStrategy`
            for acceptable args when calling this object.

    Attributes:
        reduction_from_debt (dict[int, Money]): The amount to be
            diverted from contributions to debt repayment in each year.
        reduction_from_other (dict[int, Money]): The amount to be
            diverted from contributions for other spending purposes in
            each year.
        reductions (dict[int, Money]): Amounts diverted
            from savings, such as certain debt repayments or childcare.
        net_contributions (dict[int, Money]): The total amount
            contributed to savings accounts.
    """

    # pylint: disable=not-an-iterable,unsubscriptable-object
    # Pylint can't tell that this class's `recorded_property_cached`
    # attributes return subscriptable objects.

    def __init__(
            self, initial_year, debts, debt_payment_strategy):
        """ Initializes an instance of ReductionForecast. """
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # NOTE Issue #53 removes this requirement.
        super().__init__(initial_year)
        # Store attributes:
        self.debts = debts
        self.debt_payment_strategy = debt_payment_strategy

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # First determine miscellaneous other reductions.
        # (These take priority because they're generally user-input.)
        # Assume we make these payments monthly.
        self.add_transaction(
            value=self.reduction_from_other,
            when=0.5,
            frequency=12,
            from_account=available,
            to_account=None
        )

        # Apply debt payment transactions:
        for debt in self.account_transactions:
            # Track the savings portion against `available`:
            self.add_transaction(
                value=self.payments_from_available[debt],
                when=0.5,
                frequency=debt.payment_frequency,
                from_account=available,
                to_account=debt
            )
            # Track the non-savings portion as well, but don't deduct
            # from `available`
            self.add_transaction(
                value=(
                    self.account_transactions[debt]
                    - self.payments_from_available[debt]),
                when=0.5,
                frequency=debt.payment_frequency,
                from_account=None,
                to_account=debt
            )

    @recorded_property_cached
    def account_transactions(self):
        """ Total amount repaid for each debt for the year. """
        return self.debt_payment_strategy(
            self.debts,
            self.total_available - self.reduction_from_other
        )

    @recorded_property_cached
    def payments_from_available(self):
        """ Amount repaid for each debt from `available` specifically. """
        return {
            debt: debt.payment_from_savings(
                amount=self.account_transactions[debt],
                base=debt.inflows
            ) for debt in self.account_transactions
        }

    @recorded_property
    def reduction_from_debt(self):
        """ Amount of potential savings diverted to debt. """
        # pylint: disable=no-member
        # account_transactions_from_available is a dict and so does
        # have a `values` member.
        return sum(
            self.payments_from_available.values(),
            Money(0)
        )

    @recorded_property
    def reduction_from_other(self):
        """ Amount of potential savings diverted to other reductions. """
        # NOTE: These amounts are generally user-input (i.e. they can
        # be set via an `input` dict at init time.) So although it
        # looks like we always return $0 here, in practice this won't
        # be called if another value has been provided elsewhere.
        return Money(0)

    @recorded_property
    def reductions(self):
        """ Total amount of potential savings diverted to reductions. """
        return self.reduction_from_debt + self.reduction_from_other

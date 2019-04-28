""" Provides a class for determining schedules of debt payments. """

from forecaster.strategy.base import Strategy, strategy_method
from forecaster.utility import Timing

class DebtPaymentStrategy(Strategy):
    """ Determines payments for a group of debts.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            transactions(). See its documentation for more info.

            Acceptable keys include:

            * "Snowball"
            * "Avalanche"

    Args:
        available (Money, dict[float, Money]): The amounts available
            for repayment across all accounts, either as a single
            Money value (in which case accounts' default timings
            are used) or as a mapping of {timing: value} pairs where
            positive values are treated as inflows usable as repayments.
        debts (list): Debts to repay.

    Returns:
        A dict of {Debt, Money} pairs where each Debt object
        is one of the input accounts and each Money object is a
        transaction for that account.
    """

    def _strategy_ordered(self, sorted_debts, available, assign_minimums=True):
        """ Proposes transactions based on an ordered list of debts.

        Args:
            sorted_debts (list[Debt]): A set of debt accounts,
                arranged in some order.
            available (Money): The amount available to repay
                debt from savings.
            assign_minimums (bool): Flag that determines whether
                minimum transactions should be assigned to each
                debt before assigning payments in list order.
                Optional.

        Returns:
            dict[Debt, Money]: A mapping of debts to payments.
        """
        # We need to know the total amount available to contribute and
        # also the timings of transactions. Depending on the structure
        # of `available`, we determine these differently.
        if isinstance(available, dict):
            # It's easier to update the total amount available rather
            # than track the time-series of data:
            total_available = sum(available.values())
            # `Timing` can ingest a Money-valued dict.
            timing = Timing(available)
        else:
            total_available = available
            timing = None  # Use default timing

        # Start with no transactions for each debt
        transactions = {}
        transactions_total = {}

        # Ensure all minimum payments are made, if requested:
        if assign_minimums:
            for debt in sorted_debts:
                # Add the minimum payments (this method accounts for
                # any pre-existing inflows and only returns the
                # minimum *additional* inflows)
                transactions[debt] = debt.min_inflows(timing)
                transactions_total[debt] = sum(transactions[debt].values())
                # And reduce the amount available for further payments
                # based on this debt's savings/living expenses settings:
                total_available -= debt.payment_from_savings(
                    amount=transactions_total[debt],
                    base=debt.inflows())

        # No need to continue if there's no money left:
        if total_available <= 0:
            return transactions

        # Now add further payments in the order given by the sorted
        # list of debts:
        for debt in sorted_debts:
            # Store the total amount of transactions we've allocated
            # to this debt which haven't yet been recorded as inflows:
            debt_transactions_total = sum(transactions[debt].values())
            # Determine the maximum payment we can make with what's
            # left:
            max_payment = debt.max_payment(
                savings_available=total_available,
                other_payments=debt_transactions_total,
                # TODO: Handle living expenses.
                timing=timing)

            # Reduce the pool of money remaining for further
            # payments accordingly:
            total_available -= debt.payment_from_savings(
                amount=max_payment,
                base=debt_transactions_total + debt.inflows())

            # Note that we add the payment to `transactions` *after*
            # decrementing `total_available`, which depends on the old
            # value for `transactions[debt]`
            # Use either the explicitly-provided timing or this debt's
            # default timing for the transactions:
            if timing is not None:
                debt_timing = timing
            else:
                debt_timing = debt.default_timing
            # Add a portion of `max_payment` at each timing in
            # proportion to the corresponding weight for the timing:
            for when, weight in debt_timing.items():
                value = max_payment * weight
                if when in transactions[debt]:
                    transactions[debt][when] += value
                else:
                    transactions[debt][when] = value

        return transactions

    # pylint: disable=W0613
    @strategy_method('Snowball')
    def strategy_snowball(self, debts, available, *args, **kwargs):
        """ Pays off the smallest debt first. """
        # Sort by increasing order of balance (i.e. smallest first):
        sorted_debts = sorted(
            debts, key=lambda account: abs(account.balance), reverse=False
        )
        return self._strategy_ordered(sorted_debts, available)

    @strategy_method('Avalanche')
    def strategy_avalanche(self, debts, available, *args, **kwargs):
        """ Pays off the highest-interest debt first. """
        # Sort by decreasing order of rate (i.e. largest first):
        sorted_debts = sorted(
            debts, key=lambda account: account.rate, reverse=True
        )
        return self._strategy_ordered(sorted_debts, available)

    # Overriding __call__ solely for intellisense purposes.
    # pylint: disable=W0235
    def __call__(self, debts, available, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        return super().__call__(debts, available, *args, **kwargs)

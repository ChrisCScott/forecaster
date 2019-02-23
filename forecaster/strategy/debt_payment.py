""" Provides a class for determining schedules of debt payments. """

from decimal import Decimal
from forecaster.strategy.base import Strategy, strategy_method
from forecaster.ledger import Money

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

        timing (str, Decimal): Transactions are modelled as lump sums
            which take place at this time.

            This is expressed according to the `when` convention
            described in `ledger.Account`.

    Args:
        available (Money): The total amount available for repayment
            across all accounts.
        debts (list): Debts to repay.

    Returns:
        A dict of {Debt, Money} pairs where each Debt object
        is one of the input accounts and each Money object is a
        transaction for that account.
    """

    def __init__(self, strategy, timing='end'):
        """ Constructor for DebtPaymentStrategy. """

        super().__init__(strategy)

        self.timing = timing

        # NOTE: We leave it to calling code to interpret str-valued
        # timing. (We could convert to `When` here - consider it.)
        self._param_check(self.timing, 'timing', (Decimal, str))

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
        # Start with a $0 transaction for each debt
        transactions = {debt: Money(0) for debt in sorted_debts}

        # Ensure all minimum payments are made
        if assign_minimums:
            for debt in sorted_debts:
                # Add the minimum payment (this method accounts for
                # any pre-existing inflows and only returns the
                # minimum *additional* inflows)
                transactions[debt] += debt.min_inflow(when=self.timing)
                # And reduce the amount available for further payments
                # based on this debt's savings/living expenses settings:
                available -= debt.payment_from_savings(
                    amount=transactions[debt],
                    base=debt.inflows)

        # No need to continue if there's no money left:
        if available <= 0:
            return transactions

        # Now add further payments in the order given by the sorted
        # list of debts:
        for debt in sorted_debts:
            # Determine the maximum payment we can make with what's
            # left:
            payment = debt.payment(
                savings_available=available,
                other_payments=transactions[debt],
                when=self.timing
            )

            # Reduce the pool of money remaining for further
            # payments accordingly:
            available -= debt.payment_from_savings(
                amount=payment,
                base=transactions[debt] + debt.inflows
            )
            # Note that we add the payment to `transactions` *after*
            # decrementing `available`, which depends on the old
            # value for `transactions[debt]`
            transactions[debt] += payment

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

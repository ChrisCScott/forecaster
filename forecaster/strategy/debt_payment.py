""" Provides a class for determining schedules of debt payments. """

from decimal import Decimal
from forecaster.strategy.base import Strategy, strategy_method


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

    # pylint: disable=W0613
    @strategy_method('Snowball')
    def strategy_snowball(self, available, debts, *args, **kwargs):
        """ Pays off the smallest debt first. """
        # First, ensure all minimum payments are made.
        transactions = {
            debt: debt.min_inflow(when=self.timing)
            for debt in debts
        }

        available -= sum(transactions[debt] * debt.reduction_rate
                         for debt in debts)

        if available <= 0:
            return transactions

        accelerated_debts = {
            debt for debt in debts
            if debt.max_inflow(self.timing) > transactions[debt]}
        # Now we increase contributions to any accelerated debts
        # (non-accelerated debts can just have minimum payments made,
        # handled above). Here, increase contributions of the smallest
        # debt first, then the next, and so on until there's no money
        # left to allocate to debt repayment:
        for debt in sorted(
            accelerated_debts, key=lambda x: abs(x.balance), reverse=False
        ):
            # Debts that don't reduce savings can be ignored - assume
            # they're fully repaid in the first year.
            if debt.reduction_rate == 0:
                transactions[debt] = debt.max_inflow(self.timing)
                continue

            # Payment is either the outstanding balance or the total of
            # the available money remaining for payments
            payment = min(
                debt.max_inflow(self.timing) - transactions[debt],  # balance
                available / debt.reduction_rate  # money available
            )
            transactions[debt] += payment
            # `available` is at least partially taken from savings;
            # only deduct that portion of the payment from `available`
            available -= payment * debt.reduction_rate

        return transactions

    @strategy_method('Avalanche')
    def strategy_avalanche(self, available, debts, *args, **kwargs):
        """ Pays off the highest-interest debt first. """
        # First, ensure all minimum payments are made.
        transactions = {
            debt: debt.min_inflow(when=self.timing)
            for debt in debts
        }

        available -= sum(transactions[debt] * debt.reduction_rate
                         for debt in debts)

        if available <= 0:
            return transactions

        accelerated_debts = {
            debt for debt in debts
            if debt.max_inflow(self.timing) > transactions[debt]}
        # Now we increase contributions to any accelerated debts
        # (non-accelerated debts can just have minimum payments made,
        # handled above). Here, increase contributions of the largest
        # rate first, then the next, and so on until there's no money
        # left to allocate to debt repayment:
        for debt in sorted(
            accelerated_debts, key=lambda x: x.rate, reverse=True
        ):
            # Debts that don't reduce savings can be ignored - assume
            # they're fully repaid in the first year.
            if debt.reduction_rate == 0:
                transactions[debt] = debt.max_inflow(self.timing)
                continue

            # Payment is either the outstanding balance or the total of
            # the available money remaining for payments
            payment = min(
                debt.max_inflow(self.timing) - transactions[debt],  # balance
                available / debt.reduction_rate  # money available
            )
            transactions[debt] += payment
            # `available` is at least partially taken from savings;
            # only deduct that portion of the payment from `available`
            available -= payment * debt.reduction_rate

        return transactions

    # Overriding __call__ solely for intellisense purposes.
    # pylint: disable=W0235
    def __call__(self, available, debts, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        return super().__call__(available, debts, *args, **kwargs)

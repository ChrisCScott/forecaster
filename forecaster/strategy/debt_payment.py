""" Provides a class for determining schedules of debt payments. """

from forecaster.strategy.base import Strategy, strategy_method
from forecaster.strategy.transaction import TransactionTraversal

# Expose the logic for turning iterables of debts into priority trees
# here so that, if client code wants, it can build a subtree for debts
# and insert it into a larger tree for handling all contributions
# to accounts (i.e. without invoking DebtPaymentStrategy at all.)

def avalanche_priority(debts):
    """ A priority tree of debts according to the avalanche strategy.

    Under the avalanche strategy, accounts with the highest rates are
    repaid first, regardless of balance size.

    This uses the priority tree pattern of `TransactionStrategy`; see
    that class for more information.

    Returns:
        list[Debt]: An ordered list of Debts.
    """
    return sorted(
        debts, key=lambda account: account.rate, reverse=True)

def snowball_priority(debts):
    """ A priority tree of debts according to the snowball strategy.

    Under the avalanche strategy, accounts with the lowest balances are
    repaid first, regardless of their rates.

    This uses the priority tree pattern of `TransactionStrategy`; see
    that class for more information.

    Returns:
        list[Debt]: An ordered list of Debts.
    """
    return sorted(
        debts, key=lambda account: abs(account.balance), reverse=False)

class DebtPaymentStrategy(Strategy):
    """ Determines payments for a group of debts.

    This is simply a convenient wrapper for `TransactionStrategy`.

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
        dict[Debt, dict[Decimal, Money]]: A mapping of debts to
        transactions.
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
        strategy = TransactionTraversal(priority=sorted_debts)
        return strategy(available, assign_min_first=assign_minimums)

    # pylint: disable=W0613
    @strategy_method('Snowball')
    def strategy_snowball(self, debts, available, *args, **kwargs):
        """ Pays off the smallest debt first. """
        return self._strategy_ordered(snowball_priority(debts), available)

    @strategy_method('Avalanche')
    def strategy_avalanche(self, debts, available, *args, **kwargs):
        """ Pays off the highest-interest debt first. """
        return self._strategy_ordered(avalanche_priority(debts), available)

    # Overriding __call__ solely for intellisense purposes.
    # pylint: disable=W0235
    def __call__(self, debts, available, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        return super().__call__(debts, available, *args, **kwargs)

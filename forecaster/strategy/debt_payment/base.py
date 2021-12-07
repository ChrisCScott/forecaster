""" Provides a class for determining schedules of debt payments. """

from forecaster.strategy.base import Strategy, strategy_method
from forecaster.strategy.transaction import TransactionTraversal
from forecaster.strategy.debt_payment.util import (
    avalanche_priority, snowball_priority, AVALANCHE_KEY, SNOWBALL_KEY)
from forecaster.utility.precision import HighPrecisionHandler


class DebtPaymentStrategy(Strategy, HighPrecisionHandler):
    """ Determines payments for a group of debts.

    This is simply a convenient wrapper for `TransactionTraversal`.

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
        high_precision (Callable[[float], T]): A conversion method
            that converts float internal constants to a high-precision
            numerical type `T`. Optional.

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
        strategy = TransactionTraversal(
            priority=sorted_debts, high_precision=self.high_precision)
        result = strategy(available, assign_min_first=assign_minimums)
        return result

    @strategy_method(SNOWBALL_KEY)
    def strategy_snowball(self, debts, available, *args, **kwargs):
        """ Pays off the smallest debt first. """
        # pylint: disable=unused-argument
        return self._strategy_ordered(snowball_priority(debts), available)

    @strategy_method(AVALANCHE_KEY)
    def strategy_avalanche(self, debts, available, *args, **kwargs):
        """ Pays off the highest-interest debt first. """
        # pylint: disable=unused-argument
        return self._strategy_ordered(avalanche_priority(debts), available)

    def __call__(self, debts, available, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        # Overriding __call__ solely for intellisense purposes.
        # pylint: disable=useless-super-delegation
        return super().__call__(debts, available, *args, **kwargs)

""" Provides Strategy-type wrappers for TransactionTraversal. """

from forecaster.accounts.debt import Debt
from forecaster.strategy.base import Strategy, strategy_method
from forecaster.strategy.debt_payment import (
    PRIORITY_METHODS, AVALANCHE_KEY)
from forecaster.strategy.transaction.base import TransactionTraversal

class TransactionStrategy(Strategy):
    """ Determines transactions to/from a group of accounts.

    This is simply a convenient wrapper for `TransactionTraversal`. It
    generates a suitable `priority` tree based on the selected strategy
    and then traverses the tree to generate transactions for the
    accounts.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            transactions(). See its documentation for more info.

            Acceptable keys include:

            * "TODO"
            * "TODO"
        debt_strategy (str): A key in `DebtPayment.strategies`.
            Strategies will prioritize debts according to this strategy.
            See `DebtPaymentStrategy` for more information.
        high_interest_threshold (Decimal): Debt accounts with this rate
            of interest or greater will be considered high-interest
            and those with lower interest rates will be considered
            low-interest. Some strategies use this division to determine
            which debts to prioritize ahead of investments.

            Optional. If not provided, all debts are considered
            high-interest.

    Args:
        available (dict[float, Money]): The amounts to be
            contributed to (or withdrawn from, if negative) the
            accounts, as a mapping of {timing: value} pairs.

    Returns:
        dict[Account, dict[Decimal, Money]]: A mapping of accounts to
        transactions.
    """

    # TODO: Reimplement the interface of AccountTransactionStrategy,
    # allowing user to provide a weighted list/dict of account types.
    # This method can then turn each account type into an equal-weighted
    # dict of accounts of that type.
    # Examples:
    #   in: [RRSP, TFSA, TaxableAccount]
    #   out: [{rrsp2: 1, rrsp2: 1}, {tfsa1: 1, tfsa2: 1}, taxable_acct]
    #
    #   in: [{RRSP: 1, TFSA: 1}, TaxableAccount]
    #   out: [{
    #           {rrsp1: 1, rrsp2: 1}: 1,
    #           {tfsa1: 1, tfsa2: 1}: 1},
    #         taxable_acct]
    # This mimics the behaviour of AccountGroups in the old
    # AccountTransactionStrategy.
    #
    # AccountTransactionStrategy had two __init__ args:
    #   - `strategy (str)` (only "Ordered" or "Weighted" were accepted)
    #   - `weights` (dict[type, Decimal])`
    # It had two __call__ args as well:
    #   - `total (Money)`
    #   - `accounts (Iterable[Account])`
    #
    # TransactionStrategy could use a similar set of signatures,
    # although it would be preferable to swap `total` with
    # `available (dict[Decimal, Money])` for consistency with other
    # modules.
    #
    # Consider how to address the handling of Debt accounts. The old
    # `AccountTransactionStrategy` wasn't designed for it, since `Debt`
    # was assumed to be handled totally separately from other accounts.
    # That's not a good assumption. But if an assumption of this class
    # is that all accounts of the same type receive the same treatment,
    # that's going to lead to issues as well. It's common to treat debts
    # differently based on properties - for example, high-interest debts
    # might be paid off first, with lower-interest debts being repaid
    # after other investments or perhaps in weighted combination with
    # those other investments.
    #
    # Consider providing an optional `high_interest_threshold` __init__
    # arg. If provided, any Debt accounts with this interest rate or
    # greater are repaid first (i.e. create a priority node of the form
    # `[*high_interest_debts, other_accounts]`, where `other_accounts`
    # is a priority tree constructed according to the selected strategy)
    #
    # Future revisions will need to consider the question of how to deal
    # with, say, ordering contributions to RRSPs where plannees have
    # different taxable income. That goes deeper into country-specific
    # tax planning, though, and can likely be safely carved off into
    # a submodule of `canada` (which probably won't even subclass this
    # class)

    def __init__(
            self, strategy, weights,
            debt_strategy=None, high_interest_threshold=None):
        """ Init TransactionStrategy. """
        super().__init__(strategy)

        # Store args:
        self.weights = weights
        if debt_strategy is None:
            # Default to "Avalanche" (which has superior performance to
            # Snowball, though is admittedly less popular.)
            debt_strategy = AVALANCHE_KEY
        self.debt_strategy = debt_strategy
        self.high_interest_threshold = high_interest_threshold

        # Set up private vars for tracking cached priority trees:
        # (This is some premature optimization which perhaps should
        # be cut entirely in early versions...)
        self._cache_keys = None
        self._cached_traverse = None

    @strategy_method('Ordered')
    def strategy_ordered(
            self, accounts, *args, priority=None, **kwargs):
        """ TODO """
        # TODO: Build and return a priority tree
        pass

    # TODO: Decide on a name for this stragegy.
    @strategy_method('Weighted')
    def strategy_weighted(
            self, accounts, *args, priority=None, **kwargs):
        """ TODO """
        # TODO: Build and return a priority tree
        pass

    def _get_traverse(self, accounts, *args, **kwargs):
        """ Returns a cached TransactionTraversal if it can be re-used. """
        # Don't use the cached traverse if one isn't cached!
        if self._cached_traverse is None:
            return False
        # Use the cache if the same accounts and strategy are being used
        is_cache_valid = (accounts, self.strategy) == self._cache_keys
        # If the cache is not valid, regenerate it:
        if not is_cache_valid:
            # Generate new TransactionTraverse:
            priority = super().__call__(
                accounts, priority=priority, *args, **kwargs)
            self._cached_traverse = TransactionTraversal(priority=priority)
            # Keep track of the values we used to generate it:
            self._cache_keys = (accounts, self.strategy)
        return self._cached_traverse

    def debt_priorities(self, accounts):
        """ TODO """
        # Get all debts with balances owing:
        debts = {
            account for account in accounts
            if isinstance(account, Debt) and account.balance < 0}
        # Get the method that turns a set of debts into an ordered
        # list (or other priority tree):
        priority_method = PRIORITY_METHODS[self.debt_strategy]
        # If we're distinguishing high-interest from low-interest debts,
        # separate them out here:
        if self.high_interest_threshold is not None:
            low_interest_debts = {
                debt for debt in debts
                if debt.rate < self.high_interest_threshold}
            high_interest_debts = {
                debt for debt in debts if debt not in low_interest_debts}
        # Otherwise, consider all debts to be high-interest:
        else:
            low_interest_debts = set()
            high_interest_debts = debts
        # Convert the sets of debts into priority trees
        # (or assign None if there are no debts of a given type)
        if high_interest_debts:
            high_interest_priority = priority_method(high_interest_debts)
        else:
            high_interest_priority = None
        if low_interest_debts:
            low_interest_priority = priority_method(low_interest_debts)
        else:
            low_interest_priority = None
        return (high_interest_priority, low_interest_priority)

    def __call__(self, available, accounts, *args, **kwargs):
        """ Returns a dict of account: transaction pairs. """
        # If nothing has changed since last invocation, save some time
        # by re-using the same TransactionTraverse:
        traverse = self._get_traverse(accounts, *args, **kwargs)
        # Prepend high-interest debt repayment:
        high_interest_priority, low_interest_priority = self.debt_priorities(
            accounts)
        if high_interest_priority is not None and high_interest_priority:
            pass # TODO
        return traverse(available)

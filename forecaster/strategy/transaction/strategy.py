""" Provides Strategy-type wrappers for TransactionTraversal. """

from collections import defaultdict
from forecaster.accounts.debt import Debt
from forecaster.strategy.base import Strategy, strategy_method
from forecaster.strategy.debt_payment.util import (
    PRIORITY_METHODS, AVALANCHE_KEY)
from forecaster.strategy.transaction.base import TransactionTraversal
from forecaster.strategy.transaction.node import TransactionNode
from forecaster.utility.precision import HighPrecisionOptionalPropertyCached

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

    # NOTE: Consider the question of how to deal with more complex
    # priority structures, e.g. where you might want to contribute first
    # to an RRSP and spousal RRSP with the same contributor (a
    # higher-earner) before contributing to another RRSP and spousal
    # RRSP with another contributor (a lower-earner).
    # That goes deeper into country-specific tax planning. Should these
    # country-specific scenarios be carved off into country-specific
    # submodules? Is there a generic way to implement this class so that
    # it allows for accounts of the same type to be divided up according
    # to come criterion while still allowing it to be useful?
    # In short: can we abandon type-based approaches entirely?

    # high_interest_threshold supports high-precision numerical types:
    high_interest_threshold = HighPrecisionOptionalPropertyCached()

    def __init__(
            self, strategy, weights,
            debt_strategy=None, high_interest_threshold=None,
            high_precision=None):
        """ Init TransactionStrategy. """
        super().__init__(strategy, high_precision=high_precision)

        # Store args:
        self.weights = weights
        if debt_strategy is None:
            # Default to "Avalanche" (which has superior performance to
            # Snowball, though is admittedly less popular.)
            debt_strategy = AVALANCHE_KEY
        self.debt_strategy = debt_strategy
        self.high_interest_threshold = high_interest_threshold

    @strategy_method('Ordered')
    def strategy_ordered(
            self, groups, *args, subtrees=None, **kwargs):
        """ Generates a priority tree with ordered accounts.
        
        This strategy treats the values of `TransactionStrategy.weights`
        as ordinals. The key with the lowest value (usually 1) are
        first in the order, followed by the next-lowest key.

        This method does not translate the keys of
        `TransactionStrategy.weights` into accounts. That should be done
        in advance, so that `groups` contains only sets of accounts
        mapped to weights. Each group should have a unique weight,
        otherwise the behaviour is undefined.
        _This method will fail if `groups` contains a `type` object!_

        Where multiple accounts are mapped to a given weight (by being
        contained by the same group), they will be added to the priority
        tree as a weighted node. That node will be nested within an
        ordered tree.

        Args:
            groups (dict[frozenset[Account], Decimal]): Sets of accounts
                mapped to the order (i.e. weight) associated with the
                set of accounts. Weights should be unique, otherwise
                behaviour is undefined.
            subtrees (dict[frozenset[Account], Any]): Maps groups to
                priority trees. If a given group is in `subtrees`, the
                corresponding value in `subtrees` will be inserted into
                the priority tree instead of whatever this method would
                ordinarily generate (e.g. an equal-weighted dict).

        Returns:
            list((TransactionNode, list[Any], dict[Any])): An ordered
            priority tree, potentially with nested priority trees of
            arbitrary form (if provided by `subtrees`, otherwise all
            nested trees are equal-weighted dicts).
        """
        # pylint: disable=unused-argument
        # *args, **kwargs provided to make extending by subclass easier.

        # TODO: Deal with multiple groups having the same weight
        # (swap in an equal-weighted dict rather than append?)

        # Sort groups according to their weights and then swap in
        # priority trees for each account type (either as provided in
        # `subtrees` or according to a default, e.g. equal-weighted).
        priority = []
        for group in sorted(groups, key=groups.get):
            # Add the accounts of each group, in order.
            subtree = self._get_subtree(group, subtrees)
            priority.append(subtree)
        return priority

    @strategy_method('Weighted')
    def strategy_weighted(
            self, groups, *args, subtrees=None, **kwargs):
        """ Generates a priority tree with ordered accounts.

        This strategy treats the values of `TransactionStrategy.weights`
        as proportional weights. Each group will receive its associated
        weight. Weights do not need to be unique between groups.

        This method does not translate the keys of
        `TransactionStrategy.weights` into accounts. That should be done
        in advance, so that `groups` contains only sets of accounts
        mapped to weights.
        _This method will fail if `groups` contains a `type` object!_

        Where multiple accounts are mapped to a given weight (by being
        contained by the same group), they will be added to the priority
        tree as a weighted node. That node will be nested within a
        weighted tree.

        Args:
            groups (dict[frozenset[Account], Decimal]): Sets of accounts
                mapped to the weight associated with the set.
            subtrees (dict[frozenset[Account], Any]): Maps groups to
                priority trees. If a given group is in `subtrees`, the
                corresponding value in `subtrees` will be inserted into
                the priority tree instead of whatever this method would
                ordinarily generate (e.g. an equal-weighted dict).

        Returns:
            dict((TransactionNode, list[Any], dict[Any]), Decimal):
            A weighted priority tree, potentially with nested priority
            trees of arbitrary form (if provided by `subtrees`,
            otherwise all nested trees are equal-weighted dicts).
        """
        # pylint: disable=unused-argument
        # *args, **kwargs provided to make extending by subclass easier.

        # Map each group to its corresponding weight; no need to sort.
        priority = {}
        for group, weight in groups.items():
            # Get the subtree for this group and wrap it in a
            # TransactionNode to ensure that it can be used as a key
            # in the top-level `priorty` tree (which is a dict).
            subtree = TransactionNode(self._get_subtree(group, subtrees))
            priority[subtree] = weight
        return priority

    @staticmethod
    def _get_subtree(group, subtrees):
        """ Generates a priority tree for a given group's accounts. """
        # If a subtree has been specified in `subtrees`, use that:
        if subtrees is not None and group in subtrees:
            return subtrees[group]
        # If the group has only one member, use that account directly:
        elif len(group) == 1:
            return next(iter(group))
        # If the group has more than one member, use a weighted subtree,
        # with all accounts getting equal weight:
        else:
            return {account: 1 for account in group}

    def _weight_account_groups(self, accounts):
        """ Groups accounts by their weights.

        This method identifies a weight key for each account in
        `accounts` (via `_get_weight_key`), groups accounts with common
        weight keys, and returns a mapping from groups to their weights.

        Arg:
            accounts (set[Account]): A collection of accounts.

        Returns:
            dict[frozenset[Account], Number]: A mapping of account
            groups (where each account in a group shares a common weight
            key) to weights.
        """
        account_keys = defaultdict(set)
        # Build a map of key: set[Account] pairs, where each set is the
        # set of accounts with the same key.
        for account in accounts:
            # Find the key in `self.weights` that best matches this
            # account (or None if no key is appropriate):
            key = self._get_weight_key(account)
            if key in self.weights:
                account_keys[key].add(account)
        # Now reverse that into a map of frozenset[Account]: weight
        # pairs:
        groups = {
            frozenset(group): self.weights[key]
            for key, group in account_keys.items()}
        return groups

    def _get_weight_key(self, account):
        """ Gets the most relevant key for `account` in `weights`. """
        # If this object's type is referenced by name, use that:
        key = type(account).__name__
        if key in self.weights:
            return key
        # Otherwise, type each superclass (in MRO order).
        for super_type in type(account).__mro__:
            key = super_type.__name__
            if key in self.weights:
                return key
        # If none of the above worked, there's no appropriate key.
        return None

    def divide_debts(self, accounts):
        """ Separates high- and low-interest debts.

        Args:
            accounts (Iterable[Account]): A collection of accounts,
                which may or may not contain any `Debt` members.
        
        Returns:
            tuple[frozenset[Account], frozenset[Account]]: All
            `Debt`-type accounts in `accounts` with outstanding
            balances, as a `(low_interest, high_interest)` tuple.
        """
        # Get all debts with balances owing:
        debts = {
            account for account in accounts
            if isinstance(account, Debt) and account.balance < 0}
        # If we're distinguishing high-interest from low-interest debts,
        # separate them out here:
        if self.high_interest_threshold is not None:
            low_interest_debts = frozenset(
                debt for debt in debts
                if debt.rate < self.high_interest_threshold)
            high_interest_debts = frozenset(
                debt for debt in debts if debt not in low_interest_debts)
        # Otherwise, consider all debts to be low-interest:
        else:
            low_interest_debts = frozenset(debts)
            high_interest_debts = frozenset()
        return low_interest_debts, high_interest_debts

    def debt_priority(self, debts):
        """ Converts a collection of debts into a priority tree.
        
        This method uses the selected priority method (e.g.
        `avalanche_priority`, `snowball_priority`) to convert `debts`
        into a priority tree.

        Arg:
            debt (set[Debt]): Debts to organize into a priority tree.

        Returns:
            list[Debt]: An ordered list of `Debt` objects, with the
            order determined according to `debt_strategy`. This is a
            simple priority tree that can be embedded into a larger
            tree.
        """
        # Convert the sets of debts into priority trees
        # (or assign None if there are no debts of a given type)
        if debts is not None and debts:
            # Get the method that turns a set of debts into an ordered
            # list (or other priority tree):
            priority_method = PRIORITY_METHODS[self.debt_strategy]
            # Use it to generate a priority tree:
            priority = priority_method(debts)
        else:
            priority = None
        return priority

    def __call__(self, available, accounts, *args, **kwargs):
        """ Returns a dict of account: transaction pairs. """
        # Debts get special treatment, so separate them out here:
        low_interest_debts, high_interest_debts = self.divide_debts(accounts)
        # Get priority trees for each debt. These will be inserted into
        # the final priority tree differently (in-place replacement for
        # low-interest, prepending for high-interest.)
        low_interest_priority = self.debt_priority(low_interest_debts)
        high_interest_priority = self.debt_priority(high_interest_debts)

        # Group together accounts that share weights (and map them to
        # those weights for convenience):
        groups = self._weight_account_groups(
            set(accounts) - high_interest_debts)

        # Ensure that low-interest debts are properly ordered, rather
        # than assigned some default order based on their common typing:
        subtrees = {low_interest_debts: low_interest_priority}

        # Get the basic priority tree based on this strategy:
        priority = super().__call__(
            groups, *args, subtrees=subtrees, **kwargs)

        # Prioritize high-interest debts repayment, if provided:
        if high_interest_priority is not None and high_interest_priority:
            # Prepend the high-interest debts, so that they are repaid
            # before any discretionary money is allocated to other
            # accounts (i.e. money other than minimums):
            priority = [high_interest_priority, priority]

        # Traverse the tree and return the results:
        traverse = TransactionTraversal(
            priority=priority, high_precision=self.high_precision)
        return traverse(available)

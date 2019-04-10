""" Provides a class for determining schedules of transactions.

These transaction schedules determine when transactions occur, in what
amounts, and to which accounts. """

import collections
from copy import copy
from forecaster.utility import add_transactions, subtract_transactions

class TransactionStrategy(object):
    """ Determines transactions to/from accounts based on a priority.

    Instances of this class receive a structured collection of `Account`
    objects and traverses them breadth-first to determine the
    transactions for each account. The collection can be nested and may
    involve several types.

    `dict` objects map accounts to weights (without any order between
    accounts), whereas `list` objects provide an ordered sequence of
    accounts. Accounts do not need to be unique between collections.

    Each element or subelement of `priority` may be provided with a
    maximum inflow/outflow limit which is enforced alongside each
    Account's intrinsic limits. To do this, use a tuple of the
    form `(node, limit)`. Example: `([account1, account2], Money(100))`
    is an ordered list of accounts where the total to be contributed to
    all accounts in the list will not exceed $100.

    As with all `Strategy` objects, objects of this type are callable.

    Examples:
        # Collections can be nested (note also that `account2` repeats):
        subgroup = {account1: 0.5, account2: 0.5}
        priority = [subgroup, account2]  # valid priority tree
        strategy = TransactionStrategy(priority)
        transactions = strategy(available)

        # We can limit the total amount to contribute to `subgroup`
        # (i.e. the equal-weighted group of account1 and account2)
        # by using a tuple, as follows:
        priority = [(subgroup, Money(100)), account2]
        strategy = TransactionStrategy(priority)
        transactions = strategy(available)
        # The result is that up to $100 will be contributed equally to
        # `account1` and `account2`, with any excess going to `account2`

    Args:
        priority [list[Any], dict[Any, Decimal]]: The (nested)
            collection of Accounts.

    Returns:
        dict[Account, dict[Decimal, Money]]: A mapping of accounts to
            transactions to (positive) or from (negative) those
            accounts. No `list`, `dict`, or other sub-collection is
            used as a key. Only the leaf node `Account`-like objects of
            the tree defined by `priority` are used as keys.
    """
    def __init__(self, priority):
        """ TODO """
        self.priority = priority
        # TODO: Add transaction group functionality
        # (e.g. to deal with contribution_group behaviour for
        # max_inflows()).
        # This can likely be added most generically by simply requiring
        # calling code to provide a set of groups for each of the four
        # transaction methods (max_inflow, max_outflow, etc.).
        # It will likely be necessary to add an arg. to methods like
        # `Account.max_inflows` to allow for planned but not yet
        # recorded transactions to accounted for.
        # (Example: If my contribution group allows for at most $100
        # in inflows, and I already plan to add $100 to account_1,
        # then I should be able to tell account_2, which belongs to the
        # same contribution_group, that $100 of contribution space is
        # already spoken for.)

    def __call__(self, available, total=None, assign_min_first=True):
        """ TODO """
        # We'll build of a dict of account: transactions pairs.
        # Initialize that here, to be populated during tree traversal:
        transactions = collections.defaultdict(dict)
        # By default, use up all money in `available`, unless we're
        # specifically told to use less:
        if total is None:
            total = sum(available.values())
        # Determine which methods of `Account` objects to call during
        # tree traversal:
        if total > 0:  # inflows
            min_method, max_method = "min_inflows", "max_inflows"
        elif total < 0:  # outflows
            min_method, max_method = "min_outflows", "max_outflows"
        else:  # No transactions
            return {}
        # Unless the user tells us not to assign minimums, we will
        # traverse the tree twice. To ensure that we respect per-node
        # limits, we will record all transactions to a memo:
        # NOTE: We use a list instead of a dict because nodes are not
        # necessarily unique!
        memo = []
        # First traverse to allocate mins (in priority order)
        if assign_min_first:
            min_transactions = self._process_node(
                self.priority, available, total, transactions, min_method,
                _memo=memo)
            # Other arguments are mutated, but not total, so update here
            total -= sum(min_transactions.values())
        # Then traverse again to allocate remaining money:
        self._process_node(
            self.priority, available, total, transactions, max_method,
            _last_memo=memo)
        return transactions

    def _process_node(
            self, node, available, total, transactions, method_name,
            _memo=None, _last_memo=None, **kwargs):
        """ TODO """
        if _memo is None:
            _memo = []

        if isinstance(node, list):
            method = self._process_node_list
        elif isinstance(node, dict):
            method = self._process_node_dict
        elif isinstance(node, tuple):
            method = self._process_node_tuple
        else:
            # Anything not recognized above will be treated as a leaf
            # node, i.e. an account. Such nodes should provide a method
            # with name `method_name`!
            method = self._process_node_account
        # Determine the treatment of this node:
        node_transactions = method(
            node, available, total, transactions, method_name,
            _memo=_memo, _last_memo=_last_memo, **kwargs)
        # Record the result of this traversal in `_memo`.
        _memo.append(node_transactions)
        return node_transactions

    def _process_node_list(
            self, node, available, total, transactions, method_name, **kwargs):
        """ TODO """
        node_transactions = {}
        # Iterate over in order:
        for child in node:
            # Recurse onto each element to obtain the total transactions
            # to be added to it.
            child_transactions = self._process_node(
                child, available, total, transactions, method_name, **kwargs)
            # Update `total` before recursing onto the next element.
            # (Note that `transactions` and `available` are mutated by
            # `_process_node_account` when transactions against specific
            # accounts are proposed, so no need to update them here.)
            total -= sum(child_transactions.values())
            # We return the combination of all transactions for this
            # node, as if they were to one account - i.e. not indexed
            # by account. Update those transactions here.
            add_transactions(node_transactions, child_transactions)
            # Stop early if there's no money left to allocate
            # NOTE: Consider whether this breaks `_memo` functionality,
            # since traversals may differ in where they break.
            if total == 0:
                break
        return node_transactions

    def _process_node_dict(
            self, node, available, total, transactions, method_name, **kwargs):
        """ TODO """
        # Set up local variables:
        node_transactions = {}
        limited_accounts = set()
        # We'll want to normalize weights later, so sum weights now:
        total_weight = sum(node.values())

        # Iterate over each element in arbitrary order:
        for child, weight in node.items():
            # Recurse onto each element to obtain the total transactions
            # to be added to it, but reduce `total` according to the
            # normalized weight of each element.
            child_total = total * (weight / total_weight)
            child_transactions = self._process_node(
                child, available, child_total, transactions, method_name,
                **kwargs)
            # If we weren't able to contribute the full amount available
            # the flag this account so that we can remove during recurse
            if sum(child_transactions.values()) != child_total:
                limited_accounts.add(child)
            # Pool this child's transactions with the node's:
            add_transactions(node_transactions, child_transactions)

        # `available` and `transactions` were updated by `_process_node`
        # but we need to update `total` manually:
        total -= sum(node_transactions.values())

        # If there's more money available and one or more of the
        # accounts has hit its limit, but the remaining accounts might
        # still have space. Remove any maxed-out accounts and recurse:
        # TODO: Check for rounding errors.
        if total != 0 and limited_accounts:
            # Now that we have identified accounts that can't take any
            # more transactions, remove them from `node` (well, from a
            # copy of `node` to avoid mutation) and recurse:
            node_copy = copy(node)
            for child in limited_accounts:
                del node_copy[child]
            node_copy_transactions = self._process_node_dict(
                node_copy, available, total, transactions, method_name,
                **kwargs)

            # Remember to add the recurse results to the return value!
            add_transactions(node_transactions, node_copy_transactions)

        return node_transactions

    def _process_node_tuple(
            self, node, available, total, transactions, method_name,
            _memo, _last_memo, **kwargs):
        """ TODO """
        # Tuples should be in (node, limit) form. Get each element now:
        node, limit = node

        # Reduce `limit` by the sum of all transactions recorded against
        # this node during previous traversals:
        if _last_memo is not None and len(_memo) < len(_last_memo):
            limit -= sum(_last_memo[len(_memo)].values())

        # Ensure that `total` is no larger than `limit`
        # (but only if they have the same sign):
        if total >= 0 and limit >= 0:
            total = min(total, limit)
        elif total <= 0 and limit <= 0:
            total = max(total, limit)

        return self._process_node(
            node, available, total, transactions, method_name,
            _memo=_memo, _last_memo=_last_memo, **kwargs)

    def _process_node_account(
            self, node, available, total, transactions, method_name, **kwargs):
        """ TODO """
        # pylint: disable=unused-argument
        # We provide the kwargs argument to enforce consistency between
        # _process_* methods.

        # Get the bound method for `method_name` for this account:
        # NOTE: This can raise an exception if the account doesn't have
        # a method with that name. It should be handled by client code.
        method = getattr(node, method_name)
        # Get the transactions for the account:
        account_transactions = method(available, total)

        # Add these new transactions to `available` and `transactions`:
        # Money added to the account is _removed_ from `available`:
        subtract_transactions(available, account_transactions)
        # Whereas it is added to the account's entry in `transactions`:
        # (It is a defaultdict, so there's no need to check keys)
        add_transactions(transactions[node], account_transactions)

        return account_transactions

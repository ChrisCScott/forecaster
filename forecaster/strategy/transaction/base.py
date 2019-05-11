""" Provides a class for determining schedules of transactions.

These transaction schedules determine when transactions occur, in what
amounts, and to which accounts.
"""

import collections
from copy import copy
from decimal import Decimal
from forecaster.ledger import Money
from forecaster.utility import (
    add_transactions, subtract_transactions, EPSILON_MONEY, EPSILON)
from forecaster.accounts.util import LIMIT_TUPLE_FIELDS
from forecaster.strategy.transaction.util import (
    LimitTuple, transaction_default_methods, group_default_methods)
from forecaster.strategy.transaction.node import TransactionNode


class TransactionTraversal:
    """ Determines transactions to/from accounts based on a priority.

    Instances of this class receive a structured collection of `Account`
    objects and traverses them as a tree to determine the transactions
    for each account. Each element of the collection is a node of the
    tree and may be one of several types. Nodes need not be unique.

    Nodes may be native `dict`, `list`, and `tuple` objects.
    `dict` elements are unordered; each key is a child node and the
    corresponding value is a weight. `list` or `tuple` objects provide
    an ordered sequence of child nodes. (Tip: use `tuple` for nodes that
    need to be stored as keys in a `dict`). `Account` objects (or
    similar) are leaf nodes.

    Nodes may be `TransactionNode` objects, which provide richer
    semantics. For example, a `TransactionNode` can provide limits on
    min/max in/outflows; these are enforced when assigning transactions
    to leaf nodes if they are stricter than leaf nodes' own intrinsic
    limits. See documentation for `TransactionNode` for more detail.

    As with all `Strategy` objects, objects of this type are callable
    and will return a result resulting from their various settings; in
    this case, a mapping of `Account` objects to transaction objects.

    Examples:
        # Collections can be nested (note also that `account2` repeats):
        subgroup = {account1: 0.5, account2: 0.5}
        priority = [subgroup, account2]  # valid priority tree
        strategy = TransactionStrategy(priority)
        transactions = strategy(available)

        # We can limit the total amount to contribute to `subgroup`
        # (i.e. the equal-weighted group of account1 and account2)
        # by using a single-element dict, as follows:
        limit = LimitTuple(max_inflows=Money(100))
        subgroup = TransactionNode(subgroup, limit=limit)
        priority = [subgroup, account2]
        strategy = TransactionStrategy(priority)
        transactions = strategy(available)
        # The result, assuming available represents net inflows, is that
        # up to $100 will be contributed equally to `account1` and
        # `account2`, with any excess going to `account2`

    Attributes:
        priority [list[Any], dict[Any, Decimal]]: The (nested)
            collection of Accounts.
        transaction_methods (LimitTuple[Callable]): A tuple of methods,
            each taking one argument and returning a transactions object
            (i.e. a `dict[Decimal, Money]` map of timings to values).
            Each method of the tuple respects a different limit (e.g.
            `min_inflows`, `max_outflows`).
        group_methods (LimitTuple[Callable]): A tuple of methods,
            each taking one argument and returning a group of linked
            accounts (i.e. a `set[Account]` or, more generally, `set[T]`
            where `T` is any valid type for a leaf node in `priority`).
            Each method of the tuple corresponds to a different link
            (e.g. `max_inflow_link`, `min_outflow_link`).

    Args:
        available (dict[Decimal, Money]): A time series of inflows
            and outflows, where keys are timings and values are
            inflows (positive) or outflows (negative).
        total (Money): The total amount of inflows/outflows to be
            allocated between the accounts represented in the
            `priority` tree. Optional. If not provided, the sum
            total of `available` will be allocated.
        assign_min_first (Bool): If True, minimum inflows/outflows
            will be assigned first (in `priority` order, so if
            `total` is less than the sum of minimum inflows/outflows
            then low-priority will not have transactions assigned).
            Remaining money is then allocated in `priority` order,
            up to any limits on maximum inflows/outflows.

            If False, minimum inflows/outflows will not be assigned
            and the strategy will move directly to assigning up to
            the maximum inflows/outflows.

            Optional. Defaults to True.

    Returns:
        dict[Account, dict[Decimal, Money]]: A mapping of accounts to
            transactions to (positive) or from (negative) those
            accounts. No `list`, `dict`, or other sub-collection is
            used as a key. Only the leaf node `Account`-like objects of
            the tree defined by `priority` are used as keys.
    """
    def __init__(
            self, priority, transaction_methods=None, group_methods=None):
        """ Initializes TransactionNode """
        # Set up data-holding attributes:
        self._priority = None
        self._priority_tree = None
        # Set up method-holding attributes:
        if transaction_methods is None:
            self.transaction_methods = transaction_default_methods()
        else:
            self.transaction_methods = LimitTuple(transaction_methods)
        if group_methods is None:
            self.group_methods = group_default_methods()
        else:
            self.group_methods = LimitTuple(group_methods)
        # Use property setter to fill the data-holding attributes:
        self.priority = priority

    @property
    def priority(self):
        """ A priority tree defining how to add transactions to accounts """
        return self._priority

    @priority.setter
    def priority(self, val):
        """ Sets priority """
        if val == self._priority:
            # Take no action if `priority` is unchanged.
            return
        # Otherwise, rebuild the annotated priority tree:
        self._priority_tree = TransactionNode(val)
        self._priority = val

    def __call__(self, available, total=None, assign_min_first=True):
        """ Determines transactions to accounts based on `available`. """
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
            min_limit = LIMIT_TUPLE_FIELDS.min_inflow
            max_limit = LIMIT_TUPLE_FIELDS.max_inflow
            min_total = total  # Do limit min. inflows.
        elif total < 0:  # outflows
            min_limit = LIMIT_TUPLE_FIELDS.min_outflow
            max_limit = LIMIT_TUPLE_FIELDS.max_outflow
            min_total = Money('-Infinity')  # Don't limit min. outflows.
        else:  # No transactions since total == 0
            return {}
        # Unless the user tells us not to assign minimums, we will
        # traverse the tree twice. To ensure that we respect per-node
        # limits, we will record all transactions in the first traveral
        # (where minimums are assigned) to a memo, which will be passed
        # to the second traversal (where maximums are assigned):
        memo = {}
        # It's also convenient to modify `available` during traversal,
        # so copy it here to avoid modifying the calling code's vars.
        available = copy(available)
        # First traverse to allocate mins (in priority order)
        if assign_min_first:
            # NOTE: min_total is infinite for outflows, so min outflows
            # will not be limited to the shortfall in `available`.
            min_transactions = self._traverse_tree(
                available, min_total, transactions, min_limit, memo=memo)
            # Other arguments are mutated, but not total, so update here
            total -= sum(min_transactions.values())
        # Then traverse again to allocate remaining money:
        self._traverse_tree(
            available, total, transactions, max_limit, memo=memo)
        return transactions

    def _traverse_tree(self, available, total, transactions, limit, memo=None):
        """ TODO """
        # Set up vars for the while loop:
        return_transactions = {}
        skip_nodes = set()
        threshold = self.transaction_threshold(
            self._priority_tree, total, limit,
            timing=available, transactions=transactions, skip_nodes=skip_nodes)
        # We'll be allocated `threshold` dollars, which isn't based on
        # `total`, so ensure that it isn't larger:
        if abs(threshold) > abs(total):
            threshold = total
        while abs(threshold) > EPSILON_MONEY:
            # Instead of one tree traversal for the whole total,
            # traverse the tree (up to) once for each set of linked
            # accounts. Each traversal will "close out" at least one of
            # those sets of accounts.
            loop_transactions = self._process_node(
                self._priority_tree, available, threshold, transactions,
                limit, memo=memo, skip_nodes=skip_nodes)
            # If we failed to add any new transactions, terminate loop:
            loop_total = sum(loop_transactions.values())
            if loop_total == 0:
                return return_transactions

            # Recordkeeping time!
            # Merge the new transactions with the tally of transactions
            # for all children of this node:
            add_transactions(return_transactions, loop_transactions)
            # Reduce `total` by the amount allocated:
            total -= loop_total
            # Figure out how much to allocate on the next iteration,
            # using the same logic as above:
            threshold = self.transaction_threshold(
                self._priority_tree, total, limit,
                timing=available, transactions=transactions,
                skip_nodes=skip_nodes)
            if abs(threshold) > abs(total):
                threshold = total
        return return_transactions

    def _process_node(
            self, node, available, total, transactions,
            limit_key, memo=None, skip_nodes=None, **kwargs):
        """ Top-level method for processing nodes of all types.

        Args:
            node (TransactionNode): The node to be processed.
            available (dict[Decimal, Money]): A mapping of timings to
                transaction values. See top-level documentation for
                `TransactionNode` for more information.
            total (Money): The total amount to be allocated to leaves
                under this node.
            transactions (dict[Account, dict[Decimal, Money]]): A
                mapping of accounts to transactions already assigned
                during the traversal, where transactions use the same
                style of timing-value mapping as `available`.

                Only leaf-node `Account` objects of the `priority` tree
                are used as keys here (i.e. no `TransactionNode`s).

                *This argument is mutated when this method is called.*
            limit_key (str): The name of a `LimitTuple` field. Used to
                fetch the appropriate value from `transaction_methods`
                and `group_methods`.
            memo (dict[TransactionNode, dict[Decimal, Money]]): A
                mapping of nodes to transactions already assigned during
                the traversal, where transactions use the same style of
                timing-value mapping as `available`.

                Optional. If passed, this will be mutated. The result
                can be used in subsequent traversals, in which case
                the transactions of prior traversals will be treated
                as if they were assigned by this traversal.
            skip_nodes (set[TransactionNode]): Nodes of the tree which
                are we know cannot receive any further transactions.

                Optional. If not passed, all nodes will be examined
                for potential ability to receive transactions, which
                can impact performance.

        Returns:
            dict[Decimal, Money]: A transactions object which combines
                all transactions to child nodes into one time series of
                inflows and outflows.
        """
        if memo is None:
            memo = {}
        if skip_nodes is None:
            skip_nodes = set()
        if node in skip_nodes:
            # Don't process the node at all if we've previously decided
            # to skip it:
            return {}

        # Different kinds of nodes are processed differently, so grab
        # the appropriate method (to be invoked later):
        if node.is_ordered():
            method = self._process_node_ordered
        elif node.is_weighted():
            method = self._process_node_weighted
        else:
            # Anything not recognized above will be treated as a leaf
            # node, i.e. an account. Such nodes should provide a method
            # with a name provided by `transaction_methods`!
            method = self._process_node_leaf

        # If this node has a per-node limit that applies to this
        # traveral (as determined by `limit_key`), apply it:
        limit, total = self._limit_total(node, total, limit_key, memo=memo)

        # Process the node:
        node_transactions = method(
            node, available, total, transactions, limit_key,
            memo=memo, skip_nodes=skip_nodes, **kwargs)

        # Record the result of this traversal in `memo`.
        if node in memo:
            add_transactions(memo[node], node_transactions)
        else:
            memo[node] = node_transactions

        # If we weren't able to add the full amount of `total` to this
        # node, or if we've reached the per-node limit, then the node is
        # exhausted and can be skipped in the future:
        transactions_total = sum(node_transactions.values())
        limit_reached = (
            limit is not None and
            abs(transactions_total) >= abs(limit) - EPSILON_MONEY)
        total_undershot = (
            abs(transactions_total) < abs(total) - EPSILON_MONEY)
        if limit_reached or total_undershot:
            skip_nodes.add(node)

        return node_transactions

    def _limit_total(
            self, node, total, limit_key, memo=None):
        """ Limits inflows/outflows to the node based on its metadata.

        Args:
            node (TransactionNode): The node being traversed.
            total (Money): The amount to be allocated to `node`,
                subject to any applicable limits.
            limit_key (str): A field name of `LimitTuple` specifying
                which limit to apply (e.g. `min_inflow`, `max_outflow`)
            memo (dict[TransactionNode, dict[Decimal, Money]]): A record
                of all transactions assigned to nodes in this traversal.
                See `_process_node` for more information.

        Returns:
            (Money, Money): A `(limit, total)` tuple where `limit` is
            the applicable limit on `node` (`None` if there is no such
            limit) and `total` is the maximum amount that may be
            allocated to `node` (i.e. the lesser of the input `total`
            and `limit`, if it exists.)
        """
        # Get the custom limit for this node, if any:
        limit = getattr(node.limits, limit_key)

        # If there's no applicable limit, don't modify `total`:
        if limit is None:
            return (None, total)

        # Reduce `limit` by the sum of all transactions recorded against
        # this node during previous traversals:
        if memo is not None and node in memo:
            limit -= sum(memo[node].values())

        # Ensure that `total` is no larger than `limit`
        # (but only if they have the same sign):
        if total >= 0 and limit >= 0:
            total = min(total, limit)
        elif total <= 0 and limit <= 0:
            total = max(total, limit)

        return (limit, total)

    def _process_node_ordered(
            self, node, available, total, transactions,
            limit_key, **kwargs):
        """ Processes nodes with ordered children. """
        node_transactions = {}
        # Iterate over in order:
        for child in node.children:
            # Recurse onto each element to obtain the total transactions
            # to be added to it.
            child_transactions = self._process_node(
                child, available, total, transactions,
                limit_key, **kwargs)
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

    def _process_node_weighted(
            self, node, available, total, transactions, limit_key,
            skip_nodes=None, **kwargs):
        """ Processes nodes with unordered, weighted children. """
        if skip_nodes is None:
            skip_nodes = set()
        # Set up local variables:
        node_transactions = {}
        # Reweight children to remove skipped nodes and account for
        # pre-existing transactions for that node from prior traversals:
        weights = self._reweight_children(
            node, total, skip_nodes=skip_nodes, **kwargs)

        # Iterate over each element in arbitrary order:
        for child, weight in weights.items():
            # Recurse onto each child, dividing up `total` according to
            # each child's (already-normalized) weight:
            child_transactions = self._process_node(
                child, available, total * weight, transactions, limit_key,
                skip_nodes=skip_nodes, **kwargs)
            # Pool this child's transactions with the node's:
            add_transactions(node_transactions, child_transactions)

        # `available` and `transactions` were updated by `_process_node`
        # but we need to update `total` manually:
        total -= sum(node_transactions.values())

        # If there's more money available and one or more children still
        # might have room, recurse. (`skip_nodes` is updated
        # automatically during the previous iteration, so this method
        # will recurse onto a reduced set of child nodes):
        if (
                abs(total) > EPSILON_MONEY and
                any(child not in skip_nodes for child in node.children)):
            # Note that we recurse directly on `_process_node_weighted`
            # and not to the generic `_process_node` so as to avoid
            # memoizing this node twice.
            recurse_transactions = self._process_node_weighted(
                node, available, total, transactions, limit_key,
                skip_nodes=skip_nodes, **kwargs)

            # Remember to add the recurse results to the return value!
            add_transactions(node_transactions, recurse_transactions)

        return node_transactions

    def _process_node_leaf(
            self, node, available, total, transactions, limit_key,
            memo=None, **kwargs):
        """ Processes leaf nodes. """
        # pylint: disable=unused-argument
        # We provide the kwargs argument to enforce consistency between
        # _process_* methods.

        # Extract the account itself from the node, since we want to
        # return {account: transaction} pairs, not
        # {TransactionNode: transaction} pairs. (The TransactionNodes
        # of the priority tree should not be exposed to client code
        # in the results of tree traversal.)
        account = node.source

        # We need to get two methods. The first method takes one
        # argument (account) and returns a bound method that's
        # associated with `limit_key` (e.g. `max_inflows(...)`).
        binding_method = getattr(self.transaction_methods, limit_key)
        # Use the binding method to get the appropriate bound method:
        bound_method = binding_method(account)
        # Get the transactions for the account with the bound method:
        if account in transactions:
            prior_transactions = transactions[account]
        else:
            prior_transactions = None
        # Use the bound method to get the schedule for transactions for
        # this account that respects the current limit:
        account_transactions = bound_method(
            available, total, transactions=prior_transactions,
            group_transactions=transactions)

        # Add these new transactions to `available` and `transactions`:
        # Money added to the account is _removed_ from `available`:
        subtract_transactions(available, account_transactions)
        # Whereas it is added to the account's entry in `transactions`:
        # (It is a defaultdict, so there's no need to check keys)
        add_transactions(transactions[account], account_transactions)

        return account_transactions

    def _underweighted_children(
            self, node, memo=None, skip_nodes=None, **kwargs):
        """ TODO """
        if memo is None:
            memo = {}
        if skip_nodes is None:
            skip_nodes = set()

        # Determine the effective weights of each child based on
        # pre-existing transactions:
        # First determine the total transactions for each child:
        transactions = collections.defaultdict(Money)
        transactions.update(
            (child, sum(memo[child].values()))
            for child in node.children if child in memo)
        # Then the total transactions across all children:
        total_transactions = sum(transactions.values())
        # We can end early if there are no transactions:
        if total_transactions == 0:
            return {}
        # Then determine the effective weighting of each child:
        weights = {
            child: transactions[child] / total_transactions
            for child in node.children}
        # Return a mapping of children to the amounts of money necessary
        # to transaction to return them to balance, assuming that the
        # most-overweight node cannot receive any transactions:
        ratio = {
            child: weights[child] / node.children[child]
            for child in node.children}
        # Find the element with the largest ratio; this is the benchmark
        # against which we'll determine how much each other node needs:
        sorted_children = sorted(ratio, key=ratio.get)
        max_child = sorted_children[-1]
        # If the maximal node has the right ratio (i.e. 1), it's
        # impossible for any other node to have an incorrect ratio.
        # In that case, we can terminate early:
        if abs(ratio[max_child] - 1) < EPSILON:
            return {}

        # OPTION 1: Ordered list of transactions:
        rebalance = []
        cumulative_weight = Decimal(0)
        for index in len(sorted_children) - 1:
            # Convenience references:
            child = sorted_children[index]
            next_child = sorted_children[index + 1]
            # Rather than recalculate the sum of weights of all children
            # we've seen so far, simply update it each iteration here:
            cumulative_weight += node.children[child]
            # Only consider children that are more out-of-balance than
            # the next child (i.e. if there are several children in a
            # row with the same level of imbalance, wait until we get
            # to the last of them so we handle them all together)
            if abs(ratio[child] - ratio[next_child]) > EPSILON:
                # Figure out how much we'd need to add to this child
                # and all previous children (which, if previous
                # iterations of transactions have been added, are
                # exactly as imbalanced as this child) to make it no
                # more imbalanced than the next child:

                # Suppose we have 4 nodes with weights w1-w4 and ratios
                # r1-r4. We're on node 2; all previous nodes have ratio
                # r2. We want to bring them up to ratio r3 (the next
                # ratio in the sorted order). Note that adding
                # transactions to nodes 1-2 shifts the ratio of nodes
                # 3-4. The value of transactions to add is given by
                # x = t(r3-r2)(w1+w2), where w1+w2 is the sum of all
                # weights up to and including the current child's.
                # shifts ratio r3.
                # For the initial state of transactions (t):
                # t1 = r2*w1*t, t2 = r2*w2*t, t3 = r3*w3*t, t4 = r4*w4*t
                # t1 + t2 + t3 + t4 = t
                # t + (w1/(w1+w2))*x + (w2/(w1+w2))*x = t + x
                # r3' = (t3/(t+x))/w3
                # r3' = r2' = ((t2 + w2/(w1+w2)*x) / (t + x)) / w2
                # => t3/w3 = t2/w2 + x/(w1+w2)
                # => x = (t3/w3 - t2/w2) * (w1+w2)
                # => x = t*(r3-r2)*(w1+w2)

                # We want to contribute to this node and all previous
                # nodes, so generate a slice of them here:
                process_children = sorted_children[:index + 1]
                # Find total amount we need to add to `process_children`
                # to bring them up to `next_child`'s level of imbalance:
                increment = total_transactions * (
                    (ratio[next_child] - ratio[child]) * cumulative_weight)
                # Find the weighting with which we'll add `increment`.
                # (We could instead simply record the slice and leave it
                # to calling code to assign weights, but this is more
                # convenient):
                weights = {
                    child: node.children[child] / cumulative_weight
                    for child in process_children}
                # Store the results as a (Money, dict) tuple:
                rebalance.append((increment, weights))
        return rebalance

        # OPTION 2: Total amounts needed to rebalance each child
        # (but no order of children based on which is most imbalanced):

        # Otherwise, the ratios are off for some other nodes.
        # Figure out the total value of transactions we'd need to reach
        # to fully rebalance the children (including pre-existing
        # transactions) and then determine how much needs to be added
        # to each child to reach that:
        target_transactions = (
            transactions[max_child] / node.children[max_child])
        rebalance = {}
        for child in node.children:
            # Ignore nodes that are just as out-of-sync as max_child:
            if abs(ratio[child] - ratio[max_child]) > EPSILON:
                # Each node needs its share of target_transactions (scaled
                # by its weight), less pre-existing transactions:
                rebalance[child] = (
                    node.children[child] * target_transactions
                    - total_transactions[child])
        # And we're done!
        return rebalance

    def _reweight_children(
            self, node, total, memo=None, skip_nodes=None, **kwargs):
        """ Processes nodes with unordered, weighted children. """
        if memo is None:
            memo = {}
        if skip_nodes is None:
            skip_nodes = set()
        # Find the total weight of all nodes that we're contributing to
        # (i.e. those not in skip_nodes) so we can normalize correctly:
        total_weight = sum(
            node.children[child] for child in node.children
            if child not in skip_nodes)
        # We can't assign any transactions if there are no weighted
        # children still active:
        if total_weight == 0 or total == 0:
            return {}
        # If we're transacting infinite money, ignore prior transactions
        # and simply restrict to active children:
        if abs(total) == Money("Infinity"):
            active_children = {
                child for child in node.children if child not in skip_nodes}
            total_weight = sum(
                node.children[child] for child in active_children)
            return {
                child: node.children[child] / total_weight
                for child in active_children}
        # Now we know that we're dealing with a non-zero, finite
        # transaction amount, so we can safely do division later.

        # Track the value of transactions previously allocated to
        # children of this node to ensure that their weights are
        # respected. (E.g. if a prior traversal allocated mins. to some
        # children but not others then their weightings might be off;
        # this method should fill in underweighted nodes first.)
        if any(child in memo for child in node.children):
            prior_transactions_total = sum(
                sum(memo[child].values()) for child in node.children
                if child in memo)
        else:
            prior_transactions_total = Money(0)
        # Don't allow prior_transactions_total to have different sign
        # than total (otherwise we might wind up assigning inflows
        # when traversing for outflows or vice-versa):
        if (
                prior_transactions_total < 0 < total
                or total < 0 < prior_transactions_total):
            prior_transactions_total = Money(0)

        # Generate weights for each child which are (a) normalized
        # and (b) result in all active children receiving total
        # transactions (inclusive of prior transactions!) in line with
        # their weights if `total` is contributed:
        weights = {}
        for child, weight in node.children.items():
            if child in skip_nodes:
                continue
            if child in memo:
                prior_transactions_child = sum(memo[child].values())
            else:
                prior_transactions_child = Money(0)
            # Recurse onto each element to obtain the total transactions
            # to be added to it, but reduce `total` according to the
            # normalized weight of each element.
            child_total = (
                (total + prior_transactions_total) * (weight / total_weight)
                - prior_transactions_child)
            # Ensure child_total has the same sign as total (reweighting
            # can cause some children to require negative
            # inflows/outflows to reach balance - which we won't do!)
            if child_total < 0 < total or total < 0 < child_total:
                child_total = Money(0)
            weights[child] = child_total / total

        # Normalize again, in case certain weights were set to 0 above:
        total_weight = sum(weights.values())
        return {
            child: weight / total_weight for child, weight in weights.items()}

    def weights_by_group(
            self, node, total, limit_key,
            timing=None, transactions=None, memo=None, skip_nodes=None):
        """ Determines share of in/outflows allocated to each group.

        This method operates on a _marginal_ (or infinitesimal) basis.
        Assuming the total in/outflow is not large enough to change
        any nodes' behaviour (e.g. to fill up an account/group), this
        method _exactly_ predicts the proportion contributed to each
        account/group.

        Args:
            limit_key (str): A name of a `LimitTuple` field
                corresponding to the type of limit this method should
                aim to respect.

        Returns:
            (dict[frozenset[Account], Money]): A mapping of transaction
            groups to weights. The weights are normalized (i.e. they
            sum to 1), so that each weight indicates the proportion
            of the total allocation that will be allocated to the group
            based on the current behaviour of accounts.
        """
        # Parse input args:
        if skip_nodes is None:
            skip_nodes = set()

        # If this node is being excluded from traversals, then it has
        # no groups to assign weights to.
        if node in skip_nodes:
            return {}

        if node.is_ordered():
            # Ordered nodes only contribute to the first node, so assign
            # the first non-full node a weight of 100%
            weights = tuple()
            for child in node.children:
                weights = self.weights_by_group(
                    child, total, limit_key,
                    timing=timing, transactions=transactions, memo=memo)
                # Stop at the first child that returns non-empty weights
                if weights:
                    break
            # No further processing; an ordered node's behaviour is
            # precisely that of its first (non-done) child.
            return weights

        elif node.is_weighted():
            # Weighted nodes are more complicated. Get the weights of
            # each child's groups, scale them down by the weight
            # associated with the child itnode, and merge the weights of
            # any groups represented by multiple children (by adding):
            weights = {}
            node_weights = self._reweight_children(
                node, total, memo=memo, skip_nodes=skip_nodes)
            for child in node.children:
                if child not in node_weights:
                    continue
                # Get the weights associated with the child's groups:
                child_weights = self.weights_by_group(
                    child, total * node_weights[child], limit_key,
                    timing=timing, transactions=transactions, memo=memo)
                # Add those weights to the parent node's group-weights,
                # after reweighting:
                for group, weight in child_weights.items():
                    # Scale down the added weights by the parent nodes'
                    # weight on the child:
                    weight *= node_weights[child]
                    if group in weights:
                        # Add weights for groups also found in other
                        # children:
                        weights[group] += weight
                    else:
                        # If this is the first instance of seeing this
                        # group, simply include it in the output:
                        weights[group] = weight
            return weights

        else:
            return self.weights_by_group_leaf(
                node, total, limit_key,
                timing=timing, transactions=transactions, memo=memo,
                skip_nodes=skip_nodes)

    def transaction_threshold(
            self, node, total, limit_key,
            timing=None, transactions=None, skip_nodes=None):
        """ TODO

        This method finds the largest amount that is guaranteed to be
        allocatable by this node without exceeding any transaction
        limits (of itnode and/or its children).

        Args:
            limit_key (str): A name of a `LimitTuple` field
                corresponding to the type of limit this method should
                aim to respect.

        Returns:
            (Money, set[set[Account]]): TODO
        """
        if skip_nodes is None:
            skip_nodes = set()
        memo = {}
        # TODO: Sort out how to deal with per-node limits.
        weights = self.weights_by_group(
            node, total, limit_key,
            timing=timing, memo=memo, transactions=transactions,
            skip_nodes=skip_nodes)
        # If `weights` is empty, no accounts can be allocated to,
        # so the threshold is $0:
        if not weights:
            return 0
        total_weight = sum(weights.values())
        # `memo[group]` stores the largest amount that can be allocated
        # to `group`. We hit the threshold for `group` when the total
        # amount being allocated exceeds that amount by a factor of
        # `weights[group]` (normalized - so divide it by `total_weight`)
        thresholds = {
            group: memo[group] / (weights[group] / total_weight)
            for group in weights}
        # Find the smallest (magnitude) value:
        threshold_abs = min(
            abs(threshold) for threshold in thresholds.values())
        # If we flipped the sign in the previous step, flip it back:
        if threshold_abs in thresholds.values():
            return threshold_abs
        else:
            return -threshold_abs

    def weights_by_group_leaf(
            self, node, total, limit_key,
            timing=None, transactions=None, memo=None, skip_nodes=None):
        """ Returns weights for groups associated with a leaf node.

        TODO
        """
        account = node.source
        group_method = getattr(self.group_methods, limit_key)
        group = group_method(account)
        if group is None:
            group = {account}
        # cast to a hashable type:
        group = frozenset(group)

        # Shortcut for when we already know whether this group is done:
        if memo is not None and group in memo:
            # No weights to return if the account won't receive anything
            if memo[group] == 0:
                return {}
            # Otherwise, weight this account's group 100%:
            else:
                return {group: 1}

        # Grab the method for identifying the account's transaction method:
        transaction_method = getattr(self.transaction_methods, limit_key)
        # Get the method for allocating transactions:
        method = transaction_method(account)

        # Allocate the transactions.
        # Pass in transactions already allocated to this account and
        # transactions allocated against others in its group so that the
        # method can reduce its allocation accordingly:
        if account in transactions:
            account_transactions = transactions[account]
        else:
            account_transactions = None
        transactions = method(
            timing=timing,
            transactions=account_transactions,
            group_transactions=transactions)
        # Sum up the total of the transactions:
        transactions_total = sum(transactions.values())

        # Record the result in memo, if provided:
        if memo is not None:
            memo[group] = total
        # Return no weights if there's no room for allocation, or
        # the group weighted 100% if there is room:
        if abs(transactions_total) < EPSILON_MONEY:
            # While we're here, if we've tried to add money but weren't
            # able to (i.e. if `total` is non-zero), add this node to
            # skip_nodes:
            if abs(total) < EPSILON_MONEY and skip_nodes is not None:
                skip_nodes.add(node)
            return {}
        else:
            return {group: 1}

def _groups_from_source(node):
    """ Determines groups of linked accounts for a node. """
    # Ordered and weighted nodes need to be handled differently:
    if node.is_parent_node():
        return _groups_from_source_parent(node)
    elif node.is_leaf_node():
        return _groups_from_source_leaf(node)
    else:
        raise TypeError(
            str(type(node.source)) + " is not a supported type.")

def _groups_from_source_parent(node):
    """ Determines groups of linked accounts under a parent node. """
    groups = []
    # Iterate over each field of LimitTuple in order (this makes
    # building a new LimitTuple of results easier):
    for field_name in LIMIT_TUPLE_FIELDS:
        group = set()
        # For the selected limit type (e.g. `max_inflow`), collect
        # all of the groups present in the children:
        for child in node.children:
            # Get each child's groups for this limit.
            # If any are repeated between children, they'll only be
            # added once (since sets guarantee uniqueness)
            inner_group = getattr(child.groups, field_name)
            if inner_group is not None:
                # `group` needs hashable members, so use frozenset:
                group.add(frozenset(inner_group))
        groups.append(group)
    return LimitTuple(*groups)

def _groups_from_source_leaf(node):
    """ Determines groups of linked accounts for a leaf node. """
    groups = []
    account = node.source
    # We want to build a LimitTuple (so that each kind of limit has
    # its own groups). Rather than hard-code field names, iterate
    # over each field of LimitTuple in order:
    for field_name in LIMIT_TUPLE_FIELDS:
        # Get the group method for this min/max in/outflow limit:
        method = getattr(node.group_methods, field_name)
        # Use the method to get the appropriate group:
        if method is not None:
            group = method(account)
        else:
            # The above branch can set `group=None`, so declare `group`
            # here and set to None to make the next test easier.
            group = None
        # If we don't have a group, treat this as a group of one.
        if group is None:
            group = set(account)
        groups.append(group)
    return LimitTuple(*groups)

""" Provides a class for determining schedules of transactions.

These transaction schedules determine when transactions occur, in what
amounts, and to which accounts.
"""

import networkx
from forecaster.ledger import Money
from forecaster.utility import (
    add_transactions, subtract_transactions, EPSILON_MONEY, EPSILON)
from forecaster.accounts.util import LIMIT_TUPLE_FIELDS
from forecaster.strategy.transaction.util import (
    LimitTuple, transaction_default_methods, group_default_methods)
from forecaster.strategy.transaction.node import TransactionNode


class GraphEdge:
    """ TODO """
    def __init__(self, capacity, weight):
        """ TODO """
        self.capacity = capacity
        self.weight = weight


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

    def __call__(
            self, available, total=None, assign_min=True, **kwargs):
        """ Determines transactions to accounts based on `available`. """
        # pylint: disable=unused-argument
        # We provide a kwargs argument so that this class can be used
        # wherever `TransactionStrategy` or similar classes are used.

        # By default, use up all money in `available`, unless we're
        # specifically told to use less:
        if total is None:
            total = sum(available.values())

        # Determine which limits we need to respect during traversal.
        if total > EPSILON_MONEY:  # inflows
            min_limit = LIMIT_TUPLE_FIELDS.min_inflow
            max_limit = LIMIT_TUPLE_FIELDS.max_inflow
            # Limit min. inflows to what's available:
            min_total = total
        elif total < -EPSILON_MONEY:  # outflows
            min_limit = LIMIT_TUPLE_FIELDS.min_outflow
            max_limit = LIMIT_TUPLE_FIELDS.max_outflow
            # Limit min. outflows based on what's in the account, not
            # the shortfall we're trying to fill:
            min_total = Money('-Infinity')
        else:  # No transactions since total ~= 0
            return {}

        # Build and traverse a graph based on `priority`:
        if assign_min:
            return self._traverse_priority(
                available, total, max_limit, min_limit=min_limit)
        else:
            return self._traverse_priority(
                available, total, max_limit)

    def _traverse_priority(
            self, available, total, max_limit, graph=None, min_limit=None):
        """ TODO """
        if graph is None:
            # Build a graph that can accept up to `total` flow at the
            # source and then find the maxium flow that can actually get
            # through to the sink:
            graph, source, sink = self._build_graph(
                available, total,
                max_limit=max_limit, min_limit=min_limit)

        flows = self._generate_flows(graph, source, sink)
        transactions = self._convert_flows_to_transactions(
            flows, available, max_limit)
        # NOTE: Can likely get this directly from the graph (e.g. via
        # flow_value parameter of maximum_flow):
        total_transactions = sum(
            sum(transactions[account].values()) for account in transactions)
        # If we couldn't assign any transactions, there's no need to
        # recurse; quit now:
        if abs(total_transactions) < EPSILON:
            return transactions

        # If we couldn't assign all of `total`, reduce the graph (take
        # out at least one edge) and recurse.
        shortfall = total - total_transactions
        if abs(shortfall) > EPSILON:
            graph = self._reduce_graph(graph, flows)
            loop_transactions = self._traverse_priority(
                available, shortfall, max_limit,
                graph=graph, min_limit=min_limit)

            # Merge loop_transactions with total_transactions:
            for account in loop_transactions:
                if account in transactions:
                    add_transactions(
                        transactions[account], loop_transactions[account])
                else:
                    transactions[account] = loop_transactions[account]

        return transactions

    def _build_graph(self, available, total, max_limit, min_limit=None):
        """ TODO """
        # Create an empty graph:
        graph = networkx.DiGraph()
        # Use the root node of the tree as the graph's source node:
        source = self._priority_tree
        # The sink node is a unique dummy object, but its presence is
        # important. Edges inbound to this node (from Account objects)
        # will have carefully-set capacities.
        sink = frozenset()  # must be hashable

        # Recursively build out the group from the root down:
        self._add_node(
            graph, source, available, total, max_limit,
            min_limit=min_limit, sink=sink)

        return (graph, source, sink)

    def _add_node(
            self, graph, node, available, total, max_limit,
            min_limit=None, sink=None):
        """ TODO """
        if node.is_weighted():
            method = self._add_node_weighted
        elif node.is_ordered():
            method = self._add_node_ordered
        elif node.is_leaf():
            method = self._add_node_leaf
        else:
            # Treat all other nodes as accounts:
            method = self._add_node_account

        method(
            graph, node, available, total, max_limit,
            min_limit=min_limit, sink=sink)

    def _add_node_weighted(
            self, graph, node, available, total, max_limit,
            min_limit=None, sink=None):
        """ TODO """
        # Add an edge to each child node (the nodes themselves are added
        # automatically) with 0 weight and capacity of `total` scaled
        # by the child's weight.

        # TODO: Instead of passing total, calculate it from the inbound
        # capacity of all edges to this node. (This allows a node to be
        # found at multiple spots in the tree, causing it to recalculate
        # child weights dynamically).

        # If this node has a limit that's smaller than `total`, use that
        # limit instead of total.
        total = _limit_total(node, total, (max_limit, min_limit))
        # Weighted nodes assign flows proportionately to weights.
        # Proportionality is easier to calculate with normalized weights
        # so determine that first:
        normalization = sum(node.children.values())
        # Add an edge to each child (this automatically adds the
        # children to the graph):
        for child, weight in node.children.items():
            child_total = total * weight / normalization
            graph.add_edge(node, child, capacity=child_total, weight=0)
            # Recurse onto the child:
            self._add_node(
                graph, child, available, child_total, max_limit,
                min_limit=min_limit, sink=sink)

    def _add_node_ordered(
            self, graph, node, available, total, max_limit,
            min_limit=None, sink=None):
        """ TODO """
        pass

    def _add_node_leaf(
            self, graph, node, available, total, max_limit,
            min_limit=None, sink=None):
        """ TODO """
        pass

    def _add_node_account(
            self, graph, node, available, total, max_limit,
            min_limit=None, sink=None):
        """ TODO """
        pass

    def _reduce_graph(self, graph, flows):
        """ TODO """
        pass

    def _generate_flows(self, graph, source, sink):
        """ TODO """
        pass

    def _convert_flows_to_transactions(self, flows, available, limit):
        """ TODO """
        pass

def _limit_total(node, total, limits):
    """ TODO """
    # Halt recursion:
    # (Do this here instead of at the end to allow tail recursion)
    if not limits:
        return total

    # Pick the next limit in the sequence and apply it (if not None):
    limit = limits[0]
    if limit is not None:
        limit_value = getattr(node.limits, limit)
        if limit_value is not None and abs(node_limit) < abs(total):
            total = limit_value
    # Recurse onto the remaining limits:
    return _limit_total(node, total, limits[1:])

""" Provides a class for determining schedules of transactions.

These transaction schedules determine when transactions occur, in what
amounts, and to which accounts.
"""

from decimal import Decimal
import networkx
from forecaster.ledger import Money
from forecaster.utility import EPSILON_MONEY
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
        # TODO: Traverse for `min_limit` as well:
        return self._traverse_priority(available, total, max_limit)

    def _traverse_priority(
            self, timing, total, limit, source=None, sink=None):
        """ TODO """
        # Convert Money-typed `total` to Decimal:
        if hasattr(total, "amount"):
            total = total.amount

        # Build a graph that can accept up to `total` flow at the
        # source and then find the maximum flow that can actually
        # get through to the sink:
        graph, source, sink = self._build_graph(
            timing, total, limit, source=source, sink=sink)

        _, flows = self._generate_flows(graph, source, sink)
        accounts = self._get_accounts()
        transactions = self._convert_flows_to_transactions(
            flows, timing, limit, accounts, total=total)

        return transactions

    def _build_graph(
            self, timing, total, limit, *, source=None, sink=None):
        """ TODO """
        # The sink and source nodes are each unique dummy objects.
        # Some algorithms don't require a unique sink (e.g. accounts
        # could each be sinks), but it's actually helpful to set edges
        # from accounts to this sink with capacities equal to the
        # account's maximum flow (since the accounts might have multiple
        # inbound edges which, together, exceed the account's capacity).
        # They can be any hasahble value; we default to 0 and 1.
        if source is None:
            source = 0
        if sink is None:
            sink = 1

        # `total` is used to define capacities of edges between nodes.
        # Edges must have positive capacity, so ensure `total > 0`.
        total = abs(total)

        # Create an empty graph:
        graph = networkx.DiGraph()
        # We could use the root node of the tree as the graph's source
        # node, but it's convenient if each node can determine the
        # capacities of its outbound weights based on the capacities
        # of its inbound weights. So create a dummy source node with
        # an edge to the root with capacity `total`, unless calling
        # code explicitly requests the root node:
        if source is not self._priority_tree:
            graph.add_edge(source, self._priority_tree, capacity=total)

        # Recursively build out the group from the root down:
        self._add_successors(
            graph, self._priority_tree, timing, limit, sink=sink)

        # TODO: Pass over weighted nodes and limit inbound capacity
        # to actual maximum possible flows (see comment at end of
        # `_add_node_weighted`). Probably best to push this off to
        # a new (recursive) method.

        return (graph, source, sink)

    def _add_successors(
            self, graph, node, timing, limit, *, sink=None):
        """ TODO """
        # If `node` has an applicable limit, embed it as two nodes:
        #       N --> L
        # where N is `node` and `L` is a dummy node. The edge between
        # them should have a capacity which is restricted to the limit.
        outbound_node = node
        if hasattr(node, "limits") and hasattr(node.limits, limit):
            limit_value = getattr(node.limits, limit)
            # Convert from Money-like to Decimal, if applicable:
            if hasattr(limit_value, "amount"):
                limit_value = limit_value.amount
            if limit_value is not None:
                # NOTE: We create a hashable object based on `node` and
                # `limit`, the applicable limit key. Consider whether we
                # want to use a const value so that all limit keys map
                # to the same dummy node.
                # (This may make life easier if we want to do different
                # traversals for each limit type. But then consider
                # whether we should be adding limit nodes for _all_
                # nodes, since some may have a limit for some limit
                # types but not for others, leading to different graph
                # topologies for different limit types.)
                outbound_node = (node, limit)
                # If the inbound capacity is less than the limit value,
                # use that, since many successors will use this to
                # determine their own edge capacities:
                capacity = min(_inbound_capacity(graph, node), limit_value)
                graph.add_edge(
                    node, outbound_node, capacity=capacity)

        # Anything that isn't a TransactionNode gets treated as an
        # account:
        if not isinstance(node, TransactionNode):
            method = self._add_node_account
        # TransactionNodes come in a few different flavours:
        elif node.is_weighted():
            method = self._add_node_weighted
        elif node.is_ordered():
            method = self._add_node_ordered
        elif node.is_leaf_node():
            method = self._add_node_leaf
        else:
            raise ValueError("Unrecognized node type for node " + str(node))

        method(
            graph, node, timing, limit,
            sink=sink, outbound_node=outbound_node)

    def _add_node_weighted(
            self, graph, node, timing, limit,
            *, outbound_node=None, **kwargs):
        """ Adds a weighted node's children to the graph.

        The input `node` should already be a node of `graph` with at
        least one inbound edge. This method will add the node's children
        to the graph (if not already present) and add edges from `node`
        to each of its children.

        Each edge to a child has 0 weight and capacity equal to `node`'s
        total inbound capacity, scaled down proportionately to the
        weight that `node` gives the child.

        Args:
            graph (Graph, DiGraph): A graph containing `node`.
            node (TransactionNode): A weighted node with one or more
                children.
            timing (Timing): The timing of transactions to be assigned
                to nodes.
            limit (str): The name of the method used by leaf nodes
                to determine the maximal sequence of transactions for
                given timing. The method must take `timing` as a kwarg.
            sink (str): All leaf nodes will be neighbours of this node.
                Optional; no edges will be created from leaf nodes if
                not provided.
        """
        if outbound_node is None:
            outbound_node = node
        # Calculate the total capacity of inbound edges.
        # This will be distributed to outbound edges.
        capacity = _inbound_capacity(graph, node)

        # For weighted nodes, we want to prioritize assigning flows
        # as dictated by the nodes' weights, while still allowing flows
        # to be shifted between children if some children can't receive
        # the full amount dictated by their weight.
        # We accomplish this by adding weighted edges between children
        # that allow (but penalize) flows between children.
        # (We route all these edges through `overflow_node` so that the
        # number of edges added is `n+1`, where `n` is the number of
        # children. If added directly between children, the number of
        # edges would be `n^2`.)
        overflow_node = (node, "overflow")

        # Weighted nodes assign flows proportionately to weights.
        # Proportionality is easier to calculate with normalized weights
        # so determine that first:
        normalization = sum(node.children.values())
        # Add an edge to each child (this adds both edge and child).
        for child, weight in node.children.items():
            child_total = capacity * weight / normalization
            graph.add_edge(
                outbound_node, child, capacity=child_total)
            # Add edges to and from `overflow_node` to allow shifting
            # flow between children:
            graph.add_edge(
                overflow_node, child, capacity=capacity-child_total)
            # Recurse onto the child:
            self._add_successors(
                graph, child, timing, limit, **kwargs)

        # We want the flow through each child to be as close as possible
        # to the capacity assigned above (i.e. we want to move as little
        # flow as possible between children.)
        # Accomplish this by heavily penalizing flows through
        # `overflow_node`. It should be preferable to shift flow between
        # _any_ successor path before routing it through `overflow_node`
        weight = max(_sum_weight(graph, child) for child in node.children) + 1
        graph.add_edge(node, overflow_node, capacity=capacity, weight=weight)
        # NOTE: This isn't enough, since if the inbound capacity exceeds
        # the maximum flow possible through all of the node's children,
        # then the weight on overflows doesn't affect underflows (which
        # will be distributed unpredictably).
        # We probably need to do a subsequent pass of all weighted nodes
        # to limit inbound and outbound capacity to the actual max flow
        # possible through successors. (We can probably check for flows
        # through `overflow_node` at the same time, reify them as
        # increased/decreased capacity on edges to various children,
        # and set capacity of the edge to `overflow_node` to 0.)
        # This should probably proceed depth-first from `source`, so
        # that the truest weighting of the highest-level nodes' children
        # is reified first, with lower-level nodes being considered
        # later. (Each weighted node will likely require a full
        # min-cost-max-flow iteration over the whole graph to determine
        # its max flows, since its successors may share capacity with
        # non-successors elsewhere in the tree.)
        # One benefit of this is that we can probably reinstate the
        # `_sum_weight` logic of `_add_ordered_node` (and thus assign
        # non-zero capacity to each child of an ordered node) since
        # we'll ensure that the maximum amount of flow is forced through
        # each weighted node on the first "real" traversal.
        # (This doesn't save on algorithmic complexity, sadly - we'll do
        # just as many flow-assigning traversals, but this way we do
        # them during graph-building time, with the benefit that we
        # deal with overflow in a more rigorous way than earlier
        # implementations where we simply assign capacity, try to find
        # the max flow, determine which nodes were the bottleneck,
        # reassign weights by skipping bottlenecked nodes, and reattempt
        # finding the max flow.)

    def _add_node_ordered(
            self, graph, node, timing, limit,
            *, outbound_node=None, **kwargs):
        """ TODO """
        if outbound_node is None:
            outbound_node = node
        # Calculate the total capacity of inbound edges.
        # This will be distributed to outbound edges.
        capacity = _inbound_capacity(graph, node)

        # Add an edge to each child (this adds both edge and child).
        # The first live (i.e. non-skipped) child gets all the capacity.
        weight = 0
        for child in node.children:
            graph.add_edge(
                outbound_node, child, capacity=capacity, weight=weight)
            # Recurse onto the child:
            self._add_successors(
                graph, child, timing, limit, **kwargs)
            # Ensure that assigning flows to the next child in sequence
            # has a penalty larger than any path through the current
            # child's successors:
            weight = max(weight, _sum_weight(graph, child)) + 1

    def _add_node_leaf(
            self, graph, node, timing, limit,
            *, outbound_node=None, **kwargs):
        """ TODO """
        if outbound_node is None:
            outbound_node = node
        # Calculate the total capacity of inbound edges.
        # This will be distributed to outbound edges.
        capacity = _inbound_capacity(graph, node)

        # Add an edge to the (single) child:
        child = node.source
        graph.add_edge(outbound_node, child, capacity=capacity)

        # Recurse onto the child:
        self._add_successors(graph, child, timing, limit, **kwargs)

    def _add_node_account(
            self, graph, node, timing, limit,
            *, sink=None, outbound_node=None, **kwargs):
        """ TODO """
        if outbound_node is None:
            outbound_node = node

        # The capacity of an account is not a function of its inbound
        # edges - it's just the most that an account can receive.
        transaction_limit = self._get_transactions(node, limit, timing)
        # Take `abs` since networkx requires positive-value capacity:
        capacity = abs(sum(transaction_limit.values()))
        # Convert Money-valued `capacity` to Decimal:
        if hasattr(capacity, "amount"):
            capacity = capacity.amount

        # Only assign `capacity` as an edge value if it is finite.
        # (networkx doesn't deal well with Decimal('Infinity'). The
        # "capacity" attr should be absent if capacity is unbounded.)
        # We don't need to handle the "limit" this way, because networkx
        # doesn't use that attr.
        # We don't need to include `weight` either, since when absent
        # edges are assumed to have 0 weight.
        edge_data = {"limit": capacity}
        if capacity < Decimal('Infinity'):
            edge_data["capacity"] = capacity

        # Most accounts add an edge straight to `sink`, but accounts
        # that have shared transaction limits have special treatment:
        group = self._get_group(node, limit)
        if group is not None:
            group_node = frozenset(group)  # make hashable
            # TODO: Assign limit in separate method that's called once
            # for each type of limit (i.e. not called again by
            # `_reduce_graph`)
            graph.add_edge(outbound_node, group_node, **edge_data)
            # We're done with the original outbound node; all further
            # edges will be from the group node.
            outbound_node = group_node

        # Send an edge from the node to the sink, if provided:
        if sink is not None:
            # TODO: Assign limit in separate method that's called once
            # for each type of limit (i.e. not called again by
            # `_reduce_graph`)
            graph.add_edge(outbound_node, sink, **edge_data)

    def _generate_flows(self, graph, source, sink):
        """ TODO """
        # For more on this networkx algoritm, see:
        # https://networkx.github.io/documentation/networkx-1.10/reference/generated/networkx.algorithms.flow.max_flow_min_cost.html#networkx.algorithms.flow.max_flow_min_cost
        # TODO: Use capacity and weight constants (not str literals)
        flows = networkx.algorithms.flow.max_flow_min_cost(
            graph, source, sink, capacity='capacity', weight='weight')
        # Total flow is equal to whatever's flowing out of `source`:
        total = sum(flows[source].values())
        return total, flows

    def _convert_flows_to_transactions(
            self, flows, timing, limit, accounts, total=None):
        """ TODO """
        # If `total` is negative, all flows need to be flipped to
        # negative sign.
        negative_sign = total is not None and total < 0
        # TODO: Reduce this to a dict comprehension after debugging.
        transactions = {}
        for account in accounts:
            if account in flows:
                total_flows = Money(sum(flows[account].values()))
                if negative_sign:
                    total_flows = -total_flows
                transactions[account] = self._get_transactions(
                    account, limit, timing, total=total_flows)
        return transactions

    def _get_accounts(self, node=None, accounts=None):
        """ TODO """
        # Assign defaults:
        if accounts is None:
            accounts = set()
        if node is None:
            node = self._priority_tree

        # If this is a leaf, record its account:
        if node.is_leaf_node():
            accounts.add(node.source)
        # Otherwise, recurse onto children:
        else:
            for child in node.children:
                self._get_accounts(child, accounts)

        return accounts

    def _get_transactions(self, account, limit, timing, total=None):
        """ TODO """
        if limit is None:
            return {}
        # This is ugly, but it works. Someday we should refactor this:
        selector_method = getattr(self.transaction_methods, limit)
        transaction_method = selector_method(account)
        return transaction_method(timing, transaction_limit=total)

    def _get_group(self, account, limit):
        """ TODO """
        group_method = getattr(self.group_methods, limit)
        return group_method(account)

def _inbound_capacity(graph, node):
    """ Calculates the total capacity of inbound edges. """
    # For each node, we'll calculate this amount each time the node is
    # encountered and distribute it between outbound edges.
    # (We do it this way, rather than passing `capacity` in as an arg
    # from the parent node during recursion, because `node` could be
    # found at multiple spots in the tree, so the amount to distribute
    # between outbound edges can change during recursion.)
    return sum(
        graph[parent][node]["capacity"] for parent in graph.predecessors(node))

def _sum_weight(graph, node):
    """ TODO """
    # In principal, we only need to ensure that we return the maximum
    # weight of any path from `node` to `sink`. But that problem is
    # NP-hard, whereas just summing over all descendant edges can be
    # done in linear time. Just be sure that there are no cycles!
    weight = 0
    for child in graph.successors(node):
        # Find weights on this node's children:
        if "weight" in graph[node][child]:
            weight += graph[node][child]["weight"]
        # And also on those children's descendants:
        weight += _sum_weight(graph, child)
    return weight

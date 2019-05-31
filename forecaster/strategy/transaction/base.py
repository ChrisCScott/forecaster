""" Provides a class for determining schedules of transactions.

These transaction schedules determine when transactions occur, in what
amounts, and to which accounts.
"""

from decimal import Decimal
from copy import copy
from queue import SimpleQueue
import networkx
from forecaster.ledger import Money
from forecaster.utility import EPSILON_MONEY, EPSILON
from forecaster.accounts.util import LIMIT_TUPLE_FIELDS
from forecaster.strategy.transaction.util import (
    LimitTuple, transaction_default_methods, group_default_methods)
from forecaster.strategy.transaction.node import TransactionNode

CAPACITY_KEY = "capacity"
WEIGHT_KEY = "weight"
LIMIT_KEY = "limit"


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
            self, timing, total, limit,
            *, source=None, sink=None, precision=EPSILON):
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

        # networkx has unexpected behaviour for non-int edge capacities,
        # so inflate total based on the EPSILON precision constant:
        total = int(total / precision)

        # Create an empty graph:
        graph = networkx.DiGraph()
        # We could use the root node of the tree as the graph's source
        # node, but it's convenient if each node can determine the
        # capacities of its outbound weights based on the capacities
        # of its inbound weights. So create a dummy source node with
        # an edge to the root with capacity `total`, unless calling
        # code explicitly requests the root node:
        if source is not self._priority_tree:
            _add_edge(graph, source, self._priority_tree, capacity=total)

        outbound_nodes = {}

        # Recursively build out the group from the root down:
        self._add_successors(
            graph, self._priority_tree, timing, limit,
            source=source, sink=sink, outbound_nodes=outbound_nodes,
            precision=precision)

        # This first pass results in weighted nodes providing too much
        # outbound capacity to their children. Pass over weighted nodes
        # and limit outbound capacity to actual maximum possible flows.
        self._restrict_weighted_underflows(
            graph, timing, limit, source, sink, outbound_nodes=outbound_nodes)

        return (graph, source, sink)

    def _add_successors(
            self, graph, node, timing, limit,
            capacity=None, children=None, outbound_nodes=None, **kwargs):
        """ TODO """
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
            if children is None:
                # Leaf nodes don't have children, but they do wrap an
                # account which we treat like a child:
                children = node.source
        else:
            raise ValueError("Unrecognized node type for node " + str(node))

        # Assign default value _after_ the above so that leaf nodes have
        # a chance to assign their default first.
        if children is None and isinstance(node, TransactionNode):
            # `children` can remain None for non-TransactionNode input
            children = node.children

        # If this node has a limit, enforce it by adding a dummy
        # `outbound_node` and restricting capacity on the edge from
        # `node` to `outbound_node`:
        outbound_node, capacity = self._embed_limit(
            graph, node, limit, capacity=capacity)

        # Record the outbound node if the calling method wants us to:
        if outbound_nodes is not None:
            outbound_nodes[node] = outbound_node

        method(
            graph, outbound_node, children, timing, limit,
            capacity=capacity, outbound_nodes=outbound_nodes, **kwargs)

    def _embed_limit(self, graph, node, limit, capacity=None):
        """ TODO """
        # If we don't wind up doing any embedding, just return `node`:
        outbound_node = node

        # If `node` has an applicable limit, embed it as two nodes:
        #       N --> L
        # where N is `node` and `L` is a dummy node. The edge between
        # them should have a capacity which is restricted to the limit.
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
                if capacity is None:
                    capacity = _inbound_capacity(graph, node)
                capacity = min(capacity, limit_value)
                _add_edge(graph, node, outbound_node, capacity=capacity)

        return outbound_node, capacity

    def _add_node_weighted(
            self, graph, node, children, timing, limit,
            *, capacity=None, **kwargs):
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
        """
        if capacity is None:
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
        # Add an edge from `node` to `overflow_node` and from
        # `overflow_node` to each child. This enables shifting flow
        # between children. (We'll add weight to the node-overflow_node
        # edge later, once we know the weights of all paths to `sink`):
        _add_edge(graph, node, overflow_node, capacity=capacity)
        for child in children:
            _add_edge(graph, overflow_node, child, capacity=capacity)

        # Recursively add successor nodes:
        self._add_weighted_children(
            graph, node, children, capacity, timing, limit, **kwargs)

        # We want the flow through each child to be as close as possible
        # to the capacity assigned above (i.e. we want to move as little
        # flow as possible between children.)
        # Accomplish this by heavily penalizing flows through
        # `overflow_node`. It should be preferable to shift flow between
        # _any_ successor path before routing it through `overflow_node`
        weight = max(_sum_weight(graph, child) for child in children) + 1
        _add_edge(graph, node, overflow_node, weight=weight)

        # This deals with overflows, but not underflows - which are
        # basically guaranteed, since each child node has more inbound
        # capacity than is needed to achieve its weighted flows (thanks
        # to the extra capacity from overflow_node).
        # We'll need to solve this after the first complete iteration
        # of the graph has been built.

    def _add_weighted_children(
            self, graph, node, children, capacity, timing, limit, **kwargs):
        """ TODO """
        # Weighted nodes assign flows proportionately to weights.
        # Proportionality is easier to calculate with normalized weights
        # so determine that first:
        normalization = sum(children.values())
        # TODO: Implement version of `add_edges_from` to ensure that
        # total capacity across all edges is (approx.) equal to the sum
        # of children's capacities prior to rounding.

        # Add an edge to each child (this adds both edge and child).
        ebunch = []
        for child, weight in children.items():
            child_total = capacity * weight / normalization
            ebunch.append([node, child, {CAPACITY_KEY: child_total}])
        # Add the edges all at once; this method allows us to limit the
        # effect of rounding across multiple edges:
        _add_edges_from(graph, ebunch)
        # Then fill in each child's successors:
        for child in children:
            self._add_successors(
                graph, child, timing, limit, **kwargs)

    def _restrict_weighted_underflows(
            self, graph, timing, limit, source, sink, outbound_nodes=None):
        """ TODO """
        # We want to ensure that higher-order weighted nodes are
        # prioritized (i.e. skew their flows to the most limited degree
        # possible), so we'll use _breadth-first_ traversal.
        # It's best to do that traversal on `_priority_tree`, since the
        # graph itself can have dummy nodes that cause two weighted
        # nodes with equal height in the tree to have unequal distance
        # from `source` in the graph.
        weighted_nodes = SimpleQueue()
        traverse_nodes = SimpleQueue()
        traverse_nodes.put(self._priority_tree)
        while not traverse_nodes.empty():
            # Get the node at the front of the queue:
            node = traverse_nodes.get()
            # Store weighted nodes for later traversal:
            if node.is_weighted():
                weighted_nodes.put(node)
            # Traverse children breadth-first:
            for child in node.children:
                traverse_nodes.put(child)

        # Now we can traverse weighted nodes in breadth-first order.
        while not weighted_nodes.empty():
            node = weighted_nodes.get()
            self._restrict_node_underflows(
                graph, node, timing, limit, source, sink,
                outbound_nodes=outbound_nodes)

    def _restrict_node_underflows(
            self, graph, node, timing, limit, source, sink,
            outbound_nodes=None, exclude_children=None, active_children=None):
        """ TODO """
        # First, restrict based on inbound capacity (once).
        # Second, restrict based on outbound capacity recursively,
        # so that all children with less than their target flow
        # are excluded and other children have their capacities
        # re-calculated based on the remaining flow.
        if active_children is None:
            active_children = copy(node.children)
        if exclude_children is None:
            exclude_children = set()

        # If `node` channels all its flow through some network that
        # terminates with `outbound_node`, replace `node` with
        # `outbound_node` (but save the original node for the final
        # _add_successors call, since it doesn't support receiving
        # an `outbound_node` as input)
        base_node = node
        if outbound_nodes is not None and node in outbound_nodes:
            node = outbound_nodes[node]

        # Try to generate flows through the graph.
        _, flows = self._generate_flows(graph, source, sink)
        total_flows = sum(flows[node].values())

        # For the following recursion on outbound capacity to work,
        # we need to ensure that the total 0-weight capacity to children
        # is the same as total flows through this node. If not,
        # regenerate the 0-weight edges to the node's children based on
        # the actual flows.
        zero_weight_capacity = _outbound_capacity(graph, node, weight=0)
        if abs(total_flows - zero_weight_capacity) > EPSILON:
            # Force recalculation of 0-weight edges' capacity based on
            # the actual sum of flows through this node:
            self._add_successors(
                graph, node, timing, limit,
                source=source, sink=sink, capacity=total_flows)
            # Now recurse onto this method, which should result in
            # this branch not executing.
            self._restrict_node_underflows(
                graph, node, timing, limit, source, sink,
                outbound_nodes=outbound_nodes,
                exclude_children=exclude_children,
                active_children=active_children)
            return

        # Identify which children have received less flow than their
        # 0-weight edges provide capacity for. These are added to
        # `exclude_children`, since they're definitely saturated:
        newly_excluded = set()
        for child in active_children:
            flow = flows[node][child]
            capacity = graph[node][child][CAPACITY_KEY]
            if flow < capacity:
                newly_excluded.add(child)

        # If no new children are excluded, that means that no nodes
        # have underflows, which means they must all have saturated
        # their 0-weight edges - which is what we want, so we're done.
        if not newly_excluded:
            return

        # Otherwise, update `exclude_children` and `active_children`:
        for child in newly_excluded:
            # Add to exclude_children and remove from active_children:
            exclude_children.add(child)
            # Nodes use various container classes to store children.
            # Use the appropriate removal method for active_children:
            if isinstance(active_children, dict):
                del active_children[child]
            elif isinstance(active_children, (set, list)):
                active_children.remove(child)
            else:
                raise TypeError(
                    'node.children is not of recognized type.'
                    + ' Expected dict, set, or list. Got '
                    + str(type(active_children)))

        # Lock in flows to excluded children:
        for child in exclude_children:
            _add_edge(graph, node, child, capacity=flows[node][child])
        # Re-assign capacities of  edges to `active_children` based on
        # the remaining flows:
        excluded_flow = sum(flows[node][child] for child in exclude_children)
        capacity = total_flows - excluded_flow
        self._add_successors(
            graph, node, timing, limit,
            capacity=capacity, outbound_nodes=outbound_nodes,
            children=active_children)
        # Then recurse, since reassignment may have revealed certain
        # active children which reach saturation with greater capacity:
        self._restrict_node_underflows(
            graph, base_node, timing, limit, source, sink,
            outbound_nodes=outbound_nodes,
            exclude_children=exclude_children,
            active_children=active_children)

    def _add_node_ordered(
            self, graph, node, children, timing, limit,
            *, capacity=None, **kwargs):
        """ TODO """
        if capacity is None:
            # Calculate the total capacity of inbound edges.
            # This will be distributed to outbound edges.
            capacity = _inbound_capacity(graph, node)

        # Add an edge to each child (this adds both edge and child).
        # The first live (i.e. non-skipped) child gets all the capacity.
        weight = 0
        for child in children:
            _add_edge(
                graph, node, child, capacity=capacity, weight=weight)
            # Recurse onto the child:
            self._add_successors(
                graph, child, timing, limit, **kwargs)
            # Ensure that assigning flows to the next child in sequence
            # has a penalty larger than any path through the current
            # child's successors:
            weight = max(weight, _sum_weight(graph, child)) + 1

    def _add_node_leaf(
            self, graph, node, child, timing, limit,
            *, capacity=None, **kwargs):
        """ TODO """
        if capacity is None:
            # Calculate the total capacity of inbound edges.
            # This will be distributed to outbound edges.
            capacity = _inbound_capacity(graph, node)

        # Add an edge to the (single) child:
        _add_edge(graph, node, child, capacity=capacity)

        # Recurse onto the child:
        self._add_successors(graph, child, timing, limit, **kwargs)

    def _add_node_account(
            self, graph, node, child, timing, limit,
            *, sink=None, capacity=None, precision=EPSILON, **kwargs):
        """ TODO """
        # pylint: disable=unused-argument
        # `child` isn't used by this method, but it needs to provide the
        # same number sequence of positional args as other `_add_node_*`
        # methods, because `_add_successors` will provide a value (None,
        # in the case of this method).
        if capacity is None:
            # The capacity of an account is not a function of its
            # inbound edges. It's the most that an account can receive.
            transaction_limit = self._get_transactions(node, limit, timing)
            # NOTE: We scale up based on the precision here because
            # _get_transactions returns results in `Money` terms, but
            # we want to use it to generate an edge capacity. All edge
            # capacities are scaled up this way.
            capacity = sum(transaction_limit.values()) / precision

        # Most accounts add an edge straight to `sink`, but accounts
        # that have shared transaction limits have special treatment:
        group = self._get_group(node, limit)
        if group is not None:
            group_node = frozenset(group)  # make hashable
            _add_edge(
                graph, node, group_node,
                capacity=capacity, limit=capacity)
            # We're done with the original account node; all further
            # edges will be from the group node.
            node = group_node

        # Send an edge from the node to the sink, if provided:
        if sink is not None:
            _add_edge(
                graph, node, sink,
                capacity=capacity, limit=capacity)

    def _generate_flows(self, graph, source, sink):
        """ TODO """
        # For more on this networkx algoritm, see:
        # https://networkx.github.io/documentation/networkx-1.10/reference/generated/networkx.algorithms.flow.max_flow_min_cost.html#networkx.algorithms.flow.max_flow_min_cost
        # TODO: Use capacity and weight constants (not str literals)
        flows = networkx.algorithms.flow.max_flow_min_cost(
            graph, source, sink, capacity=CAPACITY_KEY, weight=WEIGHT_KEY)
        # Total flow is equal to whatever's flowing out of `source`:
        total = sum(flows[source].values())
        return total, flows

    def _convert_flows_to_transactions(
            self, flows, timing, limit, accounts,
            total=None, precision=EPSILON):
        """ TODO """
        # If `total` is negative, all flows should be outflows
        # (and thus need to be flipped to negative sign).
        is_outflows = total is not None and total < 0
        # TODO: Reduce this to a dict comprehension after debugging.
        transactions = {}
        for account in accounts:
            if account in flows:
                # NOTE: We scale down the flows to the account by a
                # factor of `precision` because all flows/capacities
                # are automatically inflated to avoid rounding errors.
                total_flows = Money(sum(flows[account].values())) * precision
                if is_outflows:
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
    capacity = sum(
        graph[parent][node][CAPACITY_KEY]
        for parent in graph.predecessors(node))
    # Avoid setting `capacity` to a non-Decimal value:
    if not isinstance(capacity, Decimal):
        capacity = Decimal(capacity)
    return capacity

def _outbound_capacity(graph, node, weight=None):
    """ Calculates the total capacity of outbound edges. """
    capacity = 0
    # Add up the capacities of all outbound edges:
    for child in graph.successors(node):
        # `edge` is a dict with str-valued keys.
        edge = graph[node][child]
        if CAPACITY_KEY in edge:
            if (
                    # If `weight` is not provided, add up all edges:
                    weight is None or
                    # If `weight` is provided, only add edges with that
                    # specific weight (i.e. ignore other edges)
                    (
                        WEIGHT_KEY in edge and
                        edge[WEIGHT_KEY] == weight) or
                    # If an edge lacks a weight attribute, it is treated
                    # as if it has 0 weight. If `weight` is 0, we should
                    # include that edge's capacity:
                    (WEIGHT_KEY not in edge and weight == 0)
            ):
                capacity += graph[node][child][CAPACITY_KEY]
        else:
            # If capacity is not explicitly provided, it's infinite:
            capacity = Decimal('Infinity')
    return capacity

def _nodes_between(graph, start, end_nbunch):
    """ Finds all nodes on a path between `start` and `end_nbunch`.

    `end_nbunch` is expected to be an iterable of nodes.
    """
    # We could find all nodes between `start` and `end_nbunch` by
    # calling `networkx.algorithms.simple_paths`, but that has fairly
    # high algorithmic complexity for out purposes.
    # If we assume that all outbound paths from `start` are acyclic and
    # end at (or pass through) `end_nbunch` then it's more
    # straightforward to recursively add all successors of `start`
    # until we hit a node in `end_nbunch`:
    nodes = set()
    for node in graph.successors(start):
        if node not in end_nbunch:
            nodes.add(node)
            nodes.update(_nodes_between(graph, node, end_nbunch))
    return nodes

def _sum_weight(graph, node):
    """ TODO """
    # In principal, we only need to ensure that we return the maximum
    # weight of any path from `node` to `sink`. But that problem is
    # NP-hard, whereas just summing over all descendant edges can be
    # done in linear time. Just be sure that there are no cycles!
    weight = 0
    for child in graph.successors(node):
        # Find weights on this node's children:
        if WEIGHT_KEY in graph[node][child]:
            weight += graph[node][child][WEIGHT_KEY]
        # And also on those children's descendants:
        weight += _sum_weight(graph, child)
    return weight

def _add_edge(
        graph, from_node, to_node, **kwargs):
    """ TODO """
    # We allow the input of arbitrary input args (via kwargs), but
    # specific attrs with custom names are processed explicitly.
    if CAPACITY_KEY in kwargs:
        capacity = kwargs[CAPACITY_KEY]
        # Ensure all capacity attrs use the same typing to avoid
        # `unsupported operand type` errors.
        if hasattr(capacity, "amount"):
            # Convert Money-valued `capacity` to Decimal:
            capacity = capacity.amount
        # Capacity must be non-negative (we might receive negative
        # values if capacity is drawn from outflow transactions)
        capacity = abs(capacity)
        # Only assign `capacity` as an edge value if it is finite.
        # (networkx doesn't deal well with Decimal('Infinity'). The
        # "capacity" attr should be absent if capacity is unbounded.)
        if capacity < Decimal('Infinity'):
            # Round `capacity` to an int (recommended by networkx):
            # https://networkx.github.io/documentation/stable/reference/algorithms/generated/networkx.algorithms.flow.max_flow_min_cost.html#networkx.algorithms.flow.max_flow_min_cost
            # (See `Notes`: "This algorithm is not guaranteed to
            # work if edge weights or demands [capacities] are
            # floating point numbers.")
            kwargs[CAPACITY_KEY] = int(capacity)
        else:
            del kwargs[CAPACITY_KEY]

    if WEIGHT_KEY in kwargs:
        # We shouldn't ever add non-floating-point weight, but just in
        # case we'll round it as well:
        # NOTE: No need to worry about infinite-value weights.
        kwargs[WEIGHT_KEY] = int(kwargs[WEIGHT_KEY])

    graph.add_edge(from_node, to_node, **kwargs)

def _add_edges_from(graph, ebunch, **attrs):
    """ TODO """
    capacity_raw = Decimal(0)
    capacity_rounded = Decimal(0)
    edge_variances = {}
    for edge in ebunch:
        # ebunch can have 2 or 3 elements; extract them here:
        if len(edge) == 2:
            u, v = edge
            edge_data = {}
        else:
            u, v, edge_data = edge
        _add_edge(
            graph, u, v, **edge_data,
            # Avoid passing the same keyword twice:
            **{
                key: value for key, value in attrs.items()
                if key not in edge_data})
        # Sum together all of the capacities of the various edges.
        # We'll use this later to check for rounding errors:
        if CAPACITY_KEY in edge_data:
            capacity_raw += edge_data[CAPACITY_KEY]
            capacity_rounded += graph[u][v][CAPACITY_KEY]
            edge_variances[(u, v)] = (
                graph[u][v][CAPACITY_KEY] - edge_data[CAPACITY_KEY])
        else:
            capacity_raw = Decimal('Infinity')
            capacity_rounded = capacity_raw

    # If rounding can't be improved on, terminate:
    if (
            # Deal with exact matches or infinite values:
            capacity_raw == capacity_rounded or
            # And deal with cases where the rounding is as good as
            # possible, given integer precision:
            abs(capacity_raw - capacity_rounded) < 0.5):
        return

    shortfall = int(capacity_raw - capacity_rounded)
    # 1 if we need to add capacity, -1 if we need to reduce capacity:
    increment = int(shortfall / abs(shortfall))
    # Now iterate over the edges, with the edges that are farthest from
    # their target allocation first, and add (or subtract) 1 to them
    # in order until the total capacity of the edges no longer has a
    # shortfall (in integer terms).
    edges_sorted = sorted(
        edge_variances, key=edge_variances.get, reverse=increment < 0)
    edges_iter = iter(edges_sorted)
    while shortfall != 0:
        u, v = next(edges_iter)
        graph[u][v][CAPACITY_KEY] += increment
        shortfall -= increment

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
            self, timing, total, limit, graph=None, source=None, sink=None):
        """ TODO """
        # Convert Money-typed `total` to Decimal:
        if hasattr(total, "amount"):
            total = total.amount
        if graph is None:
            # Build a graph that can accept up to `total` flow at the
            # source and then find the maxium flow that can actually get
            # through to the sink:
            graph, source, sink = self._build_graph(
                timing, total, limit, source, sink)

        total_flows, flows = self._generate_flows(graph, source, sink)
        accounts = self._get_accounts()
        transactions = self._convert_flows_to_transactions(
            flows, timing, limit, accounts)
        # If we couldn't generate any flows, there's no need to recurse:
        if abs(total_flows) < EPSILON:
            return transactions

        # If we couldn't assign all of `total`, reduce the graph (take
        # out at least one edge) and recurse.
        shortfall = total - total_flows
        if abs(shortfall) > EPSILON:
            graph = self._reduce_graph(
                graph, flows, timing, limit, source, sink)
            loop_transactions = self._traverse_priority(
                timing, shortfall, limit,
                graph=graph, source=source, sink=sink)

            # Merge loop_transactions with total_transactions:
            for account in loop_transactions:
                if account in transactions:
                    add_transactions(
                        transactions[account], loop_transactions[account])
                else:
                    transactions[account] = loop_transactions[account]

        return transactions

    def _build_graph(self, timing, total, limit, source=None, sink=None):
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

        # Create an empty graph:
        graph = networkx.DiGraph()
        # We could use the root node of the tree as the graph's source
        # node, but it's convenient if each node can determine the
        # capacities of its outbound weights based on the capacities
        # of its inbound weights. So create a dummy source node with
        # an edge to the root with capacity `total`, unless calling
        # code explicitly requests the root node:
        if source is not self._priority_tree:
            graph.add_edge(
                source, self._priority_tree, capacity=total, weight=0)

        # Recursively build out the group from the root down:
        self._add_node(graph, self._priority_tree, timing, limit, sink=sink)

        return (graph, source, sink)

    def _add_node(
            self, graph, node, timing, limit, sink=None):
        """ TODO """
        # TODO: Embed nodes with applicable limits here
        # This will likely require that we redesign `_add_node_\*` to
        # receive an arbitrary value as the origin of edges to children
        # (this could be a dummy node) and passing `node.children`
        # separately.

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

        method(graph, node, timing, limit, sink=sink)

    def _add_node_weighted(
            self, graph, node, timing, limit, sink=None):
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
        # Calculate the total capacity of inbound edges.
        # This will be distributed to outbound edges.
        capacity = _inbound_capacity(graph, node)

        # TODO: Deal with per-node limits.

        # Weighted nodes assign flows proportionately to weights.
        # Proportionality is easier to calculate with normalized weights
        # so determine that first:
        normalization = sum(node.children.values())
        # Add an edge to each child (this adds both edge and child).
        for child, weight in node.children.items():
            child_total = capacity * weight / normalization
            graph.add_edge(node, child, capacity=child_total, weight=0)
            # Recurse onto the child:
            self._add_node(
                graph, child, timing, limit, sink=sink)

    def _add_node_ordered(
            self, graph, node, timing, limit, sink=None):
        """ TODO """
        # Calculate the total capacity of inbound edges.
        # This will be distributed to outbound edges.
        capacity = _inbound_capacity(graph, node)

        # TODO: Deal with per-node limits.

        # Add an edge to each child (this adds both edge and child).
        # The first child gets a 0-weight node; subsequent children
        # get edges with weight strictly greater than any descendant
        # of the previous children.
        weight = 0
        for child in node.children:
            graph.add_edge(node, child, capacity=capacity, weight=weight)
            # Recurse onto the child:
            self._add_node(
                graph, child, timing, limit, sink=sink)
            # Update weight:
            weight += _sum_weight(graph, child) + 1

    def _add_node_leaf(
            self, graph, node, timing, limit, sink=None):
        """ TODO """
        # Calculate the total capacity of inbound edges.
        # This will be distributed to outbound edges.
        capacity = _inbound_capacity(graph, node)

        # TODO: Deal with per-node limits.

        # Add an edge to the (single) child:
        child = node.source
        graph.add_edge(node, child, capacity=capacity, weight=0)

        # Recurse onto the child:
        self._add_node(graph, child, timing, limit, sink=sink)

    def _add_node_account(
            self, graph, node, timing, limit, sink=None):
        """ TODO """
        # The capacity of an account is not a function of its inbound
        # edges - it's just the most that an account can receive.
        transaction_limit = self._get_transactions(node, limit, timing)
        capacity = sum(transaction_limit.values())

        # Convert Money-valued `capacity` to Decimal:
        if hasattr(capacity, "amount"):
            capacity = capacity.amount

        # Most accounts add an edge straight to `sink`, but accounts
        # that have shared transaction limits have special treatment:
        group = self._get_group(node, limit)
        if group is not None:
            group_node = frozenset(group)  # make hashable
            # TODO: Assign limit in separate method that's called once
            # for each type of limit (i.e. not called again by
            # `_reduce_graph`)
            graph.add_edge(
                node, group_node, capacity=capacity, weight=0, limit=capacity)
            # We're done with the original node; all future edges will
            # be from the group node.
            node = group_node

        # Send an edge from the node to the sink, if provided:
        if sink is not None:
            # TODO: Assign limit in separate method that's called once
            # for each type of limit (i.e. not called again by
            # `_reduce_graph`)
            graph.add_edge(
                node, sink, capacity=capacity, weight=0, limit=capacity)

    def _reduce_graph(self, graph, flows, timing, limit, source, sink):
        """ TODO """
        # Sometimes a node's successors can't accept all the flow that
        # the node wants to send their way. This method aims to:
        # (1) reduce capacities and limits by existing flows;
        # (2) identify the successors that can't accept more flows;
        # (3) shift excess capacity from exhausted successor's inbound
        #     edges to the edges of other successors.
        #     (This is trivial for ordered nodes, but requires some
        #     reweighting for weighted nodes).

        # Reduce capacity and limit by any flows through the edge:
        for parent, child, edge_data in graph.edges_iter(date=True):
            edge_data["capacity"] -= flows[parent][child]
            if "limit" in edge_data:
                edge_data["limit"] -= flows[parent][child]

        # It's easiest to recursively identify exhausted successors,
        # starting from the sink's predecessors and moving on up:
        skip_nodes = self._skip_nodes(graph, sink)

        # If we're skipping source, that means we've added all we can.
        # Return a graph with only the source and sink nodes.
        if source in skip_nodes:
            graph = networkx.DiGraph()
            graph.add_edge(source, sink, capacity=0, weight=0, limit=0)
            return graph

        # Now re-assign weights and capacities for the various nodes.
        self._add_node(graph, self._priority_tree, timing, limit, sink=sink)

        return graph

    def _skip_nodes(self, graph, sink, node=None, skip_nodes=None):
        """ TODO """
        if skip_nodes is None:
            skip_nodes = set()

        # Figure out whether this node should be skipped.
        # It should be skipped if each of its successors is:
        #   (1) in skip_nodes; or
        #   (2) linked to this node by an outbound edge that's hit its
        #       limit.
        # (We don't do this on the first iteration, which we expect to
        # be `sink`, which we never add to `skip_nodes`)
        if node is not None:
            successors = graph.successors(node)
            # Find all nodes linked by edges that have hit their limits:
            limit_nodes = set()
            for successor in successors:
                if (
                        "limit" in graph[node][successor]
                        and graph[node][successor]["limit"] < EPSILON):
                    limit_nodes.add(successor)
            # Figure out whether all successors should be skipped:
            # (We could do a union, but using an `or` should be faster)
            if all(
                    successor in skip_nodes or successor in limit_nodes
                    for successor in successors):
                skip_nodes.add(node)

        # Recurse onto predecessors.
        # (This will cause us to visit some nodes multiple times, which
        # is OK; we may need to visit from each of its children before
        # we can figure out that it needs to be skipped.)
        for node in graph.predecessors(node):
            self._skip_nodes(graph, sink, node, skip_nodes)

        return skip_nodes

    def _generate_flows(self, graph, source, sink):
        """ TODO """
        # For more on this networkx algoritm, see:
        # https://networkx.github.io/documentation/networkx-1.10/reference/generated/networkx.algorithms.flow.max_flow_min_cost.html#networkx.algorithms.flow.max_flow_min_cost
        # TODO: Use capacity and weight constants (not str literals)
        flows = networkx.algorithms.flow.max_flow_min_cost(
            graph, source, sink, capacity='capacity', weight='weight')
        # The sum of flows leaving the source is the total quantity of
        # flow. The source only has one edge (to the tree root), so this
        # is easy to find!
        total = flows[source][self._priority_tree]
        return total, flows

    def _convert_flows_to_transactions(
            self, flows, timing, limit, accounts):
        """ TODO """
        # TODO: Reduce this to a dict comprehension after debugging.
        transactions = {}
        for account in accounts:
            total = sum(flows[account].values())
            total = Money(total)
            transactions[account] = self._get_transactions(
                account, limit, timing, total=total)
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
        weight += graph[node][child]["weight"]
        # And also on those children's descendants:
        weight += _sum_weight(graph, child)
    return weight

def _limit_total(node, total, limits):
    """ TODO """
    # Halt recursion:
    # (Do this here instead of at the end to allow tail recursion)
    if not limits:
        return total

    # TODO: Overhaul handling of per-node limits.
    # It's not clear that the correct limit is simply the smallest
    # non-None limit. If a user specifies `node.limits.min_inflow=0`,
    # does that imply that the _max_ we can contribute is 0? Or simply
    # that we mustn't contribute anything during the min_inflow phase?
    # The latter seems more principled.
    # We probably need to either traverse the graph twice (once for
    # min_inflows and once for max_inflows - though we'd need to modify
    # the graph between traversals to incorporate the results of the
    # earlier traversal!) or make the graph more complex. For example,
    # if a node has two limits, consider embedding it like this:
    #      L1
    #     /  \
    #   N1    C
    #     \  /
    #      L2
    # Where L1 is a dummy node through which min_limit flows move, and
    # where L2 is a dummy node through which max_limit flows move.
    # The edges could have weights and capacities as follows:
    # Edge      Weight  Capacity
    # (N1, L1)  0       node.limits.min_\*
    # (N1, L2)  1       node.limits.max_\* - node.limits.min_\*
    # (L1, C)   0       node.limits.min_\*
    # (L2, C)   0       node.limits.max_\* - node.limits.min_\*
    #
    # The 1-weight to (N1, L2) causes max_\* transactions to only be
    # explored when min_\* transactions are exhausted. The total
    # capacity inbound to C from N1 is unchanged (as node.limits.max_\*)
    #
    # But consider whether the addition of this 1-weight might have
    # undesirable effects when generating flows - could this result in
    # order/weighting not being strictly obeyed? Would we need to create
    # this structure for every node, even if they lacked limits, to
    # ensure that nodes with no limits and 0-weight edges didn't compete
    # with nodes with min_* limits? Or would we need to add 1-weight
    # to every edge (isomorphic to adding L1 with 0-capacity edges);
    # would this cause tree depth to affect ordering/etc.? More
    # consideration is needed before implementing these features.

    # Pick the next limit in the sequence and apply it (if not None):
    limit = limits[0]
    if limit is not None:
        limit_value = getattr(node.limits, limit)
        if limit_value is not None and abs(limit_value) < abs(total):
            total = limit_value
    # Recurse onto the remaining limits:
    return _limit_total(node, total, limits[1:])

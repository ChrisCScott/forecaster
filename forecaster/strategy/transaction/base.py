""" Provides a class for determining schedules of transactions.

These transaction schedules determine when transactions occur, in what
amounts, and to which accounts.
"""

from decimal import Decimal
from queue import SimpleQueue
from forecaster.ledger import Money
from forecaster.utility import EPSILON, add_transactions
from forecaster.accounts.util import LIMIT_TUPLE_FIELDS
from forecaster.strategy.transaction.util import (
    LimitTuple, transaction_default_methods, group_default_methods,
    _get_accounts, _get_group, _get_transactions,
    _convert_flows_to_transactions)
from forecaster.strategy.transaction.node import TransactionNode
from forecaster.strategy.transaction.graph import (
    _get_empty_graph, _add_edge, _flows_through, _generate_flows,
    _inbound_capacity, _merge_flows, _outbound_capacity, _sum_weight,
    _get_outbound_node, _get_overflow_node, _classify_children_by_flows,
    _swap_saturated, _restrict_overflow, _unrestrict_overflow)


class TransactionTraversal:
    """ Determines transactions to/from accounts based on a priority.

    Instances of this class, when initialized, receive a
    `TransactionNode` (or a data structure that is convertible to
    `TransactionNode`, e.g. `list`, `tuple`, `dict`, and/or `Account`).
    This is usually expressible as a tree (and this documentation
    usually describes it as as the "priority tree"), but a true tree
    structure is not required; for example, nodes can share children
    (even across levels).
    In fact, it often is not semantically a tree in practice, since
    leaf nodes (usually `Account`s) can share contribution room or have
    other relationships not captured by the tree structure.

    Instances of this class, when called, traverse a representation of
    the priority tree to allocate transactions to the leaves (which are
    assumed to be accounts, although as described below they do not need
    to inherit from `Account`). The traversal is breadth-first, so that
    higher-level relationships are enforced in preference to lower-level
    relationships. For example:

    *   all lower-level ordered nodes will be exhausted before
        moving on to the next ordered node at a higher level; and
    *   all lower-level weighted nodes will be forced to deviate from
        their target allocation as much as necessary to minimize
        deviations by higher-order weighted nodes.

    This class generates a directed graph based on the input which
    represents the  relationships between nodes. It finds a minimum-cost
    maximum flow across the graph which it translates into transactions
    for each leaf node (usually `Account`s). By default, it does this
    twice, once to allocate minimum transactions and then again to
    allocate maximum transactions.

    The semantics of `TransactionNode` inputs are respected, including
    limits on min/max in/outflows. See documentation for
    `TransactionNode` for more detail.

    As with all `Strategy` objects, objects of this type are callable
    and will return a result resulting from their various settings; in
    this case, a mapping of leaf nodes to transactions.

    Usually leaf nodes are `Account` objects, but any type can be used.
    If using another type, be sure to provide `transaction_methods`
    and `group_methods` that support all of the leaf nodes' types.

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
        priority (TransactionNode, list[Any], dict[Any, Decimal],
            tuple[Any]): The (nested) collection of `Account`s.
        graph (networkx.DiGraph): A directed graph representing all of
            the nodes from `priority`.
        source (Hashable): The node to use as the source of all flows.
        sink (Hashable): The node to use as the destination of all
            flows.
        memo (dict[Hashable, dict[Hashable, int]]): A record of all
            flows assigned by various invocations of
            `_traverse_priority`.
        overflow_nodes (dict[Hashable, Hashable]): A mapping of
            `node: overflow_node` pairs.
        outbound_nodes (dict[Hashable, Hashable]): A mapping of
            `node: outbound_node` pairs. Optional.
        transaction_methods (LimitTuple[Callable]): A tuple of methods,
            each taking a leaf node as the sole argument and returning a
            transactions object (i.e. a `dict[Decimal, Money]` map of
            timings to values).
            Each method of the tuple respects a different limit (e.g.
            `min_inflows`, `max_outflows`).
            Optional. If not provided, methods supporting `Account`-type
            leaf nodes will be used.
        group_methods (LimitTuple[Callable]): A tuple of methods,
            each taking a leaf node as the sole argument and returning a
            group of linked accounts (i.e. a `set[Account]` or, more
            generally, `set[T]` where `T` is any valid type for a leaf
            node in `priority`).
            Each method of the tuple corresponds to a different link
            (e.g. `max_inflow_link`, `min_outflow_link`).
            Optional. If not provided, methods supporting `Account`-type
            leaf nodes will be used.
        precision (float, Decimal): Results will be rounded to this
            level of precision.

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
        dict[Hashable, dict[Decimal, Money]]: A mapping of accounts to
            transactions to (positive) or from (negative) those
            accounts. No `list`, `dict`, or other sub-collection is
            used as a key. Only the leaf node `Account`-like objects of
            the tree defined by `priority` are used as keys.
    """
    def __init__(
            self, priority,
            transaction_methods=None, group_methods=None, precision=EPSILON):
        """ Initializes TransactionTraversal. """
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
        self.precision = precision
        # Store args used by most class methods as attributes to
        # simplify method calls:
        self.graph = None
        self.source = None
        self.sink = None
        self.memo = {}
        self.outbound_nodes = {}
        self.overflow_nodes = {}
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

        # Convert Money-typed `total` to Decimal:
        if hasattr(total, "amount"):
            total = total.amount

        # Determine which limits we need to respect during traversal.
        if total > self.precision:  # inflows
            min_limit = LIMIT_TUPLE_FIELDS.min_inflow
            max_limit = LIMIT_TUPLE_FIELDS.max_inflow
            # Limit min. inflows to what's available:
            min_total = total
        elif total < -self.precision:  # outflows
            min_limit = LIMIT_TUPLE_FIELDS.min_outflow
            max_limit = LIMIT_TUPLE_FIELDS.max_outflow
            # Limit min. outflows based on what's in the account, not
            # the shortfall we're trying to fill:
            min_total = Decimal('-Infinity')
        else:  # No transactions since total ~= 0
            return {}

        # Clear dicts storing former graph information that's carried
        # over between traversals (only memo _needs_ to be, but
        # outbound_nodes and overflow_nodes are guaranteed to be
        # identical between traversals so might as well reuse them).
        self.memo = {}
        self.outbound_nodes = {}
        self.overflow_nodes = {}
        # Build and traverse a graph based on `priority`
        # First traverse to assign min. flows:
        min_transactions = self._traverse_priority(
            min_total, available, min_limit)
        # Then traverse to assign max. flows. Pass in `memo` to ensure
        # that the flows assigned previously are respected
        max_transactions = self._traverse_priority(
            total, available, max_limit)

        # Combine min/max transactions to get final result:
        for account, transactions in min_transactions.items():
            if account in max_transactions:
                add_transactions(max_transactions[account], transactions)
            else:
                max_transactions[account] = transactions
        return max_transactions

    def _traverse_priority(
            self, total, timing, limit):
        """ Builds a graph and finds the min-cost max. flow through it.

        This method translates `priority` into a graph (via
        `_build_graph`), finds the min. cost max. flows through it
        from root to leaves, and translates those flows to transactions.

        If calling multiple times with different `limit` values, you
        may want to pass `memo` at each invocation. This will ensure
        that total flows allocated by this traversal will be reduced
        to account for earlier-allocated flows. Where necessary,
        weighted nodes will be re-weighted to reflect earlier flows.
        This method mutates `memo` to include newly-allocated flows.
        Only incremental transactions (beyond those allocated in earlier
        invocations) are returned via the return value.

        Args:
            total (Decimal): The maximum amount of flow to allow through
                the graph.
            timing (Timing): The timing of account transactions. This is
                used by leaf nodes to find their min/max transactions.
            limit (str): The name for the appropriate attribute of
                `LimitTuple` to use for this traversal (e.g.
                "min_inflow", "max_outflow")

        Returns:
            dict[Hashable, dict[Decimal, Money]]: A mapping of leaf
                nodes to transactions.
        """

        # Build a graph that can accept up to `total` flow at the
        # source and then find the maximum flow that can actually
        # get through to the sink:
        self._build_graph(total, timing=timing, limit=limit)

        _, flows = _generate_flows(self.graph, self.source, self.sink)

        # Store `flows` in memo, so that a later call to this method
        # can reference this information:
        if self.memo is not None:
            _merge_flows(self.memo, flows)

        # Generate transactions for the accounts based on the newly-
        # generated flows. (Note that memoized flows aren't included):
        accounts = _get_accounts(self._priority_tree)
        transactions = _convert_flows_to_transactions(
            flows, timing, limit, accounts,
            transaction_methods=self.transaction_methods, total=total,
            transaction_type=Money, precision=self.precision)

        return transactions

    def _build_graph(self, total, **kwargs):
        """ Generates a graph based on `priority`; assigns it to `graph`

        The generated graph represents each node of `priority`, as well
        as any accounts (stored in leaf nodes). The graph is directed
        and acyclic, provided that `priority` is acyclic. This method
        is not guaranteed to halt (and probably won't!) if `priority`
        has a cycle.

        This method also adds various nodes to support a network flow
        algorithm, including:

        *   a `source` node for flow to originate at and travel from;
        *   a `sink` node for flow to travel to and terminate at;
        *   limit nodes (if applicable) which allow for the addition of
            an edge with limited capacity to be added between a node and
            its children to enforce any per-node limit;
        *   group nodes (if applicable) which several accounts in a
            group may direct flow through to enforce shared group
            limits; and
        *   overflow nodes (if applicable) for weighted nodes which
            allow for flows to children to be reallocated when the
            default weighted allocation isn't possible.

        Edges may be weighted or unweighted (in which case they are
        treated as having 0 weight). Weighted edges are used to enforce
        ordering of flow paths among ordered nodes' children, and to
        disincentivize flow through overflow nodes (thus prioritizing
        the default allocation).

        To execute successfully, this method needs to receive any kwargs
        required by any lower-level `_add_*` methods that are called
        for each node in `priority`. This usually means that at least
        `limit` and `timing` must be provided. (See the
        `_traverse_priority` documentation.)

        Examples:
            ```
                                       T1 -> L1 -> A1
                N                     /              \\
               / \\    -->  source -> N                sink
              T1 T2                   \\              /
                                       T2 -> L2 -> A2
            ```
            In this example, N is an ordered node with children T1 and
            T2 which are leaf nodes wrapping accounts A1 and A2,
            respectively. The `source -> N` edge has a capacity limited
            to `total`. The `T1 -> L1` and `T2 -> L2` edges have
            capacity limited to the applicable `limit` value for T1 and
            T2, respectively. The capacity of the edges directed at
            sink is limited to the applicable
            min_inflow/max_outflow/etc. value for A1 and A2 for the
            given `timing`. The `N -> T1` edge has 0 weight, whereas
            the `N -> T2` weight is larger than any path flow can take
            from T1 to sink (forcing flow to exhaust all such paths
            first).

            (In practice, N might have its own limit node, not shown
            here.)

            If the previous example is modified so that A1 and A2
            are `LinkLimitAccount`s with shared `max_inflow` values
            then the graph would look like this:
            ```
                                       T1 -> L1 -> A1
                N                     /              \\
               / \\    -->  source -> N                group -> sink
              T1 T2                   \\              /
                                       T2 -> L2 -> A2
            ```
            In this case, the `A1 -> group` edge has the same capacity
            as the above `A1 -> sink` edge, but now the `group -> sink`
            edge also has that capacity, so the total amount contributed
            to A1 and A2 will not exceed their shared limit.

            Weighted nodes are a little more complicated because they
            add an overflow node:
            ```
                                        -> T1 -> L1 -> A1
                                       /   |           \\
                N                     /    |            \\
               / \\    -->  source -> N -> O              group -> sink
              T1 T2                   \\   |              /
                                       \\  |             /
                                        -> T2 -> L2 -> A2
            ```
            Here the `N -> O` edge is weighted with unlimited capacity
            and the `N -> T1` and `N -> T2` edges are unweighted with
            limited capacity. In particular, their capacity is
            determined based on the weightings provided by `N.children`.

            In practice, by the time this method completes no flow will
            pass through overflow node O. This is because the capacities
            of the `N -> T1` and `N -> T2` edges have been repeatedly
            rebalanced to reallocate those overflows proportionately
            to the weights of any children that can accept additional
            flow.

        Args:
            total (Decimal): The maximum amount of flow to allow through
                `graph`.
            **kwargs: Arguments to pass to lower-level methods. Must
                include at least "timing" and "limit" keys.
        """
        # The sink and source nodes are each unique dummy objects.
        # Some algorithms don't require a unique sink (e.g. accounts
        # could each be sinks), but it's actually helpful to set edges
        # from accounts to this sink with capacities equal to the
        # account's maximum flow (since the accounts might have multiple
        # inbound edges which, together, exceed the account's capacity).
        # They can be any hasahble value; we default to 0 and 1.
        if self.source is None:
            self.source = 0
        if self.sink is None:
            self.sink = 1

        # networkx has unexpected behaviour for non-int edge capacities,
        # so inflate total based on the EPSILON precision constant:
        if abs(total) < Decimal('Infinity'):
            # We can ignore infinite-valued `total`, which is dealt with
            # in `_add_edge` (and can't be cast to `int`)
            total = int(total / self.precision)

        # Create an empty graph:
        self.graph = _get_empty_graph()
        # We could use the root node of the tree as the graph's source
        # node, but it's convenient if each node can determine the
        # capacities of its outbound weights based on the capacities
        # of its inbound weights. So create a dummy source node with
        # an edge to the root with capacity `total`, unless calling
        # code explicitly requests the root node:
        if self.source is not self._priority_tree:
            _add_edge(
                self.graph, self.source, self._priority_tree,
                capacity=total, memo=self.memo)

        # Recursively build out the group from the root down:
        self._add_successors(
            self._priority_tree, **kwargs)

        # This first pass results in weighted nodes providing too much
        # outbound capacity to their children. Pass over weighted nodes
        # and limit outbound capacity to actual maximum possible flows.
        self._balance_weighted_flows(**kwargs)

    def _add_successors(
            self, node, capacity=None, children=None, limit=None, **kwargs):
        """ Adds the children of `node` to `graph`.

        By the time this method is called, `node` should already be in
        `self.graph`. It will probably still work if not (i.e. `node`
        should be added), but this use case has not been tested for.

        This method will wrap `node` with a limit node (if `node` has
        an applicable limit, and potentially even if not) and calls the
        appropriate `_add_*` method to add the node's children in
        whichever way is appropriate for a `node` of its type. If
        `node` was wrapped with a limit node, edges to children will
        originate with the limit node instead of `node`.

        Args:
            node (Hashable): The node whose successors are being added.
            capacity (int): The maximum flow that can pass through this
                node. Optional.
            children (Iterable[Hashable]): A subset of `node.children`
                on which to recurse. Optional; if not provided, all
                members of `node.children` are recursed on. If provided,
                this arg should be the same type as `node.children`.
            limit (str): The name for the appropriate attribute of
                `LimitTuple` to use for this traversal (e.g.
                "min_inflow", "max_outflow").
            **kwargs: Arguments to pass to lower-level methods. Must
                include at least a "timing" key.
        """
        # Identify which method is used to add the node's children to
        # the graph:
        if not isinstance(node, TransactionNode):
            # Any non-TransactionNode gets treated as an account:
            method = self._add_node_account
        else:  # TransactionNode
            # TransactionNodes come in a few different flavours:
            if node.is_weighted():
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

            # Assign default value _after_ the above so that leaf nodes
            # have a chance to assign their default first.
            if children is None:
                children = node.children

        # Some nodes can have a per-node limit.
        # Enforce this by adding a dummy `outbound_node` and limiting
        # capacity on the edge from `node` to `outbound_node`:
        outbound_node, capacity = self._embed_limit(
            node, limit, capacity=capacity)

        # Record the outbound node if the calling method wants us to:
        if self.outbound_nodes is not None:
            self.outbound_nodes[node] = outbound_node

        method(
            outbound_node, children, capacity=capacity, limit=limit, **kwargs)

    def _embed_limit(
            self, node, limit, *, capacity=None):
        """ Adds an capacity-limited edge from `node` to a limit node.

        This method will add a limit node _at least_ when `node` has an
        applicable limit, but may add limit nodes even when there is not
        an applicable limit for this value of `limit`. For example, it
        may add a limit node for every `TransactionNode`, or for
        transaction nodes that have a limit for one of several limit
        types (not just the one indicated by `limit`).

        If `capacity` is provided, the capacity of the edge from `node`
        to the limit node will not exceed `capacity`.

        Args:
            node (Hashable): The node whose successors are being added.
            limit (str): The name for the appropriate attribute of
                `LimitTuple` to use for this traversal (e.g.
                "min_inflow", "max_outflow").
            capacity (int): The maximum flow that can pass through this
                node. Optional.
        """
        # Process args:
        if capacity is None:
            capacity = _inbound_capacity(self.graph, node)

        # Only TransactionNodes can have per-node limits, so
        # short-circuit for any other node type:
        if not isinstance(node, TransactionNode):
            return node, capacity

        # We always embed TransactionNodes, even if they don't have an
        # applicable limit for this value of `limit`, because we want to
        # ensure that every call to `_traverse_priority` builds a graph
        # with the same topology.
        # NOTE: Its possible to make this more efficient by identifying
        # which nodes possess _any_ applicable limit and generating
        # outbound nodes in the initial stages of _build_graph. That's
        # an optimization that can wait for a working build.
        if node in self.outbound_nodes:
            outbound_node = self.outbound_nodes[node]
        else:
            outbound_node = (node, "limit")

        # Figure out whether `node` has an applicable limit:
        limit_value = None
        if hasattr(node, "limits") and hasattr(node.limits, limit):
            limit_value = getattr(node.limits, limit)
            # Convert from Money-like to Decimal, if applicable:
            if hasattr(limit_value, "amount"):
                limit_value = limit_value.amount
            if limit_value is not None:
                # Scale up the limit value by `precision` to avoid
                # rounding issues:
                limit_value /= self.precision
                # Reduce `limit_value` based on any memoized flows
                # through `node`:
                limit_value -= _flows_through(node, flows=self.memo)
                # Use the lesser of `capacity` and `limit_value`;
                # successors use this to determine their edge capacities
                capacity = min(capacity, limit_value)

        # Connect `node` and `outbound_node` via a directed edge:
        if limit_value is not None:
             # If `node` had an applicable limit, the edge will have
             # `limit_value` capacity. This enforces the limit!
            _add_edge(self.graph, node, outbound_node, capacity=limit_value)
        else:
            # If there's no applicable limit, the edge has infinite
            # capacity (represented by omitting the capacity argument)
            _add_edge(self.graph, node, outbound_node)

        # Return the new outbound node and the (potentially-reduced)
        # capacity. Any children should receive edges from
        # `outbound_node` instead of `node`.
        return outbound_node, capacity

    def _add_node_weighted(
            self, node, children,
            *, capacity=None, add_overflow=True, **kwargs):
        """ Adds a weighted node's children to the graph.

        Adds an edge from `node` to each child with 0 weight and
        capacity equal to `node`'s total inbound capacity, scaled down
        proportionately to the weight that `node` gives the child.

        If `add_overflow` is `True`, an overflow node is also added with
        a weighted edge from `node` to the overflow node (and edges from
        the overflow node to children which are unweighted and have
        unlimited capacity). The weighted edge is guaranteed to have
        a weight larger than the total weight of any path from any
        member of `children` to `sink`.

        Args:
            node (TransactionNode): A weighted node with one or more
                children.
            children (dict[Hashable, Decimal]): The children to be
                added to the graph, mapped to their relative weights.
            capacity (int): The maximum flow that can pass through this
                node. Optional.
            add_overflow (bool): If True, adds an overflow node between
                `node` and each member of `children`. Optional; defaults
                to `True`.
            **kwargs: Arguments to pass to lower-level methods. Must
                include at least "timing" and "limit" keys.
        """
        if capacity is None:
            # Calculate the total capacity of inbound edges.
            # This will be distributed to outbound edges.
            capacity = _inbound_capacity(self.graph, node)

        if add_overflow:
            # For weighted nodes, we want to prioritize assigning flows
            # as dictated by the nodes' weights, while still allowing
            # flows to be shifted between children if some children
            # can't receive the full amount dictated by their weight.
            # We accomplish this by adding weighted edges between
            # children that allow (but penalize) flows between children.
            # (We route all these edges through `overflow_node` so that
            # the number of edges added is `n+1`, where `n` is the
            # number of children. If added directly between children,
            # the number of edges would be `n^2`.)
            if self.overflow_nodes is not None and node in self.overflow_nodes:
                overflow_node = self.overflow_nodes[node]
            else:
                overflow_node = (node, "overflow")
                if self.overflow_nodes is not None:
                    self.overflow_nodes[node] = overflow_node
            # Add an edge from `node` to `overflow_node` and from
            # `overflow_node` to each child. This enables shifting flow
            # between children. (We'll add weight to the
            # node->overflow_node edge later, once we know the weights
            # of all paths to `sink`):
            _add_edge(self.graph, node, overflow_node, capacity=capacity)
            for child in children:
                _add_edge(self.graph, overflow_node, child, capacity=capacity)

        # Recursively add successor nodes:
        self._add_weighted_children(
            node, children, capacity, add_overflow=add_overflow, **kwargs)

        if add_overflow:
            # We want the flow through each child to be as close as
            # possible to the capacity assigned above (i.e. we want to
            # move as little flow as possible between children.)
            # Accomplish this by heavily penalizing flows through
            # `overflow_node`.
            # It should be preferable to shift flow between _any_
            # successor path before routing it through `overflow_node`.
            weight = 1 + max(_sum_weight(
                self.graph, child) for child in children)
            _add_edge(self.graph, node, overflow_node, weight=weight)

        # This deals with overflows, but not underflows - which are
        # basically guaranteed, since each child node has more inbound
        # capacity than is needed to achieve its weighted flows (thanks
        # to the extra capacity from overflow_node).
        # We'll need to solve this after the first complete iteration
        # of the graph has been built.

    def _add_weighted_children(
            self, node, children, capacity, **kwargs):
        """ Helper method for `_add_node_weighted`.

        This method does the actual calculating of child nodes'
        capacities and adding of children to the graph. Unlike
        `_add_node_weighted`, this method doesn't worry about overflow
        nodes (which are handled by the parent method).

        One important feature of this method is that it accounts for
        any flows in `self.memo` so that the resulting capacities remain
        true to the weights of `children` _after_ the flows in
        `self.memo` are added in. This is essential for allowing
        `_traverse_priority` to be called multiple times with different
        limit values without introducing unbalanced flows among weighted
        children.

        If the flows in `self.memo` are greater than would otherwise be
        allocated based on weights, this method distorts the children's
        weights as little as possible to accomodate. In particular, it
        sets those children to have 0 capacity and recurses on the
        remaining children to allocate the remaining capacity
        proportionately among them.

        Args:
            node (TransactionNode): A weighted node with one or more
                children.
            children (dict[Hashable, Decimal]): The children to be
                added to the graph, mapped to their relative weights.
            capacity (int): The maximum flow that can pass through this
                node. Optional.
            **kwargs: Arguments to pass to lower-level methods. Must
                include at least "timing" and "limit" keys.
        """
        # Weighted nodes assign flows proportionately to weights.
        # Proportionality is easier to calculate with normalized weights
        # so determine that first:
        normalization = sum(children.values())
        # If we've previously assigned flows from `node` (or, rather,
        # its corresponding outbound node) to any of `children`, account
        # for that by increasing `capacity` here and decrementing that
        # flow from the child's proportionate capacity later on:
        outbound_node = _get_outbound_node(node, self.outbound_nodes)
        flows = _flows_through(
            outbound_node, flows=self.memo, children=children)
        capacity += flows

        # Generate a proportionate weighting for each child:
        totals = {}
        for child, weight in children.items():
            # Each child is allocated a slice of `capacity`
            # proportionate to its weight in `children`:
            child_total = capacity * weight / normalization
            # Reduce this capacity to account for any memoized flows:
            child_total -= _flows_through(outbound_node, child, flows=self.memo)
            # Save this allocation:
            totals[child] = child_total

        # Deal with the scenario where some children have been assigned
        # negative capacity (i.e. memoized flows are greater than the
        # total amount that would ordinarily be assigned here):
        if any(total < 0 for total in totals.values()):
            # Recurse on any children which have not previously been
            # allocated more flows than their weight dictates:
            recurse_children = {
                child: weight for child, weight in children.items()
                if totals[child] > 0}
            # Capacity should be restored to its original value...
            capacity -= flows
            # ... and further reduced by the amount of excess flows
            # previously allocated to some children:
            capacity += sum(total for total in totals.values() if total < 0)
            self._add_weighted_children(
                node, recurse_children, capacity, **kwargs)
            # As for the children that have been over-allocated flow,
            # give them 0-capacity edges (since negative capacity is
            # not allowed):
            totals = {
                child: 0 for child, total in totals.items() if total <= 0}

        # Generate edges for `children` (or, if we recursed onto a
        # subset, onto the remainder that wasn't recursed on):
        for child, child_total in totals.items():
            # Add the edge (this implicitly adds the child to the
            # graph if it hasn't already been added)
            _add_edge(self.graph, outbound_node, child, capacity=child_total)
            # Then recurse onto the child:
            self._add_successors(child, **kwargs)

    def _balance_weighted_flows(self, **kwargs):
        """ Rebalances capacities of children of weighted nodes.

        This method visits each weighted node in breadth-first order
        and calls `_balance_flows` on each child.

        Args:
            **kwargs: Arguments to pass to lower-level methods. Must
                include at least "timing" and "limit" keys.
        """
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
            self._balance_flows(node, **kwargs)

    def _balance_flows(
            self, node, children=None, rebalance_all=True, **kwargs):
        """ Attempts to shift flow between children to match weights.

        Based on the flows from `node` to `children`, we can identify 3
        sets of child nodes.
        (References to a child's "capacity" below refers to the
        capacity of all zero-weight paths from `node` to the child.)

        1. Underflow nodes: Flow to these nodes from `node` is less than
            their capacity.
        2. Overflow nodes: Flow to these nodes exceeds their capacity
            (i.e. they receive flow over non-zero-weight paths).
        3. Saturated nodes: All nodes that are not underflow or overflow
            nodes. These have received exactly their capacity in flows.

        There is no guarantee that overflow and underflow nodes are
        weighted properly relative to each other, since there's no
        mechanism to force flows through a set of identically-weighted
        paths to adhere to a certain proportion of flows. This method
        recurses onto each of those sets of children separately,
        thereby attempting to reallocate capacity between them in a way
        that respects weightings.

        We know we can recurse on those sets of nodes separately because
        overflow nodes only receive flow if they _must_, and underflow
        nodes only fail to reach saturation if it's _impossible_ to do
        so (so long as total flow through `node` is at least as large
        as the capacity of the children - which this method enforces).

        Saturated nodes are included when recursing onto both underflow
        and overflow nodes. This is because it's possible for a
        saturated node to share capacity with underflow or overflow
        nodes. It might be appropriate to reallocate capacity from a
        saturated node to an underflow node and/or to reallocate
        capacity from an overflow node to a saturated node.

        Args:
            node (Hashable): The node whose children are being
                rebalanced.
            children (dict[Hashable, Decimal]): The children to be
                rebalanced, mapped to their relative weights. Optional.
                If not provided, all children of `node` are rebalanced.
            rebalance_all (bool): If `True`, this method will attempt to
                reassign capacities if they don't match total flows.
                It sets this to `False` on recursion to avoid infinite
                recursion due to rounding error. Optional. Defaults to
                `True`.
            **kwargs: Arguments to pass to lower-level methods. Must
                include at least "timing" and "limit" keys.
        """
        if children is None:
            children = node.children

        if not children:
            # Nothing to process if there are no children. Done.
            return

        # Try to generate flows through the graph.
        _, flows = _generate_flows(self.graph, self.source, self.sink)
        # Divide nodes based on whether flows match their capacities:
        underflow, overflow, saturated = _classify_children_by_flows(
            self.graph, node, children, flows,
            self.outbound_nodes, self.overflow_nodes)

        # Terminate if all nodes are saturated. This means we found
        # a perfect proportion of flows to satisfy the source node's
        # weights:
        if not underflow and not overflow:
            return
        # If only _one_ of those two is empty, then we have an imbalance
        # in capacity; need to reassign capacities to match flows:
        elif bool(underflow) != bool(overflow):
            # `rebalance_all` ensures that we recurse here *at most
            # once* for each instance of children. (Can have infinite
            # recursion due to rounding errors; this avoids that.)
            if rebalance_all:
                # Force recalculation of 0-weight edges' capacity based
                # on the actual sum of flows through this node:
                self._balance_flows_recurse(
                    node, children=children, flows=flows,
                    rebalance_all=False, **kwargs)
                # Don't proceed on, since the old `flows` is based on
                # unbalanced capacities.
                return
            elif saturated:
                # We can't move capacity out of `saturated`, so treat
                # them as under/overflow (whichever is empty):
                if not underflow:
                    saturated, underflow = underflow, saturated
                else:
                    saturated, overflow = overflow, saturated
            else:
                # If there are no saturated nodes then we have only
                # underflow/overflow. Not much that can be done there.
                return

        # We are guaranteed to have both underflow and overflow nodes.
        # Recurse first onto all non-overflow nodes, to see if any
        # capacity from saturated nodes can be shifted to underflow
        # nodes in a way that better reflects their proportionate
        # weights:
        underflow_expanded = underflow.union(saturated)
        self._balance_flows_recurse(
            node, children=underflow_expanded, flows=flows, **kwargs)

        # Any saturated nodes that have changed capacity will
        # necessarily have had their capacity reduced; shift those
        # into `underflow`. This avoids recursing onto them in
        # the non-overflow step.
        _swap_saturated(
            saturated, underflow, node, children, self.graph, flows,
            outbound_nodes=self.outbound_nodes)

        # Now do the same thing, but for non-underflow nodes.
        overflow_expanded = overflow.union(saturated)
        # NOTE: We use the same `flows` because only flows to
        # _underflow_ nodes have changed in the previous step.
        self._balance_flows_recurse(
            node, children=overflow_expanded, flows=flows, **kwargs)

    def _balance_flows_recurse(
            self, node, children=None, flows=None, **kwargs):
        """ Helper method for `_balance_flows`.

        Calls `_add_successors` on `children` to distribute capacity
        between them to match the amount in `flows` and then recurses
        onto `_balance_flows` to ensure that the new capacities of
        `children` are distributed correctly.

        Args:
            node (Hashable): The node whose children are being
                rebalanced.
            children (dict[Hashable, Decimal]): The children to be
                rebalanced, mapped to their relative weights. Optional.
                If not provided, all children of `node` are rebalanced.
            flows (dict[Hashable, dict[Hashable, int]]): Flows through
                the graph, as `from_node: (to_node: flow)` triples.
            **kwargs: Arguments to pass to lower-level methods. Must
                include at least "timing" and "limit" keys.
        """
        # Process input:
        if children is None:
            children = node.children
        outbound_node = _get_outbound_node(node, self.outbound_nodes)
        overflow_node = _get_overflow_node(
            node, self.overflow_nodes, outbound_node=outbound_node)

        if flows is not None:
            # Calling code can provide `flows`, in which case edges to
            # children should be re-allocated based on actual flows
            # (rather than capacities, which may be under- or
            # over-provisioned).
            capacity = sum(flows[outbound_node][child] for child in children)
            if overflow_node is not None:
                capacity += sum(
                    flows[overflow_node][child] for child in children)
        else:
            # Otherwise, simply use the 0-weight capacity to `children`:
            capacity = _outbound_capacity(
                self.graph, outbound_node, weight=0, children=children)

        # _add_successors expects `children` to have the appropriate
        # typing for this kind of node, so enforce that here:
        children_subset = node.children_subset(children)
        # Attempt to reallocate capacity among children based on the
        # parent node's weights.
        self._add_successors(
            node, capacity=capacity, children=children_subset,
            # (Don't mess with overflow nodes at this stage)
            add_overflow=False, **kwargs)
        # If there are multiple children, recurse onto them to ensure
        # that they are balanced relative to each other:
        if len(children) > 1:
            # Ensure that, if any changes in capacity cause additional
            # flow to go through `overflow_node`, that such overflows
            # are directed to `children` (which we know can accept it.)
            _restrict_overflow(
                self.graph, node, children, flows, self.overflow_nodes,
                outbound_nodes=self.outbound_nodes)
            self._balance_flows(node, children=children, **kwargs)
            # Undo the foregoing mutation of edges from `overflow_node`:
            _unrestrict_overflow(self.graph, node, self.overflow_nodes)

    def _add_node_ordered(
            self, node, children, *, capacity=None, **kwargs):
        """ TODO """
        if capacity is None:
            # Calculate the total capacity of inbound edges.
            # This will be distributed to outbound edges.
            capacity = _inbound_capacity(self.graph, node)

        # Add an edge to each child (this adds both edge and child).
        # The first live (i.e. non-skipped) child gets all the capacity.
        weight = 0
        for child in children:
            _add_edge(
                self.graph, node, child, capacity=capacity, weight=weight)
            # Recurse onto the child:
            self._add_successors(child, **kwargs)
            # Ensure that assigning flows to the next child in sequence
            # has a penalty larger than any path through the current
            # child's successors:
            weight = max(weight, _sum_weight(self.graph, child)) + 1

    def _add_node_leaf(
            self, node, child, *, capacity=None, **kwargs):
        """ TODO """
        if capacity is None:
            # Calculate the total capacity of inbound edges.
            # This will be distributed to outbound edges.
            capacity = _inbound_capacity(self.graph, node)

        # Add an edge to the (single) child:
        _add_edge(self.graph, node, child, capacity=capacity)

        # Recurse onto the child:
        self._add_successors(child, **kwargs)

    def _add_node_account(
            self, node, child,
            *, timing=None, limit=None, **kwargs):
        """ TODO """
        # pylint: disable=unused-argument
        # `child` isn't used by this method, but it needs to provide the
        # same number sequence of positional args as other `_add_node_*`
        # methods, because `_add_successors` will provide a value (None,
        # in the case of this method).

        # NOTE: It's expensive to query the account, and for a given
        # `limit` the result shouldn't change. Consider caching the
        # result on first invocation and reusing it on subsequent
        # invocations.

        # The capacity of an account is not a function of its
        # inbound edges. It's dictated by the account itself.
        # Query the account for the time-series of transactions that
        # defines its capacity for the given `limit`:
        transactions = _get_transactions(
            node, limit, timing, transaction_methods=self.transaction_methods)
        transaction_limit = sum(transactions.values())
        # Convert `transaction_limit` to a non-Money type (since
        # Money is not convertible to int, which is a problem later)
        if hasattr(transaction_limit, "amount"):
            transaction_limit = transaction_limit.amount
        # Scale up based on the precision (as we do with all edge
        # capacities):
        capacity = transaction_limit / self.precision

        # Most accounts add an edge straight to `sink`, but accounts
        # that have shared transaction limits have special treatment:
        group = _get_group(node, limit, group_methods=self.group_methods)
        if group is not None:
            group_node = frozenset(group)  # make hashable
            # Reduce capacity based on any memoized flows through
            # `group_node` (which accounts for all flows through all
            # of the linked nodes of the group)
            # This prevents inadvertent over-contribution/withdrawal:
            capacity -= _flows_through(group_node, flows=self.memo)
            _add_edge(
                self.graph, node, group_node,
                capacity=capacity, limit=capacity)
            # We're done with the original account node; all further
            # edges will be from the group node.
            node = group_node
        else:
            # Reduce capacity based on any memoized flows through `node`
            capacity -= _flows_through(node, flows=self.memo)

        # Send an edge from the node to the sink, if provided:
        if self.sink is not None:
            _add_edge(
                self.graph, node, self.sink, capacity=capacity, limit=capacity)

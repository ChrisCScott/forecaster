""" Provides methods for generating and manipulating graphs.

Wraps networkx and adds a few convenience methods.
"""

from decimal import Decimal
import networkx

CAPACITY_KEY = "capacity"
WEIGHT_KEY = "weight"
LIMIT_KEY = "limit"

def _get_empty_graph():
    """ Generates an empty directed graph.

    Returns:
        networkx.DiGraph
    """
    return networkx.DiGraph()

def _inbound_capacity(graph, node):
    """ Calculates the total capacity of inbound edges to node.

    Args:
        graph (networkx.DiGraph): A directed graph.
        node (Hashable): A node in `graph`.

    Returns:
        Decimal: The sum of the capacities of inbound edges. Inbound
        edges with no `capacity` attribute are ignored.
    """
    # For each node, we'll calculate this amount each time the node is
    # encountered and distribute it between outbound edges.
    # (We do it this way, rather than passing `capacity` in as an arg
    # from the parent node during recursion, because `node` could be
    # found at multiple spots in the tree, so the amount to distribute
    # between outbound edges can change during recursion.)
    capacity = sum(
        graph[parent][node][CAPACITY_KEY]
        for parent in graph.predecessors(node)
        if CAPACITY_KEY in graph[parent][node])
    # Avoid setting `capacity` to a non-Decimal value:
    # TODO: If any(CAPACITY_KEY not in graph[parent[node]]) then
    # return Decimal('Infinity')?
    if not isinstance(capacity, Decimal):
        capacity = Decimal(capacity)
    return capacity

def _outbound_capacity(graph, node, weight=None, children=None):
    """ Calculates the total capacity of outbound edges from node.

    Args:
        graph (networkx.DiGraph): A directed graph.
        node (Hashable): A node in `graph`.
        weight (int): Only edges with this weight value are included.
            Optional. If not provided, all edges are included.
        children (Iterable[Hashable]): If provided, only edges between
            `node` and members of `children` are included. Optional.

    Returns:
        Decimal: The sum of the capacities of outbound edges from
        `node` to its successors. Outbound edges with no `capacity`
        attribute are ignored.
    """
    if children is None:
        children = graph.successors(node)
    capacity = 0
    # Add up the capacities of all outbound edges:
    for child in children:
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

def _sum_weight(graph, node):
    """ Returns the sum of edge weights of all n-successors of `node`.

    `graph` must be acyclic, otherwise this method may not terminate.

    Args:
        graph (networkx.DiGraph): A directed graph.
        node (Hashable): A node in `graph`

    Returns:
        int: The sum of weights of all edges from `node` to its
        successors, from those successors to their successors, and
        so on.
    """
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
        graph, from_node, to_node, memo=None, **kwargs):
    """ Adds an edge to `graph` from `from_node` to `to_node`.

    This method wraps `networkx.DiGraph.add_edge`. Edge attributes may
    be passed in as kwargs. (Note that `memo` is a special kwarg which
    is not translated into an attribute.) Certain attributes with
    significance to `networkx` are processed to avoid errors.

    For `capacity` attributes (passed via the `capacity` kwarg), this
    method converts `Decimal`- or `Money`-valued attribute inputs to
    `int`, handles infinite-valued inputs appropriately, and reduces
    edges' capacities based on any flows in `memo`.

    This method also converts non-int `weight` attributes to `int`.

    Args:
        graph (networkx.DiGraph): A directed graph.
        from_node (Hashable): A node in `graph`. The added edge will
            start at this node.
        to_node (Hashable): A node in `graph`. The added edge will end
            at this node.
        memo (dict[Hashable: dict[Hashable: int]]): Flows as
            `from_node: (to_node: flow_value)` triples. Optional.
        **kwargs (dict[str: Any]): A mapping of attribute names to
            attribute values for the added edge.
    """
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

        # Reduce capacity by any previously-allocated flows over this
        # edge:
        capacity -= _flows_through(from_node, to_node, flows=memo)
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

def _merge_flows(first, second):
    """ Merges flows in `second` into `first`. Mutates `first`.

    Args:
        first (dict[Hashable: dict[Hashable: int]]): Flows as
            `from_node: (to_node: flow_value)` triples. *Mutated.*
        second (dict[Hashable: dict[Hashable: int]]): Flows as
            `from_node: (to_node: flow_value)` triples.
    """
    # Iterate over edges in `second` by iterating over pairs of nodes:
    for from_node in second:
        for to_node in second[from_node]:
            # These aren't defaultdicts, so ensure there's a dict in
            # first[from_node] for us to add to later:
            if from_node not in first:
                first[from_node] = {}
            # If this edge is in `first`, mutate `first` by adding the
            # value in `second`:
            if to_node in first[from_node]:
                first[from_node][to_node] += second[from_node][to_node]
            # Otherwise insert the value from `second` into `first`:
            else:
                first[from_node][to_node] = second[from_node][to_node]

def _flows_through(from_node, to_node=None, *, flows=None, children=None):
    """ Calculates the total flows through `from_node`.

    This method can be called several ways. If `to_node` is provided,
    only flows from `from_node` to `to_node` are included. If `children`
    is provided, only froms from `from_node` to members of `children`
    are included. At most one of `to_node` and `children` may be
    provided.

    Returns 0 if `flows` is not provided. This is provided for
    convenience, since in many applications `flows` is really a `memo`
    dict which may be `None` (in which case it's easiest to return 0).

    Args:
        from_node (Hashable): A node.
        to_node (Hashable): A node. Optional.
        flows (dict[Hashable: dict[Hashable: int]]): Flows as
            `from_node: (to_node: flow_value)` triples. Optional.
        children (Iterable[Hashable]): A collection of nodes. Optional.

    Returns:
        int: The total flows through `from_node` in `flows` (restricted
        to flows from `from_node` to `to_node` or nodes in `children`
        if provided.)
    """
    # Find the total flows through `node` allocated during previous
    # iterations of `_traverse_priority` (as recorded in `memo`):
    if flows is None or from_node not in flows:
        # If there are no applicable flows, return 0
        return 0
    if to_node is not None and children is not None:
        raise ValueError('Cannot pass both `to_node` and `children` arguments')

    # Deal with the four non-trivial cases:
    if children is not None:
        # Return flows from `from_node` to `children`
        return sum(flows[from_node][child] for child in children)
    elif to_node is None:
        # If only `from_node` is provided, return the sum of all
        # outbound flows.
        return sum(flows[from_node].values())
    elif to_node in flows[from_node]:
        # If `from_node` is provided and there are flows between
        # `from_node` and `to_node`, return those flows
        return flows[from_node][to_node]
    else:
        # Otherwise, there are no flows from `from_node` to `to_node`,
        # so return 0
        return 0

def _generate_flows(graph, source, sink):
    """ Generates maximum flows through `graph` at minimum cost.

    "Cost" here refers to the the product of flows over edges by the
    weights of those edges.

    `graph` is preferably acyclic, although this method should work for
    any directed graph without a negative-weight cycle. Cycles get
    computationally expensive fast, though.

    Args:
        graph (networkx.DiGraph): A directed graph.
        source (Hashable): A node in `graph`. Unlimited flow originates
            at this node and attempts to flow to `sink`.
        sink (Hashable): A node in `graph`. This is the only node that
            can receive flow via an inbound edge without passing it
            through to an outbound edge.

    Returns:
        dict[Hashable: dict[Hashable: int]]: Flows as
            `from_node: (to_node: flow_value)` triples. Optional.
    """
    # For more on this networkx algoritm, see:
    # https://networkx.github.io/documentation/networkx-1.10/reference/generated/networkx.algorithms.flow.max_flow_min_cost.html#networkx.algorithms.flow.max_flow_min_cost
    flows = networkx.algorithms.flow.max_flow_min_cost(
        graph, source, sink, capacity=CAPACITY_KEY, weight=WEIGHT_KEY)
    # Total flow is equal to whatever's flowing out of `source`:
    total = sum(flows[source].values())
    return total, flows

def _get_related_node(node_relations, *nodes):
    """ Finds a node that is related to one of the nodes in `nodes`.

    "Related" can mean anything, but in general this method is intended
    to be used to find a node that wraps another node, in the sense that
    the related node is the origin for edges which ordinarily would
    originate at the wrapped node. Client code sometimes refers to such
    nodes as outbound nodes or overflow nodes.

    This method finds the first node from `nodes` that's in
    `node_relations` and returns the corresponding value. If that can't
    be done, it returns None.

    Args:
        node_relations (dict[Hashable, Hashable], NoneType): A mapping
            of nodes to their related nodes, or None.
        *nodes (tuple[Hashable]): A collection of nodes.

    Returns:
        (Hashable, NoneType): A value from `node_relations` with a
            member of `nodes` as a key (and specifically the value for
            the first member of `nodes` in `node_relations`), or None
            if such a value cannot be found.
    """
    # If there are no related nodes in general, we can't find a related
    # node, so return None:
    if node_relations is None:
        return None
    # If a given `node` is mapped to a related node, return the mapped
    # node. (Try each node in `node` in order, terminating on the first
    # one that corresponds to a mapped node in `node_relations`)
    for node in nodes:
        if node is not None and node in node_relations:
            return node_relations[node]
    # If we couldn't find a relation, return None:
    return None

def _get_outbound_node(node, outbound_nodes):
    """ Returns the outbound node corresponding to `node`.

    An outbound node is the node that is the origin for edges that
    ordinarily would originate at `node`, but don't because `node` has
    been embedded as some subgraph that uses another node as the origin
    for such edges.

    If no such node is found in `outbound_nodes`, this method returns
    `node`, since it's its own outbound node.

    Args:
        node (Hashable): A node.
        outbound_nodes (dict[Hashable, Hashable]): A mapping of
            `node: outbound_node` pairs.

    Returns:
        Hashable: The outbound node for `node` (which may be `node`
        itself).
    """
    outbound_node = _get_related_node(outbound_nodes, node)
    if outbound_node is None:
        return node
    return outbound_node

def _get_overflow_node(node, overflow_nodes, outbound_node=None):
    """ Returns the overflow node corresponding to `node`.

    An overflow node is a node that is the origin for additional edges
    from `node` to its successors (i.e. `node` may have edges to its
    successors, with additional capacity flowing through an overflow
    node). This allows a `DiGraph` to approximate some features of a
    `MultiGraph`.

    `node` may be wrapped by an `outbound_node`; in that case,
    `outbound_node`'s overflow node will be returned if it exists.
    If it doesn't, then `node`'s will be returned.
    If neither exists, then `None` is returned.

    Args:
        node (Hashable): A node.
        overflow_nodes (dict[Hashable, Hashable]): A mapping of
            `node: overflow_node` pairs.
        outbound_node (NoneType, Hashable): A node that is used to wrap
            `node` such that `outbound_node`'s outbound edges are
            attributable to `node`.

    Returns:
        Hashable, NoneType: The overflow node for `node` (via
        `outbound_node`, if provided) or `None` if no such node exists.
    """
    # Check for an overflow node attached to `outbound_node` first,
    # then fall back to `node` if none was found:
    return _get_related_node(overflow_nodes, outbound_node, node)

def _restrict_overflow(
        graph, node, children, flows, overflow_nodes, outbound_nodes=None):
    """ Limits overflows to successors not in `children` at given flows.

    If `node` (or its outbound node) has an overflow node, outbound
    edges from that overflow node to any children not in `children` have
    their capacity limited to the values for those edges in `flows`.
    This prevents any children not in `children` from increasing their
    total flows, but allows flows to shift between nodes in `children`.

    `_unrestrict_overflow` is a companion method.

    Args:
        graph (networkx.DiGraph): A directed graph.
        node (Hashable): A node in `graph`
        children (Iterable[Hashable]): A collection of `node`'s children
            to which overflows should _not_ be restricted.
        flows (dict[Hashable: dict[Hashable: int]]): Flows as
            `from_node: (to_node: flow_value)` triples. Optional.
        overflow_nodes (dict[Hashable, Hashable]): A mapping of
            `node: overflow_node` pairs.
        outbound_nodes (dict[Hashable, Hashable]): A mapping of
            `node: outbound_node` pairs. Optional.
    """
    # Process input:
    outbound_node = _get_outbound_node(node, outbound_nodes)
    overflow_node = _get_overflow_node(
        node, overflow_nodes, outbound_node=outbound_node)

    if overflow_node is None:
        # If there is no overflow node, there's nothing to do.
        return

    # Limit the capacity from `overflow_node` to each child of `node`
    # which is _not_ in `children`. The goal here is to ensure that any
    # changed in 0-weight capacity result in excess flow being forced
    # through `children` (via `overflow_node`) and not other nodes.
    for child in node.children:
        if child not in children:
            if overflow_node in flows and child in flows[overflow_node]:
                capacity = flows[overflow_node][child]
            else:
                capacity = 0
            edge_data = {CAPACITY_KEY: capacity}
            graph.add_edge(overflow_node, child, **edge_data)

def _unrestrict_overflow(
        graph, node, overflow_nodes, outbound_nodes=None):
    """ Undoes the effects of `_restrict_overflow`.

    If `node` (or its outbound node) has an overflow node, outbound
    edges from that overflow node have their capacity reset so as not
    to restrict flows over those edges.

    Args:
        graph (networkx.DiGraph): A directed graph.
        node (Hashable): A node in `graph`
        overflow_nodes (dict[Hashable, Hashable]): A mapping of
            `node: overflow_node` pairs.
        outbound_nodes (dict[Hashable, Hashable]): A mapping of
            `node: outbound_node` pairs. Optional.
    """
    # Process input:
    outbound_node = _get_outbound_node(node, outbound_nodes)
    overflow_node = _get_overflow_node(
        node, overflow_nodes, outbound_node=outbound_node)

    if overflow_node is None:
        # If there is no overflow node, there's nothing to do.
        return

    # Restore plenty of capacity to each edge from `overflow_node` to
    # each child:
    capacity = _outbound_capacity(graph, outbound_node, weight=0)
    for child in node.children:
        edge_data = {CAPACITY_KEY: capacity}
        graph.add_edge(overflow_node, child, **edge_data)

def _swap_saturated(
        saturated, non_saturated, node, children, graph, flows,
        outbound_nodes=None):
    """ Moves nodes with differing flows/capacity to `non_saturated`.

    Any nodes in `saturated` which have inbound flows from `node`
    that are different from the flows in `flows` are moved to
    `non_saturated`. The implication of such a mismatch is that
    such nodes now receive more or less flows than their 0-weight
    capacity, which means they are not saturated.

    `saturated` and `non_saturated` are mutated by this method.

    Args:
        saturated (set[Hashable]): A collection of nodes to check for
            saturated status.
        non_saturated (set[Hashable]): A collection of nodes to move
            non-saturated nodes to.
        node (Hashable): A predecessor to nodes in `saturated`; only
            paths between `node` and nodes in `saturated` are considered
        children (Iterable[Hashable]): A collection of `node`'s
            children. Only nodes in `children` will be moved.
        graph (networkx.DiGraph): A directed graph.
        flows (dict[Hashable: dict[Hashable: int]]): Flows as
            `from_node: (to_node: flow_value)` triples. Optional.
        outbound_nodes (dict[Hashable, Hashable]): A mapping of
            `node: outbound_node` pairs. Optional.
    """
    # Process input:
    outbound_node = _get_outbound_node(node, outbound_nodes)

    # Re-calculate membership of `saturated`. This is intended to be
    # called after reallocation of capacity between nodes based on
    # previously-identified underflows or overflows:
    for child in children:
        # Iterate over `children` instead of `saturated` because we
        # want to mutate `saturated`:
        if child in saturated:
            new_capacity = graph[outbound_node][child][CAPACITY_KEY]
            old_capacity = flows[outbound_node][child]
            if new_capacity != old_capacity:
                saturated.remove(child)
                non_saturated.add(child)

def _classify_children_by_flows(
        graph, node, children, flows,
        outbound_nodes=None, overflow_nodes=None):
    """ Classifies children as overflowed, underflowed, or saturated.

    Each child in `children` receives some amount of flow from `node`
    (via `flows`). If this exceeds the capacity of 0-weight edges then
    the child is an overflow node. If it is less than the capacity of
    0-weight edges then it is an underflow node. If flows and 0-weight
    capacity are matched then it is a saturated node.

    This tells you something about whether or not the node is a
    bottleneck in the flow algorithm:

    *   Underflow nodes definitely *are*. Paths from underflow nodes to
        `sink` cannot accomodate the current outbound capacity.
    *   Overflow nodes definitely *are not*. Flow intended for
        underflow nodes has been redirected to them because paths from
        those nodes to `sink` have excess capacity.
    *   Saturated nodes might go either way. It might be that they have
        excess capacity which simply wasn't used by the flow-assigning
        algorithm, or they might have consumed 100% of their capacity
        (and thus implicitly be bottlenecks insofar as the question of
        where to assign excess capacity is concerned.)

    Args:
        graph (networkx.DiGraph): A directed graph.
        node (Hashable): A node in `graph`
        children (Iterable[Hashable]): A collection of `node`'s children
            to which overflows should _not_ be restricted.
        flows (dict[Hashable: dict[Hashable: int]]): Flows as
            `from_node: (to_node: flow_value)` triples. Optional.
        outbound_nodes (dict[Hashable, Hashable]): A mapping of
            `node: outbound_node` pairs. Optional.
        overflow_nodes (dict[Hashable, Hashable]): A mapping of
            `node: overflow_node` pairs. Optional.

    Returns:
        tuple[set[Hashable], set[Hashable], set[Hashable]]: The nodes in
        `children`, divided into disjoint sets as follows:
        `(underflow_nodes, overflow_nodes, saturated_nodes)`.
    """
    # Process input:
    outbound_node = _get_outbound_node(node, outbound_nodes)
    overflow_node = _get_overflow_node(
        node, overflow_nodes, outbound_node=outbound_node)

    # Define some sets to contain each group of children:
    underflow_nodes = set()
    overflow_nodes = set()
    saturated_nodes = set()
    # Add each node to exactly one of those sets:
    for child in children:
        # Nodes with flows that are less than their max. 0-weight
        # capacity are underflow nodes:
        if (
                graph[outbound_node][child][CAPACITY_KEY]
                > flows[outbound_node][child]):
            underflow_nodes.add(child)
        # Nodes that receive flow via overflow_node must be receiving
        # more than their max. 0-weight capacity, and are overflow nodes
        elif overflow_node is not None and flows[overflow_node][child] > 0:
            overflow_nodes.add(child)
        # Any other node is receiving exactly its 0-weight capacity, and
        # is a saturated node:
        else:
            saturated_nodes.add(child)
    return underflow_nodes, overflow_nodes, saturated_nodes

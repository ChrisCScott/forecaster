""" Helper methods and classes for TransactionStrategy. """

from collections import namedtuple, abc

# Define helper classes for storing data:

LIMIT_TUPLE_FIELDS = ['min_inflow', 'max_inflow', 'min_outflow', 'max_outflow']
LimitTuple = namedtuple(
    'LimitTuple', LIMIT_TUPLE_FIELDS,
    defaults=(None,) * len(LIMIT_TUPLE_FIELDS))
LimitTuple.__doc__ = (
    "A data container holding different values for min/max inflow/outfow")

# Parent nodes (i.e. non-leaf nodes) can be ordered or weighted. These
# are distinguished by their types; represent those here for easy
# extension/modification. (Use `tuple` to easier for `isinstance`)
ORDERED_NODE_TYPES = (list, tuple)
WEIGHTED_NODE_TYPES = (dict,)
PARENT_NODE_TYPES = ORDERED_NODE_TYPES + WEIGHTED_NODE_TYPES

class TransactionNode:
    """ A data container for notes about nodes of a priority tree.

    This is intended for use with TransactionStrategy, which provides
    traversal logic.

    Attributes:
        source (dict[Any, Decimal], list[Any], tuple[Any], Account): A
            user-provided tree structure.

            Nodes may be native `dict`, `list`, and `tuple` objects.
            `dict` elements are unordered; each key is a child node and
            the corresponding value is a weight. `list` or `tuple`
            objects provide an ordered sequence of child nodes. (Tip:
            use `tuple` for nodes that need to be stored as keys in a
            `dict`). `Account` objects (or similar) are leaf nodes.

            Nodes may optionally be `TransactionNode` objects, which
            must provide their own non-`TransactionNode` `source`
            attributes. These will not be wrapped in a further
            `TransactionNode`.
        limits (LimitTuple[Money]): Limits on min/max in/outflows for
            this `TransactionNode`. These do not replace any limits on
            leaf nodes' `Account` objects. The intention is that the
            strictest limit will be enforced by traversing code.
        group_methods (LimitTuple[Callable]): A tuple of methods,
            each taking one argument and returning a group of linked
            accounts (i.e. a `set[Account]` or, more generally, `set[T]`
            where `T` is any valid type for a leaf node in `priority`).
            Each method of the tuple corresponds to a different link
            (e.g. `max_inflow_link`, `min_outflow_link`).
        children (dict[TransactionNode: Decimal],
            tuple(TransactionNode)): The children of this node, which
            are `TransactionNode` objects encapulating the children
            of the corresponding node in `source`. (If a child in
            `source` is a `TransactionNode`, it is not re-encapsulated).

            `children` is a dict if the node is weighted (i.e. if the
            `source` version of the node is a dict) and a tuple if the
            node is ordered (i.e. if the `source` version of the node
            is a list or tuple).
        groups (LimitTuple[set[set[Account]]]): A set of all
            contribution groups present in this node or its children
            (of any depth), for each type of limit in `LimitTuple`.

            For example, `groups.max_inflow` could be
            `{{account1, account2}, {account3, account4}}`, where the
            max inflows of `account1` and `account2` are linked and the
            max inflows of `account3` and `account4` are also linked.
    """
    def __init__(self, source, limits=None, group_methods=None):
        """ Initializes TransactionNode. """
        if isinstance(source, type(self)):
            # Copy initialization:
            self.source = source.source
            self.group_methods = source.group_methods
            self.groups = source.groups
            self.limits = source.limits
            return

        # Hold on to the original list/dict/whatever.
        # (Consider copying it in case input `children` is mutated?)
        self.source = source

        # Parse `limits` input:
        if limits is not None:
            # Cast to LimitTuple if not already in that format:
            if not isinstance(limits, LimitTuple):
                limits = LimitTuple(*limits)
            self.limits = limits
        else:
            # To avoid testing for `self.limits is not None` elsewhere,
            # assign an all-None-valued LimitTuple if `limits` was not
            # provided.
            self.limits = LimitTuple()

        # Parse `group_methods` inputs:
        if group_methods is None:
            group_methods = group_default_methods()
        self.group_methods = group_methods

        # Generate `children` attribute by recursively generating a
        # TransactionNode instance for each child in `source`.
        self.children = _children_from_source(self)
        # Generate `groups` attribute based on leaf nodes (by applying
        # the methods of `group_methods`) and combining at parent nodes:
        self.groups = _groups_from_source(self)

    def is_leaf_node(self):
        """ Returns True if the node is a leaf node, False otherwise. """
        return not self.is_parent_node()

    def is_parent_node(self):
        """ Returns True if the node is a parent (non-leaf) node. """
        return isinstance(self.source, PARENT_NODE_TYPES)

    def is_ordered(self):
        """ Returns True if the node is an ordered parent node. """
        return (
            isinstance(self.source, PARENT_NODE_TYPES)
            and isinstance(self.source, abc.Sequence))

    def is_weighted(self):
        """ Returns True if the node is a weighted parent node. """
        return (
            isinstance(self.source, PARENT_NODE_TYPES)
            and isinstance(self.source, abc.Mapping))

def _children_from_source(node):
    """ Converts children in `source` to `TransactionNode`s """
    # Ordered and weighted nodes need to be handled differently:
    if node.is_ordered():
        return _children_from_source_ordered(node)
    elif node.is_weighted():
        return _children_from_source_weighted(node)
    elif node.is_leaf_node():
        # Leaf nodes have no children
        return tuple()
    else:
        raise TypeError(
            str(type(node.source)) + " is not a supported type.")

def _children_from_source_ordered(node):
    """ Converts ordered children in `source` to `TransactionNode`s """
    children = []
    # Convert each child to TransactionNode, if not already
    # in that format, and store as a tuple with the same order
    # as in `source`:
    for child in node.source:
        if isinstance(child, TransactionNode):
            children.append(child)
        else:
            children.append(TransactionNode(
                child, group_methods=node.group_methods))
    return tuple(children)

def _children_from_source_weighted(node):
    """ Converts weighted children in `source` to `TransactionNode`s """
    children = {}
    # Convert each child to TransactionNode, if not already in
    # that format, and store as a tuple with the same
    for child, weight in node.source.items():
        if not isinstance(child, TransactionNode):
            child = TransactionNode(
                child, group_methods=node.group_methods)
        children[child] = weight
    return children

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
    # We want to build a LimitTuple (so that each kind of limit has
    # its own groups). Rather than hard-code field names, iterate
    # over each field of LimitTuple in order:
    for field_name in LIMIT_TUPLE_FIELDS:
        # Get the group method for this min/max in/outflow limit:
        method = getattr(node.group_methods, field_name)
        # Use the method to get the appropriate group:
        if method is not None:
            groups.append(method(node.source))
        # (or simply use the empty set if there's no such method)
        # NOTE: We don't return a set containing this account
        # to make it easy for client code to skip over accounts
        # which don't belong to groups, and we don't return None
        # to spare client code from the hassle of sprinkling in
        # tests for None.
        else:
            groups.append(set())
    return LimitTuple(*groups)

def reduce_node(
        node, remove_children,
        child_transactions=None, _reduce_limit_methods=None):
    """ Generates a tree with certain children removed.

    Args:
        node (TransactionNode): The node to be reduced.
        remove_children (set[TransactionNode]): The children of `node`
            to be removed.
        child_transactions (dict[TransactionNode,
            dict[Decimal, Money]]): A mapping of nodes to transactions.
            Optional. If passed in, any limits on the reduced node will
            be reduced by an amount equal to the sum of any transactions
            already recorded against the children being removed.
            Optional.
        _reduce_limit_methods (LimitTuple[Callable]): Methods which
            take two arguments: `limit` (a `Money` object) and
            `transactions` (a `Money` object). The methods return a new
            limit reduced based on `transactions`; the new limit is a
            `Money` object. Optional; if not provided, the default
            methods of `reduce_limit_default_methods()` are used.
    """
    # At a basic level, we need to reduce `source` to exclude the items
    # in `remove_children`, but `remove_children`'s elements are
    # `TransactionNode` objects and `source`'s are not. So use
    # `remove_children` to reduce `node.children` and then use the
    # results of _that_ to reduce `source` (since each child contains
    # a `source` attribute that should be present in `node.source`).
    if node.is_ordered():
        # For ordered nodes, generate a tuple with children in
        # `remove_children` removed.
        children = tuple(
            child for child in node.children if child not in remove_children)
        source = tuple(child.source for child in children)
    elif node.is_weighted():
        # For weighted nodes, generate a dict with children in
        # `remove_children` removed. Copy weights of remaining children.
        children = {
            child: weight for child, weight in node.children.items()
            if child not in remove_children}
        source = {child.source: weight for child, weight in children.items()}
    elif not node.children:
        # Leaf nodes can't be reduced, so just return it as-is.
        return node
    else:
        # If the node has children but isn't recognized by the above,
        # there's a problem.
        raise ValueError('node has children but is not supported.')

    # If transactions have been passed in, we should reduce any limits
    # based on the values of those transactions:
    if child_transactions is not None:
        limits = []
        # Determine the total transactions to children being removed:
        transactions = sum(
            sum(child_transactions[child].values())
            for child in remove_children)
        # We reduce limits differently for inflows and outflows; let
        # the methods of reduce_limit_default_methods tell us how to
        # handle that:
        if _reduce_limit_methods is None:
            _reduce_limit_methods = reduce_limit_default_methods()
        for field_name in LIMIT_TUPLE_FIELD_NAMES:
            # Get each min/max in/outflow limit:
            limit = getattr(node.limits, field_name)
            # If this node has such a limit, reduce it based on the
            # transactions against the accounts being removed:
            if limit is not None:
                reduce_limit_method = getattr(
                    _reduce_limit_methods, field_name)
                limit = reduce_limit_method(limit, transactions)
            limits.append(limit)

    # Groups will be updated automatically upon init:
    return TransactionNode(
        source, limits=limits, group_methods=node.group_methods)

# Define helper functions for identifying an account's min/max:

# Give an easy way for refactors to update references to LimitTuples:
LIMIT_TUPLE_FIELD_NAMES = LimitTuple(*LIMIT_TUPLE_FIELDS)
# Map LimitTuple fields to the names of AccountLink members of
# LinkedLimitAccount objects:
LINK_FIELD_NAMES = LimitTuple(
    'min_inflow_link', 'max_inflow_link',
    'min_outflow_link', 'max_outflow_link')
# Map LimitTuple fields to the named of min/max inflow/outflow members
# of Account objects:
TRANSACTION_LIMIT_FIELD_NAMES = LimitTuple(
    'min_inflows', 'max_inflows', 'min_outflows', 'max_outflows')

def transaction_default_methods(field_names=TRANSACTION_LIMIT_FIELD_NAMES):
    """ Returns methods for finding min/max in/outflows as a LimitTuple. """
    methods = []
    # Rather than write out four separate methods that return
    # min_inflows, max_inflows, ..., we write a generator for such
    # methods and return a full set of them as a LimitTuple:
    for field_name in field_names:
        # We use `field_name` as a default value to avoid the issue
        # where the closure will use the most recent value for
        # `field_name` rather than the value at the time the closure
        # was defined. (This could also be solved by using a partial).
        # The default value is locked in at definition time.
        methods.append(lambda account, name=field_name: getattr(account, name))
    return LimitTuple(*methods)

def group_default_methods(field_names=LINK_FIELD_NAMES):
    """ Returns methods returning sets of linked accts. as a LimitTuple. """
    methods = []
    # Rather than write out four separate methods that return
    # min_inflow_link, max_inflow_link, ..., we write a generator for
    # such methods and return a full set of them as a LimitTuple:
    for field_name in field_names:
        # Define a method that returns the group of linked accounts for
        # a given link (e.g. `max_inflow_link`).
        # NOTE: Use `field_name` as a default value to avoid the issue
        # where the closure will use the most recent value for
        # `field_name` rather than the value at the time the closure
        # was defined. (This could also be solved by using a partial).
        # The default value is locked in at definition time.
        def default_method(account, name=field_name):
            # Return the group for the given link if the link exists:
            if hasattr(account, name):
                link = getattr(account, name)
                if link is not None:
                    return link.group
            # If the account doesn't have a link (either because it's
            # not a LinkedLimitAccount or similar, or because its link
            # is None), then simply return None:
            return None
        # default_method over. It will be added to the LimitTuple later.
        methods.append(default_method)
    return LimitTuple(*methods)

def reduce_limit_default_methods():
    """ Returns methods for reducing limits based on transactions. """
    def add_inflows(limit, transactions):
        """ Reduces inflow limit based on transactions. """
        # No change if there are no net inflows:
        if transactions > 0:
            # Limits on inflows must be non-negative:
            limit = max(limit - transactions, 0)
        return limit
    def add_outflows(limit, transactions):
        """ Reduces outflow limit based on transactions. """
        # No change if there are no net outflows:
        if transactions < 0:
            # Limits on outflows must be non-positive:
            limit = min(limit - transactions, 0)
        return limit
    return LimitTuple(
        min_inflow=add_inflows, max_inflow=add_inflows,
        min_outflow=add_outflows, max_outflow=add_outflows)

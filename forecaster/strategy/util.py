""" Helper methods and classes for TransactionStrategy. """

from collections import namedtuple, abc
from copy import copy

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

    For use with TransactionStrategy.
    """
    def __init__(self, source, limits=None, group_methods=None):
        """ TODO """
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
        self.children = self._children_from_source()
        # Generate `groups` attribute based on leaf nodes (by applying
        # the methods of `group_methods`) and combining at parent nodes:
        self.groups = self._groups_from_source()

    def is_leaf_node(self):
        """ TODO """
        return not self.is_parent_node()

    def is_parent_node(self):
        """ TODO """
        return isinstance(self.source, PARENT_NODE_TYPES)

    def is_ordered(self):
        """ TODO """
        return (
            isinstance(self.source, PARENT_NODE_TYPES)
            and isinstance(self.source, abc.Sequence))

    def is_weighted(self):
        """ TODO """
        return (
            isinstance(self.source, PARENT_NODE_TYPES)
            and isinstance(self.source, abc.Mapping))

    def _children_from_source_ordered(self):
        """ TODO """
        children = []
        # Convert each child to TransactionNode, if not already
        # in that format, and store as a tuple with the same order
        # as in `source`:
        for child in self.source:
            if isinstance(child, TransactionNode):
                children.append(child)
            else:
                children.append(TransactionNode(
                    child, group_methods=self.group_methods))
        return tuple(children)

    def _children_from_source_weighted(self):
        """ TODO """
        children = {}
        # Convert each child to TransactionNode, if not already in
        # that format, and store as a tuple with the same
        for child, weight in self.source.items():
            if not isinstance(child, TransactionNode):
                child = TransactionNode(
                    child, group_methods=self.group_methods)
            children[child] = weight
        return children

    def _children_from_source(self):
        """ TODO """
        # Ordered and weighted nodes need to be handled differently:
        if self.is_ordered():
            return self._children_from_source_ordered()
        elif self.is_weighted():
            return self._children_from_source_weighted()
        elif self.is_leaf_node():
            # Leaf nodes have no children
            return set()
        else:
            raise TypeError(
                str(type(self.source)) + " is not a supported type.")

    def _groups_from_source_parent(self):
        """ TODO """
        groups = []
        # Iterate over each field of LimitTuple in order (this makes
        # building a new LimitTuple of results easier):
        for field_name in LIMIT_TUPLE_FIELDS:
            group = set()
            # For the selected limit type (e.g. `max_inflow`), collect
            # all of the groups present in the children:
            for child in self.children:
                # Get each child's groups for this limit.
                # If any are repeated between children, they'll only be
                # added once (since sets guarantee uniqueness)
                inner_group = getattr(child.groups, field_name)
                if inner_group is not None:
                    # `group` needs hashable members, so use frozenset:
                    group.add(frozenset(inner_group))
            groups.append(group)
        return LimitTuple(*groups)

    def _groups_from_source_leaf(self):
        """ TODO """
        groups = []
        # We want to build a LimitTuple (so that each kind of limit has
        # its own groups). Rather than hard-code field names, iterate
        # over each field of LimitTuple in order:
        for field_name in LIMIT_TUPLE_FIELDS:
            # Get the group method for this min/max in/outflow limit:
            method = getattr(self.group_methods, field_name)
            # Use the method to get the appropriate group:
            if method is not None:
                groups.append(method(self.source))
            # (or simply use the empty set if there's no such method)
            # NOTE: We don't return a set containing this account
            # to make it easy for client code to skip over accounts
            # which don't belong to groups, and we don't return None
            # to spare client code from the hassle of sprinkling in
            # tests for None.
            else:
                groups.append(set())
        return LimitTuple(*groups)

    def _groups_from_source(self):
        """ TODO """
        # Ordered and weighted nodes need to be handled differently:
        if self.is_parent_node():
            return self._groups_from_source_parent()
        elif self.is_leaf_node():
            return self._groups_from_source_leaf()
        else:
            raise TypeError(
                str(type(self.source)) + " is not a supported type.")

def reduce_node(
        node, remove_children,
        child_transactions=None, _reduce_limit_methods=None):
    """ TODO """
    # At a basic level, we need to reduce `source` to exclude the items
    # in `remove_children`, but `remove_children`'s elements are
    # `TransactionNode` objects and `source`'s are not. So use
    # `remove_children` to reduce `node.children` and then use the
    # results of _that_ to reduce `source` (since each child contains
    # a `source` attribute that should be present in `node.source`).
    if node.is_ordered():
        children = tuple(
            child for child in node.children if child not in remove_children)
        source = tuple(child.source for child in children)
    elif node.is_weighted():
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
        # the methods of reduce_limit_methods tell us how to handle that
        if _reduce_limit_methods is None:
            _reduce_limit_methods = reduce_limit_methods()
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

def reduce_limit_methods():
    """ Returns methods for reducing limits based on transactions. """
    def add_inflows(limit, transactions):
        """ TODO """
        # No change if there are no net inflows:
        if transactions > 0:
            # Limits on inflows must be non-negative:
            limit = max(limit - transactions, 0)
        return limit
    def add_outflows(limit, transactions):
        """ TODO """
        # No change if there are no net outflows:
        if transactions < 0:
            # Limits on outflows must be non-positive:
            limit = min(limit - transactions, 0)
        return limit
    return LimitTuple(
        min_inflow=add_inflows, max_inflow=add_inflows,
        min_outflow=add_outflows, max_outflow=add_outflows)

# TODO: Sort out how to map nodes to Annotation objects.
# The central issue is that mutable types (i.e. most nodes) are not
# hashable, and thus not valid keys in a standard dict.
#
# We could generate a make_hashable method that cast each node of
# `priority` to a hashable type (e.g. set -> frozenset, list -> tuple,
# dict -> ??? (add the third-party frozendict library? create a custom
# hashable_dict type? c.f. https://stackoverflow.com/a/1151705)).
# This adds complexity by causing the internal `priority` tree to differ
# from the tree provided - e.g. it would evaluate to not-equal.
#
# We could forego some efficiency and use a datastructure with slower
# lookup (e.g. a list or set of (node, annotation) tuples). But we do
# a lot of lookups - once per node, per traversal!
#
# We could generate a whole annotated tree structure, rather than a
# mapping. This loses out of the potential to avoid duplicate
# annotations if a node happens to be repeated, but that is likely to be
# rare (much rarer than traversals...). Consider building an
# `_annotated_priority` tree where each node is a (node, annotation)
# tuple (namedtuple?). It's easy enough to unpack each node at the start
# of each `_process_*` method (e.g. change the arg to `annotated_node`
# and add the new first line `node, annotation = annotated_node`).
# This avoids hashing issues.

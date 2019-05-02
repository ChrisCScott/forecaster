""" Helper methods and classes for TransactionStrategy. """

from collections import abc
from forecaster.accounts import LimitTuple, LIMIT_TUPLE_FIELDS
from forecaster.strategy.transaction.util import (
    group_default_methods, TRANSACTION_DEFAULT_METHODS,
    reduce_limit_default_methods, is_done_default)

# Define helper classes for storing data:

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

    def weights_by_group(
            self, limit_key, timing=None, transactions=None, memo=None,
            is_done=None, transaction_methods=None):
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
        if is_done is None:
            is_done = is_done_default
        if transaction_methods is None:
            transaction_methods = TRANSACTION_DEFAULT_METHODS

        if self.is_ordered():
            # Ordered nodes only contribute to the first node, so assign
            # the first non-full node a weight of 100%
            weights = tuple()
            for child in self.children:
                weights = child.weights_by_group(
                    limit_key, timing=timing, transactions=transactions,
                    memo=memo, is_done=is_done,
                    transaction_methods=transaction_methods)
                # Stop at the first child that returns non-empty weights
                if weights:
                    break
            # No further processing; an ordered node's behaviour is
            # precisely that of its first (non-done) child.
            return weights

        elif self.is_weighted():
            # Weighted nodes are more complicated. Get the weights of
            # each child's groups, scale them down by the weight
            # associated with the child itself, and merge the weights of
            # any groups represented by multiple children (by adding):
            weights = {}
            for child in self.children:
                # Get the weights associated with the child's groups:
                child_weights = child.weights_by_group(
                    limit_key, timing=timing, transactions=transactions,
                    memo=memo, is_done=is_done,
                    transaction_methods=transaction_methods)
                # Add those weights to the parent node's group-weights:
                for group, weight in child_weights.items():
                    # Scale down the added weights by the parent nodes'
                    # weight on the child:
                    weight *= self.children[child]
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
            # Leaf node:
            account = self.source
            group_method = getattr(self.group_methods, limit_key)
            group = group_method(account)
            if group is None:
                group = {account}
            # cast to a hashable type:
            group = frozenset(group)
            if is_done(
                    group, limit_key,
                    timing=timing, transactions=transactions, memo=memo,
                    transaction_methods=transaction_methods):
                # No weights to return if the account won't receive
                # any allocation:
                return {}
            # Otherwise, contribute 100% to this account:
            return {group: 1}

    def transaction_threshold(
            self, limit_key, timing=None, transactions=None,
            is_done=None, transaction_methods=None):
        """ TODO

        This method finds the largest amount that is guaranteed to be
        allocatable by this node without exceeding any transaction
        limits (of itself and/or its children).

        Args:
            limit_key (str): A name of a `LimitTuple` field
                corresponding to the type of limit this method should
                aim to respect.

        Returns:
            (Money, set[set[Account]]): The
        """
        memo = {}
        # TODO: Sort out how to deal with per-node limits.
        weights = self.weights_by_group(
            limit_key, timing=timing, memo=memo, transactions=transactions,
            is_done=is_done, transaction_methods=transaction_methods)
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
        for field_name in LIMIT_TUPLE_FIELDS:
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

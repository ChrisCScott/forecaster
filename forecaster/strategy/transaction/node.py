""" Helper methods and classes for TransactionStrategy. """

from collections import abc
from forecaster.accounts import LimitTuple

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
        children (dict[TransactionNode: Decimal],
            tuple(TransactionNode)): The children of this node, which
            are `TransactionNode` objects encapulating the children
            of the corresponding node in `source`. (If a child in
            `source` is a `TransactionNode`, it is not re-encapsulated).

            `children` is a dict if the node is weighted (i.e. if the
            `source` version of the node is a dict) and a tuple if the
            node is ordered (i.e. if the `source` version of the node
            is a list or tuple).
    """
    def __init__(self, source, limits=None):
        """ Initializes TransactionNode. """
        if isinstance(source, type(self)):
            # Copy initialization:
            self.source = source.source
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

        # Generate `children` attribute by recursively generating a
        # TransactionNode instance for each child in `source`.
        self.children = _children_from_source(self)

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

    def children_subset(self, subset):
        """ Returns a reduced form of `children` based on `subset.

        The reduced form includes only children in `subset` but has the
        same typing as `children`. So, for example, for a weighted node
        `node.children_subset({child_node})` will return a dict of the
        form `{child_node: weight}` where `weight` is equal to
        `node.children[child_node]`.

        Args:
            subset (Container): An iterable container containing only
                elements of `node.children`.

        Raises:
            KeyError: An element of `subset` is not present in
                `self.children`.
            NotImplementedError: `node.children` is of a type that this
                class does not recognize.
                This is most likely caused by implementing a subclass
                that allows for a differently-typed `children` attribute
                but which hasn't overloaded this method to deal with it.
        """
        if isinstance(self.children, dict):
            # Preserve the weights (values) of `node.children`:
            return {child: self.children[child] for child in subset}
        if isinstance(self.children, (list, tuple)):
            # Preserve the ordering of `node.children`:
            if any(child not in self.children for child in subset):
                raise KeyError('subset contains element not in children.')
            return type(self.children)(
                child for child in self.children if child in subset)
        # Type of `children` is determined by __init__, so if we get
        # this far we're likely in a subclass that hasn't overloaded
        # this method properly.
        raise NotImplementedError(
            str(type(self.children)) + " is not a supported type for the "
            "children attribute.")

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
    # Convert each child to TransactionNode, if not already in that
    # format, and store as a tuple with the same order as in `source`:
    for child in node.source:
        if not isinstance(child, TransactionNode):
            child = TransactionNode(child)
        children.append(child)
    return tuple(children)

def _children_from_source_weighted(node):
    """ Converts weighted children in `source` to `TransactionNode`s """
    children = {}
    # Convert each child to TransactionNode, if not already in
    # that format, and store as a dict with the same weights (values):
    for child, weight in node.source.items():
        if not isinstance(child, TransactionNode):
            child = TransactionNode(child)
        children[child] = weight
    return children

""" Helper methods and classes for TransactionStrategy. """

from dataclasses import dataclass, field
from collections import namedtuple, abc

# Define helper classes for storing data:

LIMIT_TUPLE_FIELDS = ['min_inflow', 'max_inflow', 'min_outflow', 'max_outflow']
LimitTuple = namedtuple('LimitTuple', LIMIT_TUPLE_FIELDS)
LimitTuple.__doc__ = (
    "A data container holding different values for min/max inflow/outfow")

@dataclass
class Annotation:
    """ A data container for notes about nodes of a priority tree.

    For use with TransactionStrategy.
    """
    groups: LimitTuple = field(default=(None,) * len(LIMIT_TUPLE_FIELDS))
    limits: LimitTuple = field(default=(None,) * len(LIMIT_TUPLE_FIELDS))

def annotate_account(account, group_methods):
    """ Generates an Annotation for an Account (or similar) object.

    Args:
        account (Account, Any): An account which is to be passed as the
            sole argument to each method in `group_methods`.
        group_methods (LimitTuple[Callable]): A tuple of methods
            (one for each min/max in/outflow `Account` method), each
            of which takes one argument (`account`) and returns a set
            of accounts.

            One or more fields of `group_methods` may be None, in which
            case the corresponding fields of the resulting Annotation
            will also be None.

    Returns:
        Annotation: An annotation for `account`.
    """
    groups = []
    # Rather than hard-code field names, simply iterate over each field
    # of LimitTuple in order
    for field_name in LIMIT_TUPLE_FIELDS:
        # Get the appropriate group method for this min/max in/outflow:
        method = getattr(group_methods, field_name)
        # Use the method to get the appropriate group (or simply
        # record `None` if there is no method to call for this limit):
        if method is not None:
            groups.append(method(account))
        else:
            # TODO: Do we want to allow `None` values for groups?
            # Perhaps recording the empty set is more appropriate.
            groups.append(None)
    return Annotation(LimitTuple(*groups))

def merge_annotations(*args):
    """ Merges any number of Annotation objects into one. """
    groups = []
    # Iterate over each field of LimitTuple in order (this makes
    # building a new LimitTuple of results easier):
    for field_name in LIMIT_TUPLE_FIELDS:
        # For the selected limit type (e.g. `max_inflow`), build up a
        # set of linked accounts:
        # TODO: Revise this logic to allow for nested sets?
        # Right now it looks like we're adding accounts from different
        # contribution groups to the same set (including accounts which
        # aren't necessarily present in a given node's children.)
        group = set()
        # Take the union of groups for this limit type:
        for annotation in args:
            inner_group = getattr(annotation.groups, field_name)
            if inner_group is not None:
                group.update(inner_group)
        # TODO: Do we want to allow `None` values for groups? Perhaps
        # recording the empty set is more appropriate.
        # (c.f. `annotate_account`)
        if group:
            groups.append(group)
        else:
            groups.append(None)
    return Annotation(LimitTuple(*groups))

# Define helper functions for identifying an account's min/max:

LINK_FIELD_NAMES = LimitTuple(
    'min_inflow_link', 'max_inflow_link',
    'min_outflow_link', 'max_outflow_link')
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

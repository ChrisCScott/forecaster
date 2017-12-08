""" This module provides various convenience methods for testing. """

import collections
import traceback
import warnings
import sys


def type_check(val, types):
    """ Recursively checks that all elements in val are of correct type.

    If `types` is iterable, this method (a) tests that `val` is an
    instance of the same iterable type, and (b) tests that each element
    of `val` is an instance of the type at the corresponding level of
    depth in `types`.

    If `types` is an iterable, it must have at most one element. That
    element must be a type object or an iterable which itself has the
    same structure. (If the iterable is empty, the elements of the
    corresponding iterable of `val` are not type-checked.)

    Example:
        d = {'one': {2, 3}, 'two': {4, 5}}
        type_check(d, {str: {int}})  # Evaluates to True
        type_check(1, int)  # Evaluates to True

    Returns:
        True if the types of `val` correspond to the types of `types`.

    Raises:
        ValueError: `types` must have only one element at each level.
    """
    # First, deal with the iterable case:
    if isinstance(types, collections.Iterable):
        # Check that val and types are of the same (ish) iterable type:
        if not isinstance(val, type(types)):
            return False
        # We don't know what to do with multiple elements.
        if len(types) > 1:
            raise ValueError('type_check: types must have only one ' +
                             'element at each level.')
        # In the typical case, we have exactly one element. We'll
        # want to recurse on that.
        elif len(types) == 1:
            # If it's a dict, check both keys and values
            if isinstance(types, dict):
                key_type = next(iter(types.keys()))
                val_type = next(iter(types.values()))
                return all(
                    type_check(k, key_type) and
                    type_check(v, val_type)
                    for k, v in val.items()
                )
            # For non-dict iterables, iterate over their elements:
            else:
                val_type = next(iter(types))
                return all(
                    isinstance(v, val_type) for v in val
                )
        else:
            # If the iterable is empty, no need to recurse
            return True
    else:
        return isinstance(val, types)


def warn_with_traceback(message, category, filename, lineno, file=None,
                        line=None):
    """ Forces warnings to be more verbose during testing. """
    log = file if hasattr(file, 'write') else sys.stderr
    traceback.print_stack(file=log)
    log.write(warnings.formatwarning(message, category, filename, lineno,
                                     line))

warnings.showwarning = warn_with_traceback

warnings.simplefilter("always")

""" This module provides functions for copying and replacing objects. """

import copy
from functools import update_wrapper
from types import FunctionType, CellType

def populate_memo(original, replacement, memo=None):
    """ Returns a memo that uses `replacement` in place of `original`.

    This method depends on implementation details of `copy.deepcopy`.
    In particular, this only works if `copy.deepcopy` populates its
    `memo` arg with `{id(original): copy}` pairs, where `original` is
    the object being copied and `copy` is a copy of `original`.

    This is a bit naughty. `copy.deepcopy`'s documentation is clear that
    you should not do this:
        > The memo dictionary should be treated as an opaque object.
        > https://docs.python.org/3/library/copy.html
    However, the format of `copy.deepcopy`'s memo is well-known and used
    widely. (Plus, if you think this is naughty, don't even peek at the
    way `deepcopy` itself is extended by this module...)

    Arguments:
        original (Any): A value.
        replacement (Any): A value that should replace instances of
            `original` when calling `deepcopy` (even if calling
            `deepcopy` on objects which _reference_ `original`, directly
            or indirectly).
        memo (dict[int, Any]): A mapping of `id`s of original objects to
            replacement objects. This recursively includes attributes of
            `original`, if `replacement` provides an attribute with the
            same name. Optional.

    Returns:
        (dict[int, Any]): A mapping which, if passed to `copy.deepcopy`
        as the `memo` argument, will cause `original` to be replaced by
        `replacement` in the resulting copy.
    """
    # Avoid mutating default value:
    if memo is None:
        memo = {}
    # Don't recurse onto entities already in `memo`, to avoid infinite
    # recursion.
    elif id(original) in memo:
        return memo
    # deepcopy maps the id of the original object to a copied instance.
    # We want to replace the copied instance with `replacement`:
    memo[id(original)] = replacement

    # Recurse onto attributes of the original:
    # Some values are special (e.g. like ints). For instance, we
    # wouldn't necessarily want to replace every instance of `0` with
    # `1`. So we want to be careful when iterating over attributes.
    # `copy.deepcopy` handles this by avoiding memoization of certain
    # objects. We can leverage this by performing a test copy of
    # `original` and then, when iterating over attributes, recursing
    # only if the attribute is one that `deepcopy` copied (i.e. if it's
    # in the resulting memo).
    test_memo = {}
    _ = copy.deepcopy(original, memo=test_memo)
    for name in dir(original):
        attr = getattr(original, name)
        # Replace with the corresponding attribute of the replacement,
        # if it exists (and if this attr was copied by `deepcopy`)
        if id(attr) in test_memo and name in dir(replacement):
            memo.update(populate_memo(
                getattr(original, name), getattr(replacement, name)))
    return memo

# WARNING: Monkey-patch ahead!
# The `copy` module defines the copying behaviour for each datatype
# via the mapping `_deepcopy_dispatch`, a `dict[type, function]` (also
# referred to as `d` in the
# [source](https://github.com/python/cpython/blob/main/Lib/copy.py)).
# By default, `d[FunctionType] = _deepcopy_atomic`, which is the
# behaviour used for non-copied values (like ints).
# We can support copying of functions simply by setting the key
# `FunctionType` in `_deepcopy_dispatch` to point to a new function that
# creates copies of functions and calls `deepcopy` on closure variables.
# We define that function first:

def _deepcopy_function(func, memo):
    """ Returns a copy of function `func`.

    This function performs a deep copy of `func`'s closure, and thus
    can replace objects referenced in the closure if used in combination
    with `populate_deepcopy_memo`.

    Arguments and return values are the same as with `deepcopy`.
    """
    # If `func` has an empty closure, there's nothing to copy:
    if not hasattr(func, '__closure__') or not func.__closure__:
        return func

    # To avoid recursion (if a deeper object refers back to the function
    # being copied for some reason), we need to update `memo` with a
    # reference to the new function before we call `deepcopy` on any
    # closure variables.
    # So build a copy of the function now with a dummy closure (of the
    # correct length!). We can fill `closure` with copies later:
    closure = tuple(CellType(None) for _ in range(len(func.__closure__)))
    # Create a copy of the function:
    # See https://stackoverflow.com/a/13503277
    func_copy = FunctionType(
        func.__code__, func.__globals__,
        name=func.__name__, argdefs=func.__defaults__, closure=closure)
    func_copy = update_wrapper(func_copy, func)
    func_copy.__kwdefaults__ = func.__kwdefaults__
    # `update_wrapper` is a convenient way to copy `func`'s __module__,
    # __name__, __qualname__, __annotations__, and __doc__ attributes
    # (and to update its __dict__ attribute), but it also adds a new
    # attribute __wrapped__ which references `func`. `func_copy` doesn't
    # actually wrap `func`, and adding this attr can interfere with
    # equality checks or other comparisons, so delete it (or set it to
    # the same value as in `func`, if it has this attribute.)
    if hasattr(func, '__wrapped__'):
        func_copy.__wrapped__ = func.__wrapped__
    else:
        del func_copy.__wrapped__
    # Memoize the new function to avoid infinite recursion:
    memo[id(func)] = func_copy
    # Now we can build a copy of `func`'s closure recursively:
    # Note that `closure` is a `tuple[cell]`; `cell` objects are mutable
    # (via the `cell_contents` attr), so mutate those rather than trying
    # to assign to `func_copy.__closure__` or mutating `closure`
    # (neither of which are possible, as they are immutable)
    for i, val in enumerate(func.__closure__):
        # pylint: disable=no-member
        # `func_copy` definitely has a closure; we built one above!
        func_copy.__closure__[i].cell_contents = copy.deepcopy(
            val.cell_contents, memo)
        # pylint: enable=no-member
    return func_copy

# Tell `copy.deepcopy` to copy functions using the above behaviour:
# pylint: disable=protected-access
# Yes, this is naughty. If it breaks, we may want to consider copying
# the implementation of `deepcopy` current as of 2021-11-14; see here:
# https://github.com/python/cpython/blob/e5894ca8fd05e6a6df1033025b9093b68baa718d/Lib/copy.py
# That code is part of the Python standard library and is covered by
# the Python Software Foundation License Version 2, which requires
# only basic documentation and a copyright notice.
copy._deepcopy_dispatch[FunctionType] = _deepcopy_function
# pylint: enable=protected-access

# Expose `deepcopy` method to client code:
deepcopy = copy.deepcopy

""" This module provides functions for copying and replacing objects. """

import copy
from functools import update_wrapper
from types import FunctionType, CellType

def populate_deepcopy_memo(original, replacement, memo=None):
    """ Returns a memo that uses `replacement` in place of `original`.

    This method depends on implementation details of `copy.deepcopy`.
    In particular, this only works if `copy.deepcopy` populates its
    `memo` arg with `{id(original): copy}` pairs, where `original` is
    the object being copied and `copy` is a copy of `original`.

    This is a bit naughty. `copy.deepcopy`'s documentation is clear that
    you should not do this:
        > The memo dictionary should be treated as an opaque object.
        > https://docs.python.org/3/library/copy.html
    However, the format of `copy.deepcopy`'s memo is well-known and is
    identical between python, CPython, and others.

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
    _ = deepcopy(original, memo=test_memo)
    for name in dir(original):
        attr = getattr(original, name)
        # Replace with the corresponding attribute of the replacement,
        # if it exists (and if this attr was copied by `deepcopy`)
        if id(attr) in test_memo and name in dir(replacement):
            memo.update(populate_deepcopy_memo(
                getattr(original, name), getattr(replacement, name)))
    return memo

def deepcopy(obj, memo=None, _memo_funcs=None):
    """ Extends `copy.deepcopy` to copy objects in function closures.

    This is primarily useful in conjunction with
    `populate_deepcopy_memo`, which allows one to use `copy.deepcopy`
    to _replace_ objects with substitutes while copying by providing
    a specially-constructed `memo` argument. This allows objects in
    closures to be replaced

    This function calls `_func_copy` if `obj` is a function, and calls
    `copy.deepcopy` otherwise. It then checks any newly-copied objects
    for function attributes with closures and, if it finds any, it
    recurses onto those.

    Arguments:
        obj (Any): An object to be copied.
        memo (dict[int, Any]): A mapping generated by `copy.deepcopy`.
            This is a mapping of object ids (for original objects) to
            copies of objects. Optional.
        _memo_funcs (dict[int, FunctionType]): An inverse mapping to
            `memo`, but just for functions. This maps ids of _copies_
            of functions to the original functions. Optional.

    Returns:
        (Any): A deep copy of `obj`.
    """
    # See #82: https://github.com/ChrisCScott/forecaster/issues/82
    if memo is None:
        memo = {}
    if _memo_funcs is None:
        _memo_funcs = {}
    # Avoid recursion on objects we've copied before:
    if id(obj) in memo:
        return memo[id(obj)]  # return copy of orignal item
    if id(obj) in _memo_funcs:
        return obj  # return copied items as-is
    # Store a copy of `memo` before mutating it so that we can iterate
    # over newly-added entries later:
    old_memo = dict(memo)
    # Use our custom function-copying method for functions
    # (This calls `copy.deepcopy` for any closured variables)
    if hasattr(obj, '__closure__') and obj.__closure__:
        obj_copy = _func_copy(obj, memo=memo, _memo_funcs=_memo_funcs)
    else:
        obj_copy = copy.deepcopy(obj, memo=memo)
    # We're not done. `copy.deepcopy` recurses over attributes and
    # copies them, but ignores functions. So we need to check copied
    # objects for function attributes that need copying:
    new_keys = memo.keys() - old_memo.keys()
    for key in new_keys:
        val = memo[key]
        for name in dir(val):
            attr = getattr(val, name)
            if isinstance(attr, FunctionType):
                # `deepcopy` only copies if we haven't copied already:
                attr_copy = deepcopy(attr, memo=memo, _memo_funcs=_memo_funcs)
                # If `deepcopy` returned a new copy, assign it to the attr:
                if id(attr) != id(attr_copy):
                    setattr(val, name, attr_copy)
    return obj_copy

def _func_copy(func, memo=None, _memo_funcs=None):
    """ Returns a copy of function `func`.

    This function performs a deep copy of `func`'s closure, and thus
    can replace objects referenced in the closure if used in combination
    with `populate_deepcopy_memo`.

    Arguments and return values are the same as with `deepcopy`.
    """
    # If `func` has an empty closure, there's nothing to copy:
    if not hasattr(func, '__closure__') or not func.__closure__:
        return func

    # Avoid mutating default values:
    if memo is None:
        memo = {}
    if _memo_funcs is None:
        _memo_funcs = {}

    # Before building a copy of `func`, we need to copy its closure (so
    # it can be provided to the copy of `func` at init; the __closure__
    # attribute is immutable).
    # Note that `__closure__` is a `tuple[cell]`. `deepcopy` does not
    # support `cell`, so we need to copy the contents of each cell and
    # wrap them in new cells:
    closure = tuple(CellType(
        # Call our custom `deepcopy`, which will handle any functions
        # referenced by closure vars correctly (by calling _func_copy):
        deepcopy(cell.cell_contents, memo=memo, _memo_funcs=_memo_funcs))
        for cell in func.__closure__)
    # Create a copy of the function:
    # See https://stackoverflow.com/a/13503277
    func_copy = FunctionType(
        func.__code__, func.__globals__,
        name=func.__name__, argdefs=func.__defaults__, closure=closure)
    func_copy = update_wrapper(func_copy, func)
    func_copy.__kwdefaults__ = func.__kwdefaults__
    # Memoize `func` and `func_copy` to avoid infinite recursion:
    memo[id(func)] = func_copy
    _memo_funcs[id(func_copy)] = func
    return func_copy

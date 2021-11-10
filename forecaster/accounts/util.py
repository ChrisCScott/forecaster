""" Helper classes and methods for Account. """

import math
from collections import namedtuple
from forecaster.utility import when_conv


FIELDS = ['min_inflow', 'max_inflow', 'min_outflow', 'max_outflow']
LimitTuple = namedtuple(
    'LimitTuple', FIELDS, defaults=(None,) * len(FIELDS))
LimitTuple.__doc__ = (
    "A data container holding different values for min/max inflow/outfow")
IDENTITY_FUNCTION = lambda x: x

# Give an easy way for refactors to update references to LimitTuples:
LIMIT_TUPLE_FIELDS = LimitTuple(*FIELDS)


def accumulation_function(t, rate, nper=1, high_precision=None):
    """ The accumulation function, A(t), from interest theory.

    A(t) provides the growth (or discount) factor over the period
    [0, t]. If `t` is negative, this method returns the inverse
    (i.e. `A(t)^-1`).

    This method's output is not well-defined if `t` does not align
    with the start/end of a compounding period. (It will produce
    sensible output, but it might not correspond to how your bank
    calculates interest).

    Args:
        t (float, Decimal): Defines the period [0,t] over which the
            accumulation will be calculated.
        rate (float, Decimal): The rate of return (or interest).
        nper (int): The number of compounding periods per year.
            Optional. If not provided, defaults to 1 - i.e. annual
            compounding.
        high_precision (Callable[[float], T]): A method that converts
            `float` inputs to a high-precision type `T` (e.g. Decimal).
            Optional.

    Returns:
        The accumulation A(t), as a Decimal.
    """
    # pylint: disable=invalid-name
    # `t` is the usual name for the input to A(t) in interest theory.

    # If using high-precision numerical types, convert inputs here:
    if high_precision is not None:
        one = high_precision(1)
        # nper can be default-valued to a float, so convert that too:
        if nper is 1:
            nper = one
    else:
        one = 1

    # Use the exponential formula for continuous compounding: e^rt
    if nper is None:
        # Need to convert e to high-precision
        # TODO: consider using Decimal.exp when appropriate.
        # (Prefer to do this without importing decimal.)
        if high_precision is not None:
            exp = high_precision(math.e)
        else:
            exp = math.e
        acc = exp ** (rate * t)
    # Otherwise use the discrete formula: (1+r/n)^nt
    else:
        acc = (one + rate / nper) ** (nper * t)

    return acc

def accumulation_function_inverse(accum, rate, nper=1, high_precision=None):
    """ The inverse of the accumulation function, A^-1(a).

    A^-1(a) provides the amount of time required to achieve a
    certain growth (or discount) factor. If `accum` is less than
    1, the result is negative. `accum` must be positive.

    Args:
        accum (float, Decimal): The accumulation factor.
        rate (float, Decimal): The rate of return (or interest).
        nper (int): The number of compounding periods per year.

    Returns:
        (float, Decimal): A value `t` defining the period [0,t]
            or [t, 0] (if negative) over which the accumulation
            would be reached.
    """
    # NOTE: If using high-precision numerical classes (like Decimal),
    # convert `accum` and `rate` here

    if accum < 0:
        raise ValueError('accum must be positive.')

    if high_precision is None:
        high_precision = IDENTITY_FUNCTION

    # The case where rate=0 results in divide-by-zero errors later
    # on, so deal with it specifically here.
    # If the rate is 0%, it will either take an infinite value
    # (positive or negative, depending on the rate)
    # or 0 (in the special case of accum=1)
    if rate == 0:
        if accum == 1:
            return high_precision(0)
        elif accum < 1:
            return high_precision(float('-inf'))
        else:
            return high_precision(float('inf'))

    # Use the exponential formula for continuous compounding: a=e^rt
    # Derive from this t=ln(a)/r
    if nper is None:
        # math.exp(rate * t) throws a warning, since there's an
        # implicit float-Decimal multiplication.
        timing = math.log(accum, high_precision(math.e)) / rate
    # Otherwise use the discrete formula: a=(1+r/n)^nt
    # Derive from this t=log(a,1+r/n)/n
    else:
        timing = math.log(accum, high_precision(1) + rate / nper) / nper

    return timing

def value_at_time(
        value, rate, now='start', time='end', nper=1, high_precision=None):
    """ Returns the present (or future) value.

    Args:
        value (Money): The (nominal) value to be converted.
        rate (Decimal): The rate of growth (e.g. inflation)
        now (Decimal): The time associated with the nominal value,
            expressed using `when_conv` syntax.
        time (Decimal): The time to which the nominal value is to
            be converted, expressed using `when_conv` syntax.
        nper (Decimal): The number of compounding periods for growth.

    Returns:
        A Money object representing the present value
        (if now > time) or the future value (if now < time) of
        `value`.
    """
    return value * accumulation_function(
        when_conv(
            time, high_precision=high_precision
        ) - when_conv(now, high_precision=high_precision),
        rate, nper,
        high_precision=high_precision)


def time_to_value(rate, value_now, value_then, nper=1, high_precision=None):
    """ The time required to grow from one value to another.

    Args:
        rate (Decimal): The rate of growth (e.g. inflation)
        value_now (Money): The (nominal) value we start with.
        value_then (Money): The (nominal) value we end with.
        nper (Decimal): The number of compounding periods for growth.

    Returns:
        A Decimal object representing the time required to
        grow (or shrink) from `value_now` to `value_then`.
    """
    return accumulation_function_inverse(
        accum=value_then/value_now, rate=rate, nper=nper,
        high_precision=high_precision)

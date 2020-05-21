""" A module with free methods and extensions to third-party classes.

Used throughout the application, without any dependency on any other
modules.
"""

import collections
from numbers import Number
from typing import Union, Dict, Optional, Iterable, Any
from forecaster.typing import Money, Real


# `when` values can take any (real-valued) numeric value, as well as
# specific string values. This gets used a lot, so define the type here.
Time = Union[Real, str]

# String codes describing points in time, mapped to numeric values:
WHEN_STRS: Dict[str, Real] = {
    'start': 0,
    'end': 1
}

# String codes describing frequencies (e.g. annual, bimonthly)
# mapped to ints giving the number of such periods in a year:
FREQUENCY_STRS: Dict[str, Optional[int]] = {
    'C': None,
    'D': 365,
    'W': 52,
    'BW': 26,
    'SM': 24,
    'M': 12,
    'BM': 6,
    'Q': 4,
    'SA': 2,
    'A': 1
}

# Define constants for use throughout `forecaster` packages:
EPSILON: Real = 0.5**13  # Roughly 0.000122. Should be losslessly represented.
WHEN_DEFAULT: Time = 0.5

class Timing(dict):
    """ A dict of {timing: weight} pairs.

    This is really just a vanilla dict with a convenient init method.
    It divides the interval [0,1] into a number of equal-length periods
    equal to `frequency` and, within each period, assigns a timing at
    `when`. The timings are equally-weighted.

    This class only accepts discrete frequencies. Providing a continuous
    frequency will result in an error.

    This class can be initialized as follows:
    * No args: Produces empty dict
    * One arg, a dict (e.g. a Timing object): Copy-constructor. If the
      dict has non-numeric values (e.g. non-numeric Money type), these
      are converted to numeric values to avoid arithmetic errors.
    * One arg, a str-value interpretable as a frequency: The arg is
      interpreted as a frequency. Each period receives a timing based on
      `WHEN_DEFAULT`.
    * One arg, otherwise: Interprets the input as a `when` value and
      thus produces a dict with one key.
    * Two args: Interprets the inputs as `when` and `frequency`.

    In general, the type of values will be `float` unless a
    copy-constructor is used, in which case the type will be based on
    the types of values in the input dict (e.g. numeric types are
    preserved, non-numeric Money types are converted to Numeric.)

    Examples:
        Timing()  # 0-ary
        # {}
        Timing('SA')  # 1-ary with valid frequency string
        # {0.25: 0.5, 0.75: 05}
        Timing(0.5)  # 1-ary otherwise
        # {0.5: 1}
        Timing(when=1, frequency=4)  # 2-ary
        # {0.25: 0.25, 0.5: 0.25, 0.75: 0.25, 1: 0.25}
        Timing(when=0, frequency=4)
        # {0: 0.25, 0.25: 0.25, 0.5: 0.25, 0.75: 0.25}
        Timing(when=0.5, frequency=2)
        # {0.25: 0.5, 0.75: 0.5}

    Args:
        when (Real, str): When transactions occur in each period (e.g.
            'start', 'end', 0.5). Uses the same syntax as
            `forecaster.utility.when_conv`. Optional.
        frequency (Real, str): The number of periods (and thus the
            number of transactions). Uses the same syntax as
            `forecaster.utility.frequency_conv`. Optional.
    """
    def __init__(
            self, when: Optional[Union[
                Time, # Standard call signature, receiving a when value
                Dict[Real, Any], # 1-ary copy constructor
                str, # 1-ary frequency string
            ]]=None,
            frequency: Optional[Union[Real, str]] = None
        ) -> None:
        """ Initializes a Timing dict. """
        # We allow four forms of init call:
        # 1) Init with two arguments: `when` and `frequency`
        # 2) Init with dict of {when: value} pairs (e.g. `Timing(d)`
        #    where d is a dict)
        # 3) Init with string denoting a frequency (e.g. `Timing('BW')`)
        # 4) Init with `when`-convertible value (e.g. Timing('start'),
        #    `Timing(1)`)

        # Set up the object by getting an empty dict:
        super().__init__()

        # First, deal with 0-ary construction:
        if when is None and frequency is None:
            return
        # If frequency was provided but when wasn't, use default value:
        elif when is None:
            when = WHEN_DEFAULT

        # Deal with 1-ary init.
        if frequency is None:
            # First deal with copy constructor. There are two cases:
            # 1: the input is already Timing. No more processing needed.
            if isinstance(when, Timing):
                self.update(when)
                return
            # 2: the input is a dict. We want to be able to receive
            # time-series data of transactions. Values may be
            # non-numeric or negative, so some processing is needed.
            elif isinstance(when, dict):
                self.update(_convert_dict(when))
                return
            # Next, deal with case where a string interpretable as a
            # frequency is passed:
            elif isinstance(when, str) and when in FREQUENCY_STRS:
                # Simple to deal with; use the input as `frequency` and
                # use the default value for `when`, then fall through
                # to the regular 2-ary case:
                frequency = when
                when = WHEN_DEFAULT  # default value

        # Now deal with 2-ary case:
        # First, catch the case where `frequency` was passed with
        # dict-type `when`:
        if isinstance(when, dict):
            raise ValueError('frequency cannot be used with copy-constructor')

        # Next, convert arguments to numeric type if necessary:
        when = when_conv(when)
        frequency = frequency_conv(frequency)

        # Some str codings convert to None, so test for that here:
        if frequency is None:  # Continuous frequency provided.
            raise ValueError('Frequency must be non-continuous.')

        # Build out multiple timings based on scalar inputs.
        # Each transaction has equal weight:
        weight: float = 1 / frequency
        # Build the dict:
        for time in range(frequency):
            self[(time + when) / frequency] = weight

    def _normalized(
            self, keys: Optional[Iterable[Real]] = None
        ) -> Dict[Real, Real]:
        """ Returns a normalized dict based on this `Timing` object.

        This method is just a convenience for other class methods which
        need to get a normalized dict quickly but don't need to wrap the
        result in a `Timing` object.

        Args:
            keys (Iterable[Real]): A subset of the keys of the
                `Timing` object. If provided, the result contains only
                the keys in `keys` and the normalization is applied only
                to those keys. Optional.

        Returns:
            dict[Real, Real]: A normalized dict with values
            proportional to those of this `Timing` object (or to the
            subset indicated by `keys`).

        Raises:
            KeyError: Element of `keys` not in `self`.
        """
        if keys is None:
            keys = self.keys()
        # Simply scale down each value by the sum of all values:
        normalization: Real = sum(self[key] for key in keys)
        return {key: self[key] / normalization for key in keys}

    def normalized(
            self, keys: Optional[Iterable[Real]] = None
        ) -> Timing:
        """ Returns a normalized version of the `Timing` object.

        'Normalized' here means that the values sum to 1.

        Args:
            keys (Iterable[Number]): A subset of the keys of the
                `Timing` object. If provided, the result contains only
                the keys in `keys` and the normalization is applied only
                to those keys. Optional.

        Raises:
            KeyError: Element of `keys` not in `self`.

        Returns:
            Timing: A `Timing` object with values that sum to 1 and
            which are proportional to those of this `Timing` object (or
            to the subset indicated by `keys`).
        """
        return Timing(self._normalized(keys))

    def time_series(
            self, scalar: Union[Money, Real],
            keys: Optional[Iterable[Real]] = None
        ) -> Dict[Real, Union[Money, Real]]:
        """ Scales `scalar` into portions proportionate to this timing.

        This method essentially performs scalar multiplication, where
        `scalar` is the scalar value and `self` is the (normed) vector.
        The result is a time-series that has the same proportions as
        `self` and sums to `scalar`.

        Args:
            scalar (Union[Real, Money]): Any scalar value that supports
                multiplication against the values of `Timing`.
            keys (Iterable[Real]): Key values for timings.
                See `Timing.normalized` for more. Optional.

        Returns:
            dict[Real, Union[Money, Real]]: A time-series of values with
                the same proportions as this timing object, with values
                of the same type as `scalar` and which sum to `other`.

        Raises:
            ValueError: `scalar` does not support multiplication by the
            values of this timing object.
        """
        # We get a dict of Real values here, but we'll mutate later
        # and may potentially introduce Money-typed values
        # (if scalar is Money-typed):
        normalized: Dict[Real, Union[Real, Money]] = (
            self._normalized(keys=keys)) # type: ignore[assignment]
        # Scale `scalar` by the normalized weight of each value of this
        # `Timing` object. This effectively splits `scalar` up into
        # smaller amounts for each key in `self` proportionately to the
        # (normalized) values of `self`.
        for key in normalized:
            # Leave it to calling code to provide compatibly-typed
            # `scalar` (i.e. should be compatible with values of `self`)
            normalized[key] *= scalar  # type: ignore[operator]
        return normalized

def _convert_dict(when: Dict[Real, Union[Money, Real]]) -> Dict[Real, Real]:
    """ Converts `dict` input to `Timing`-style `when: weight` pairs.

    If all values are positive, the dict is returned unchanged. If they
    are all negative, they're flipped to positive and returned. (This
    excludes 0-values, so technically "non-negative" and "non-positive"
    are the correct terms.)

    If there are both positive and negative values, `when` is assumed
    to be a dict of transactions. If total flows are positive, this
    method returns a mapping of timings to the largest amount at each
    timing that can be withdrawn without causing the net flows at that
    timing or any later timing to be negative. If the total flows are
    negative, the method returns a mapping of timings to the smallest
    amount that must be added to bring the net flows to zero balance
    (without bringing the net transactions to positive balance).

    Args:
        when (dict[Real, Union[Money, Real]]): A mapping of timings
            (in [0,1]) to values.
            If the values are `Money`-typed, they are converted to
            a numerical type.

    Returns:
        dict[Real, Real]: A mapping of timings to weights.
    """
    # First, deal with empty dict or all-zero dict:
    if not when:
        # This dict has no meaningful timings, so return empty dict.
        return {}
    if all(value == 0 for value in when.values()):
        # Use the timings provided by the dict and fill in uniform
        # weights, since no non-zero weights were given:
        return {key: 1 for key in when}

    # If values are Money-like, convert to numerical type:
    when_out: Dict[Real, Real]
    if all(hasattr(value, 'amount') for value in when.values()):
        # Convert the dict's values to Decimal (no mutation!):
        when_out = {
            # We know from the above test that `amount` is an attribute:
            timing: value.amount # type: ignore[union-attr]
            for timing, value in when.items()}
    # If values not Money-like, then they should all be numeric:
    elif any(not isinstance(value, Number) for value in when.values()):
        raise TypeError("Money value not convertible to numeric type")
    # If we don't trigger the above checks, then all values are numeric:
    else:
        when_out = when  # type: ignore[assignment]

    # OK, so the dict is non-empty, has a non-zero element, and
    # has only numeric values. The only remaining issue is sign.
    # If there are no negative values, the dict is useable as-is:
    if all(value >= 0 for value in when_out.values()):  # type: ignore[operator]
        return when_out
    # If all items are negative, flip the signs:
    elif all(value <= 0 for value in when_out.values()):
        return {time: -value for time, value in when_out.items()}

    # If the dict has a mix of positive and negative values, treat
    # it like an `available` dict of transactions. Use the
    # timings for inflows if the total is positive and outflows if
    # the total is negative (this way we reinforce inflows/outflows)
    total = sum(when_out.values())
    # First, deal with the case where the total is zero:
    if total == 0:
        # If the time-series is perfectly balanced between positive and
        # negative, no transactions are needed to bring the time-series
        # to balance, so return a time-series with no transactions:
        return {}
    elif total > 0:  # type: ignore[operator]
        return _accum_inflows(when_out)
    else:
        return _accum_outflows(when_out)

def _accum_inflows(when):
    """ Determines maximum withdrawable amount for each timing.

    This method receives an input (`when`) with a mix of inflows and
    outflows which sum up to a net inflow. It then determines, for each
    timing in `when`, the largest amount that can be withdrawn at that
    timing without causing the balance of transactions to go negative
    (or, at least, any more negative than it already is) at any point in
    time. The value for each timing assumes that all withdrawals for
    previous timings have been made.

    A simpler way to think about this: This is the time-series of
    outflows which, when added to `when`, zeroes out the net
    transactions by the end of the period and makes each outflow
    as large and as early as possible while only using money that's
    available (i.e. no overdraft/credit).

    Example:
        when = {0: 10, 0.5: -5, 1: 5}
        outflows = _accum_inflows(when)
        # outflows == {0: 5, 1: 5}

    Args:
        when (dict[Number, Union[Money, Number]]): A mapping of timings
            (in [0,1]) to values. The values must sum to a positive
            value. If the values are `Money`-typed, they are converted
            to `Decimal`.

    Returns:
        dict[Decimal, Number]: A mapping of timings to weights.
    """
    # We do this in two stages.
    # First, for each timing, determine the cumulative value of
    # all transactions to date and store it in `accum`:
    accum = {}
    result = {}
    tally = 0  # sum of transactions so far
    for timing in sorted(when.keys()):
        tally += when[timing]
        accum[timing] = tally
    # Second, iterate over the timings *again*, this time
    # determining for each timing the maximum amount that can be
    # withdrawn without changing the sign of any future timing:
    tally = 0  # amounts withdrawn so far
    for timing in sorted(when.keys()):
        # Find the bottleneck: the future value with the
        # smallest cumulative amount determines the maximum
        # transaction we can make right now:
        max_transaction = min(
            value for key, value in accum.items() if key >= timing)
        # Only record timings with positive sign:
        if max_transaction > 0:
            result[timing] = max_transaction
            # Update loop variables to reflect that a transaction
            # has been added: all future timings in accum should be
            # modified accordingly.
            tally += max_transaction
            for key in accum:
                if key >= timing:
                    accum[key] -= max_transaction
    return result

def _accum_outflows(when):
    """ Determines minimum necessary contribution for each timing.

    This method receives an input (`when`) with a mix of inflows and
    outflows which sum up to a net outflow. It then determines, for each
    timing in `when`, the smallest amount that must be contributed at
    that timing to bring the rolling total to zero balance.
    The value for each timing assumes that all contributions for
    previous timings have been made.

    Note that, unlike `_accum_inflows`, this method does not guarantee
    that the total net flows will be zero. Rather, the resulting time
    series merely avoids a negative balance at any point in time.

    Example:
        when = {0: -10, 0.5: -5, 1: 5}
        inflows = _accum_outflows(when)
        # inflows == {0: 10, 0.5: 5}

    Args:
        when (dict[Number, Union[Money, Number]]): A mapping of timings
            (in [0,1]) to values. The values must sum to a negative
            value. If the values are `Money`-typed, they are converted
            to `Decimal`.

    Returns:
        dict[Decimal, Number]: A mapping of timings to weights.
    """
    # Accumulate the various transactions in order. Every time the
    # rolling accumulation dips negative, record an inflow that brings
    # it back to 0:
    accum = 0
    result = {}
    for timing in sorted(when.keys()):
        accum += when[timing]
        if accum < 0:
            result[timing] = -accum
            accum = 0
    return result

def transactions_from_timing(timing, total):
    """ Generates a schedule of transactions based on a timing and total

    Args:
        timing (Timing): The timing of the transactions, each with a
            corresponding weight.
        total (Money): The sum of all transactions to be generated.

    Returns:
        dict[Decimal, Money]: A schedule of transactions, each
        transaction having the relative weighting provided by `timing`
        and the total value of the transactions summing to `total`.
    """
    if not isinstance(timing, Timing):
        timing = Timing(timing)
    normalization = sum(timing.values())
    transactions = {
        time: total * (weight / normalization)
        for time, weight in timing.items()}
    return transactions

def when_conv(when: Time) -> Real:
    """ Converts various types of `when` inputs to numeric values.

    The numeric value is in [0,1], where 0 is the start of the period
    and 1 is the end.

    NOTE: `numpy` defines its `when` argument such that 'end' = 0 and
    'start' = 1. If you're using that package, consider whether any
    conversions are necessary.

    Args:
        `when` (Real, str): The timing of the transaction.
            Must be in the range [0,1] or in ('start', 'end').

    Raises:
        ValueError: `when` must be either 'start' or 'end'.
        ValueError: `when` must be in [0,1]

    Returns:
        A Decimal in [0,1]
    """
    # Attempt to convert strings 'start' and 'end' first
    if isinstance(when, str):
        if when == 'end':
            when = 1
        elif when == 'start':
            when = 0
        else:
            raise ValueError('`when` must be either \'start\' or \'end\'.')

    # Any str-valued `when` input was dealt with above. It is Real now.
    # For some reason mypy insists that < is not supported for Real and
    # int operands, but it ought to be.
    if when > 1 or when < 0:  # type: ignore[operator]
        raise ValueError("When: 'when' must be in [0,1]")

    return when

def frequency_conv(nper: Optional[Union[Real, str]]) -> Optional[int]:
    """ Number of periods in a year given a compounding frequency.

    Args:
        nper (str, Real): A code (str) indicating a compounding
            frequency (e.g. 'W', 'M'), an integer-valued numeric value,
            or None.

    Returns:
        An int indicating the number of compounding periods in a year,
        or None if compounding is continuous.

    Raises:
        ValueError: str nper must have a known value.
        ValueError: nper must be greater than 0.
        ValueError: nper must have an integer value.
    """
    # nper can be None, so return gracefully.
    if nper is None:
        return None

    # Try to parse a string based on known compounding frequencies
    if isinstance(nper, str):
        if nper not in FREQUENCY_STRS:
            raise ValueError('Account: str nper must have a known value')
        return FREQUENCY_STRS[nper]
    # For numeric types, ensure that it's a positive integer:
    else:
        if not nper == int(nper):  # type: ignore[arg-type]
            raise ValueError(
                'Account: nper is not losslessly convertible to int')
        if nper <= 0:
            raise ValueError('Account: nper must be greater than 0')
        # After the above tests, the value should be convertible to int:
        return int(nper)  # type: ignore[arg-type]

def add_transactions(base, added):
    """ Combines the values of two dicts, summing values of shared keys.

    This method mutates its first argument (base). If you don't want
    that behaviour, copy your input dict before calling this method.

    Example:
        d1 = {1: 1, 2: 2}
        d2 = {2: 2, 3: 3}
        add_transactions(d1, d2)
        // d1 == {1: 1, 2: 4, 3: 3}

    Args:
        base [dict[Any, Any]]: A dictionary, generally of transactions
            (i.e. `Decimal: Money` pairs), but potentially of any types.
            Mutated by this method.
        added [dict[Any, Any]]: A dictionary whose values support
            addition (via `+` operator) with the same-key values of
            `base`. Not mutated by this method.

    Returns:
        None. Input `base` is mutated instead.
    """
    for key, value in added.items():
        # Sum values if the key is in both inputs, insert otherwise:
        if key in base:
            base[key] += value
        else:
            base[key] = value

def subtract_transactions(base, added):
    """ Combines values of two dicts, subtracting values of shared keys.

    This method mutates its first argument (base). If you don't want
    that behaviour, copy your input dict before calling this method.

    The semantics of this method are the same as `add_transactions`,
    except that the values of `added` are subtracted from those of
    `base`. A consequence of this is that, unlike `add_transactions`,
    `subtract_transactions` is not commutative.

    Args:
        base [dict[Any, Any]]: A dictionary, generally of transactions
            (i.e. `Decimal: Money` pairs), but potentially of any types.
            Mutated by this method.
        added [dict[Any, Any]]: A dictionary whose values support
            addition (via `+` operator) with the same-key values of
            `base`. Not mutated by this method.

    Returns:
        None. Input `base` is mutated instead.
    """
    for key, value in added.items():
        # Sum values if the key is in both inputs, insert otherwise:
        if key in base:
            base[key] -= value
        else:
            base[key] = -value

def nearest_year(vals, year):
    """ Finds the nearest (past) year to `year` in `vals`.

    This is a companion method to `inflation_adjust()`. It's meant to be
    used when you want to pull a value out of an incomplete dict without
    inflation-adjusting it (e.g. when you want to grab the most recent
    percentage rate from a dict of `{year: Decimal}` pairs.)

    If `year` is in `vals`, then this method returns `year`.
    If not, then this method tries to find the last year
    before `year` that is in `vals`. If that doesn't work, then this
    method tries to find the first year in `vals` following `year`.

    Returns:
        A year in `vals` is near to `year`, preferring
        the nearest preceding year (if it exists) over the nearest
        following year.

        Returns `None` if `vals` is empty.
    """
    if vals == {}:
        return None

    # If the year is explicitly represented, no need to inflation-adjust
    if year in vals:
        return year

    # Look for the most recent year prior to `year` that's in vals
    key = max((k for k in vals if k < year), default=None)

    # If that didn't work, look for the closest following year.
    if key is None:
        key = min((k for k in vals if k > year), default=None)

    return key


def extend_inflation_adjusted(vals, inflation_adjust, target_year):
    """ Fills in partial time-series with inflation-adjusted values.

    This method is targeted at inflation-adjusting input data (e.g.
    as found in the Constants module), which tends to be incomplete
    and can represent non-sequential years. New years are often entered
    when something changes (i.e. when values change in real terms), so
    this method prefers to infer inflation-adjusted values based on the
    most recent *past* years when possible (since future years might
    not be comparable).

    If `target_year` is in `vals`, then this method returns the value
    for `target_year` in `vals` without further inflation-adjusting
    (as that value is already in nominal terms).

    If `target_year` is not in `vals`, then this method attempts to
    interpolate an inflation-adjusted value based on the last year in
    `vals` before `target_year` or, if no such year exists, based on the
    first year in `vals` after `target_year`.

    If the values of `vals` are dicts or other iterable, this method
    returns a dict or other iterable with values that have each been
    inflation-adjusted.

    Args:
        vals (dict): A dict of `{year: val}` pairs, where `val` is a
            scalar, list, or dict. This dict may be incomplete, in the
            sense that some years may not be represented.

            If `val` is non-scalar, an object of the same type is
            returned with each of its values inflation-adjusted.
        inflation_adjust: A method of the form
            `inflation_adjust(val, this_year, target_year)` that finds a
            nominal value in `target_year` with the same real value as
            nominal value `val` in `this_year`.
        year (int): The year for which an adjusted value is to be
            generated.
    """
    # If the year is explicitly represented, no need to inflation-adjust
    if target_year in vals:
        return vals[target_year]

    # Look for the most recent year prior to `year`
    base_year = nearest_year(vals, target_year)

    # If one of the above searches worked, return an inflation-adjusted
    # value (or dict/list of values, depending on what the values of
    # `vals` are)
    if base_year != target_year:
        val = vals[base_year]
        if isinstance(val, dict):
            return {
                k: val[k] * inflation_adjust(target_year, base_year)
                for k in val
            }
        elif isinstance(val, collections.abc.Iterable):
            return type(val)(
                v * inflation_adjust(target_year, base_year) for v in val
            )
        else:
            return val * inflation_adjust(target_year, base_year)
    # If none of the above searches for a year worked, raise an error.
    else:
        raise ValueError('inflation_adjust: No year is in both vals and ' +
                         'inflation_adjustment')


def build_inflation_adjust(inflation_adjust=None):
    """ Generates an inflation_adjust method.

    If inflation_adjust is not provided, all values are assumed to be in
    real terms, the returned method will return its argument `val`
    without inflation adjustment.

    Args:
        inflation_adjust: May be a dict of {year: inflation_adjustment}
            pairs, where `inflation_adjustment` is a Decimal that
            indicates a cumulative year-over-year inflation factor.
            Or may be a method (returned as-is). Optional.

    Returns:
        A method with the following form:
        `inflation_adjust(val, this_year, target_year)`.

        The method returns a Money object (assuming Money-typed `val`
        input).

        Finds a nominal value in `target_year` with the same real
        value as `val`, a nominal value in `this_year`.
    """
    # Use a default value
    if inflation_adjust is None:
        # Assume real values if no inflation-adjustment method is
        # given - i.e. always return val without adjustment.
        # pylint: disable=W0613,E0102
        def inflation_adjust_func(target_year, base_year=None):
            """ No inflation adjustment; returns 1 every year. """
            return 1
    elif isinstance(inflation_adjust, dict):
        # If a dict of {year: Decimal} values has been passed in,
        # convert that to a suitable method.

        # It's slightly more efficient to find the smallest key in
        # inflation_adjust outside of the function.
        default_base = min(inflation_adjust.keys())

        def inflation_adjust_func(target_year, base_year=None):
            """ Inflation adjustment from """
            if base_year is None:
                base_year = default_base
            return inflation_adjust[target_year] / inflation_adjust[base_year]
    elif not callable(inflation_adjust):
        # If it's not a dict and not callable, then we don't know
        # what to do with it. Raise an error.
        raise TypeError('RegisteredAccount: inflation_adjust must be ' +
                        'callable.')
    else:
        # inflation_adjust is callable, so just use that!
        inflation_adjust_func = inflation_adjust

    return inflation_adjust_func

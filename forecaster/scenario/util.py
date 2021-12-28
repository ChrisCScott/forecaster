""" Utility methods for `forecaster.scenario`. """

from bisect import bisect_left
from typing import Sequence, Mapping
from itertools import pairwise, takewhile, count
from functools import reduce
from statistics import mode, StatisticsError
from collections import OrderedDict
from dateutil.relativedelta import relativedelta

DATES_INTERVAL_SAMPLES = 100

def interpolate_value(values, date, high_precision=None):
    """ Determines a portfolio value on `date` based on nearby dates.

    This method is aimed at sequences like
    `{datetime(2000,1,1): 100, datetime(2002,1,1): 300}`
    where it would be sensible to interpolate a value of `200` for
    `datetime(2001,1,1)` because each value is absolute and is not
    expressed relative to preceding values.

    If values in `values` are relative, such as rates of return
    expressed in percentage terms, then use `return_over_period`.

    Arguments:
        values (OrderedDict[datetime, HighPrecisionOptional]): A mapping
            of dates to absolute values, e.g. portfolio values.
        date (datetime): A date within the range represented by the keys
            of `values` (i.e. no earlier than the earliest key-date and
            no later than the latest key-date). `date` does not need to
            be (and usually isn't) a key in `values`.
        high_precision (Callable[[float], HighPrecisionType] | None): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Returns:
        (HighPrecisionOptional): A value at `date`. If `date` is not
        in `values`, this is the *weighted average* of the values
        nearest in time to `date` (before and after).

    Raises:
        (KeyError): `date` is out of range.
    """
    # Deal with array-style inputs:
    if isinstance(values, (tuple, list)):
        return _interpolate_value_array(
            *values, date, high_precision=high_precision)
    # Check to see if the date is available exactly:
    if date in values:
        return values[date]
    if not min(values) <= date <= max(values):
        raise KeyError(str(date) + ' is out of range.')
    # Get the dates on either side of `date`:
    dates = list(values)
    index = bisect_left(dates, date)
    prev_date = dates[index-1]
    next_date = dates[index]
    # Find out how much the portfolio grew between prev_date and date:
    returns = {prev_date: 0, next_date: values[next_date] / values[prev_date]}
    growth = return_over_period(
        returns, prev_date, date, high_precision=high_precision)
    # Apply that growth and voila: the new portfolio value
    return values[prev_date] * (growth + 1)

def _interpolate_value_array(dates, values, date, high_precision=None):
    """ Array-based companion to `interpolate_value` """
    index = bisect_left(dates, date)
    # Check to see if the date is available exactly:
    if dates[index] == date:
        return values[index]
    # Check to see if the date is outside the range of `dates`:
    if not get_first_date(dates) <= date <= get_last_date(dates):
        raise KeyError(str(date) + ' is out of range.')
    # This date is between other dates.
    # Get the dates on either side of `date`:
    prev_date = dates[index-1]
    prev_value = values[index-1]
    next_date = dates[index]
    next_value = values[index]
    # Find out how much the portfolio grew between prev_date and date
    # based on the returns-based logic of `return_over_period`.
    # To do that, we need to provide an array of _returns_, not
    # portfolio values, so build a simple one with just the key dates:
    growth = _return_over_period_array(
        [prev_date, next_date],
        [0, next_value / prev_value],
        prev_date, date, high_precision=high_precision)
    # Apply that growth and voila: the new portfolio value
    return prev_value * (growth + 1)

def return_over_period(
        returns, start_date, end_date,
        dates_interval=None, high_precision=None):
    """ Determines the total return between `start_date` and `end_date`.

    Arguments:
        returns (OrderedDict[datetime, HighPrecisionOptional]): A
            mapping of dates to relative values, e.g. rates of return.
        start_date (datetime): A date within the range represented by
            the keys of `returns` (i.e. no earlier than the earliest
            key-date and no later than the latest key-date). `date` does
            not need to be a key in `returns`.
        end_date (datetime): A date within the range represented by
            the keys of `returns` (i.e. no earlier than the earliest
            key-date and no later than the latest key-date). `date` does
            not need to be a key in `returns`.
        dates_interval (relativedelta | timedelta): The period covered
            by the first date in `dates`. Optional. Will be inferred if
            not provided; see `_infer_interval`.
        high_precision (Callable[[float], HighPrecisionType] | None): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Returns:
        (HighPrecisionOptional): The total return between `start_date`
        and `end_date`. If `start_date` and `end_date` are not in
        `returns`, returns are interpolated for them via
        `interpolate_returns`.

    Raises:
        (KeyError): `date` is out of range.
    """
    # Deal with array-style inputs:
    if isinstance(returns, (tuple, list)):
        return _return_over_period_array(
            *returns, start_date, end_date, dates_interval=dates_interval,
            high_precision=high_precision)
    # Get all dates between start_date and end_date:
    dates = [date for date in returns if start_date < date < end_date]
    # Recurse if there are any dates between `start_date` and `end_date`
    if dates:
        # Insert start and end dates so we recurse over them too:
        dates.insert(0, start_date)
        dates.append(end_date)
        # Recurse onto each period of adjacent dates between start_date
        # and end_date (inclusive).
        def accum_returns(accum, date_pair):
            """ Grows `accum` by return over period of `date_pair` """
            start_date, end_date = date_pair
            return accum * (
                1 + _return_over_period(
                    returns, start_date, end_date,
                    dates_interval, high_precision))
        return reduce(accum_returns, pairwise(dates), 1) - 1
    # We only need to do the above on the first call, not on recursion.
    # So split off the remaining logic into a separate function call:
    return _return_over_period(
        returns, start_date, end_date, dates_interval, high_precision)

def _return_over_period_array(
        dates, returns, start_date, end_date,
        dates_interval=None, high_precision=None):
    """ Determines the total return between `start_date` and `end_date`.

    Arguments:
        dates (list[datetime]): Dates at which returns have been
            observed. Must have a one-to-one correspondence with
            `returns`, such that `returns[i]` is the return observed at
            `dates[i]`.
        returns (list[HighPrecisionOptional]): Returns as relative
            values (e.g. `0.5` implies 50% return).
            Must have a one-to-one correspondence with `dates`, such
            that `returns[i]` is the return observed at `dates[i]`.
        start_date (datetime): A date within the range represented by
            the keys of `returns` (i.e. no earlier than the earliest
            key-date and no later than the latest key-date). `date` does
            not need to be a key in `returns`.
        end_date (datetime): A date within the range represented by
            the keys of `returns` (i.e. no earlier than the earliest
            key-date and no later than the latest key-date). `date` does
            not need to be a key in `returns`.
        dates_interval (relativedelta | timedelta): The period covered
            by the first date in `dates`. Optional. Will be inferred if
            not provided; see `_infer_interval`.
        high_precision (Callable[[float], HighPrecisionType] | None): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Returns:
        (HighPrecisionOptional): The total return between `start_date`
        and `end_date`. If `start_date` and `end_date` are not in
        `returns`, returns are interpolated for them via
        `interpolate_returns`.

    Raises:
        (KeyError): `date` is out of range.
    """
    start_index = get_date_index(dates, start_date)
    end_index = get_date_index(dates, end_date)
    # Recurse if there are any dates between `start_date` and `end_date`
    if (
            # If the indices are far apart, there must be elements between:
            end_index > start_index + 1 or
            # If `start_date` isn't in `dates`, `start_index` should be
            # the same as `end_index` (since it will point to the next
            # element). If not, there's an element between:
            (dates[start_index] != start_date and start_index < end_index)):
        recurse_dates = dates[start_index:end_index]
        # Ensure that `start_date` and `end_date` are both recursed on:
        if recurse_dates[0] != start_date:
            recurse_dates.insert(0, start_date)
        if recurse_dates[-1] != end_date:
            recurse_dates.append(end_date)
        # Recurse onto each period of adjacent dates between start_date
        # and end_date (inclusive).
        def accum_returns(accum, date_pair):
            """ Grows `accum` by return over period of `date_pair` """
            start_date, end_date = date_pair
            return accum * (
                1 + _return_over_period_array_r(
                    dates, returns, start_date, end_date,
                    dates_interval, high_precision))
        return reduce(accum_returns, pairwise(recurse_dates), 1) - 1
    # We only need to do the above on the first call, not on recursion.
    # So split off the remaining logic into a separate function call:
    return _return_over_period_array_r(
        dates, returns, start_date, end_date, dates_interval, high_precision)

def _return_over_period(
        returns, start_date, end_date, dates_interval, high_precision):
    """ Recursive helper for `return_over_period`.

    In this function, `start_date` and `end_date` are assumed to be
    adjacent. Otherwise, the documentation for `return_over_period`
    applies here too.
    """
    # Simplest case: The period between dates is represented exactly:
    if start_date in returns and end_date in returns:
        return returns[end_date]
    # If this period trims off the end of a larger period, simplify the
    # problem by finding the return over the larger period and then
    # reduce it by the return over the trimmed portion. (Both periods
    # end on a key date, so are not trimmed on the right-hand-side.)
    if end_date not in returns:
        next_date = min(date for date in returns if date > end_date)
        total_return = (1 + _return_over_period(
                returns, start_date, next_date, dates_interval, high_precision))
        trimmed_return = (1 + _return_over_period(
                returns, end_date, next_date, dates_interval, high_precision))
        return total_return / trimmed_return - 1
    # If we're made it here, we can guarantee that `end_date` is in
    # returns but `start_date` isn't. Find the bounds for the full
    # period ending on `end_date`, determine the daily rate of return
    # over that period, and calculate the total return over the shorter
    # period between `start_date` and `end_date`::
    prev_date = max(
        (date for date in returns if date < start_date), default=None)
    if prev_date is None:
        # Special case: `end_date` is first date in `returns`.
        if dates_interval is None:
            dates_interval = infer_interval(returns)
        prev_date = end_date - dates_interval
        if start_date < prev_date:
            # Don't extrapolate past prev_date
            raise KeyError(str(start_date) + " is out of range.")
    interval = end_date - prev_date
    elapsed = end_date - start_date
    # Assume that the rate of growth is constant over `interval` and
    # compounds daily. Then the return over `interval` is given by:
    # `P(1+r_t)=P(1+r_d)^t`
    # and more generally the return over any number of days can be
    # expressed as:
    # `P(1+r_t)^(d/t)=P(1+r_d)^d`
    # where P is a portfolio value, `r_t` is the return over `interval`
    # having length `t` (in days), `r_d` is the daily rate of return,
    # and `d` is the number of days of compounding.
    # We can thus solve for `r_d`:
    # `r_d = (1 + r_t)^(d/t)-1`
    if not high_precision:
        # Convert exponent to high-precision if needed:
        exp = elapsed.days / interval.days
    else:
        exp = high_precision(elapsed.days) / high_precision(interval.days)
    return ((1 + returns[end_date]) ** exp) - 1

def _return_over_period_array_r(
        dates, returns, start_date, end_date, dates_interval, high_precision):
    """ Recursive helper for `return_over_period_array`.

    In this function, `start_date` and `end_date` are assumed to be
    adjacent. Otherwise, the documentation for
    `return_over_period_array` applies here too.
    """
    start_index = get_date_index(dates, start_date)
    end_index = get_date_index(dates, end_date)
    # Simplest case: The period between dates is represented exactly:
    if dates[start_index] == start_date and dates[end_index] == end_date:
        return returns[end_index]
    # If this period trims off the end of a larger period, simplify the
    # problem by finding the return over the larger period and then
    # reduce it by the return over the trimmed portion. (Both periods
    # end on a key date, so are not trimmed on the right-hand-side.)
    if not dates[end_index] == end_date:
        next_date = dates[end_index]
        total_return = (1 + _return_over_period_array(
                dates, returns, start_date, next_date,
                dates_interval, high_precision))
        trimmed_return = (1 + _return_over_period_array(
                dates, returns, end_date, next_date,
                dates_interval, high_precision))
        return total_return / trimmed_return - 1
    # If we're made it here, we can guarantee that `end_date` is in
    # returns but `start_date` isn't. Find the bounds for the full
    # period ending on `end_date`, determine the daily rate of return
    # over that period, and calculate the total return over the shorter
    # period between `start_date` and `end_date`::
    if start_index == 0:
        # Special case: `start_date` precedes the earliest date in `dates`.
        if dates_interval is None:
            dates_interval = infer_interval(dates)
        prev_date = dates[0] - dates_interval
        if start_date < prev_date:
            # Don't extrapolate past prev_date
            raise KeyError(str(start_date) + " is out of range.")
    else:
        prev_date = dates[start_index - 1]
    interval = end_date - prev_date
    elapsed = end_date - start_date
    # Assume that the rate of growth is constant over `interval` and
    # compounds daily. Then the return over `interval` is given by:
    # `P(1+r_t)=P(1+r_d)^t`
    # and more generally the return over any number of days can be
    # expressed as:
    # `P(1+r_t)^(d/t)=P(1+r_d)^d`
    # where P is a portfolio value, `r_t` is the return over `interval`
    # having length `t` (in days), `r_d` is the daily rate of return,
    # and `d` is the number of days of compounding.
    # We can thus solve for `r_d`:
    # `r_d = (1 + r_t)^(d/t)-1`
    if not high_precision:
        # Convert exponent to high-precision if needed:
        exp = elapsed.days / interval.days
    else:
        exp = high_precision(elapsed.days) / high_precision(interval.days)
    return ((1 + returns[end_index]) ** exp) - 1

def regularize_returns(
        returns, interval, date=None, num_dates=None,
        dates_interval=None, high_precision=None):
    """ Generates a sequence of returns with regularly-spaced dates.

    The resulting sequence contains only dates which are spaced apart
    from `date` by an integer number of `interval`. So, for example,
    if `interval` is `relativedelta(years=1)` then the resulting
    sequence will contain annualized returns for each year for which
    there is data (on the same month and day as `date`).

    Arguments:
        returns (OrderedDict[datetime, HighPrecisionOptional]): A
            mapping of dates to relative values, e.g. rates of return.
        interval (timedelta | relativedelta): The period between dates.
        date (datetime): The date from which all other dates in the
            resulting sequence are calculated.
            Optional; defaults to the first date in `returns`.
        num_dates (int): The number of dates for which to generate
            returns. Optional; if not provided, as many dates as
            possible will be generated.
        dates_interval (relativedelta | timedelta): The period covered
            by the first date in `dates`. Optional. Will be inferred if
            not provided; see `_infer_interval`.
        high_precision (Callable[[float], HighPrecisionType] | None): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Returns:
        (OrderedDict[datetime, HighPrecisionOptional]): A mapping of
        dates to relative values, e.g. rates of return, where the dates
        are regularly spaced apart by `interval`. Returns are
        interpolated wherever necessary based on `interpolate_return`.

    Raises:
        (KeyError): `start_date` is out of range.
    """
    # Deal with array-style input:
    if isinstance(returns, (list, tuple)):
        return _regularize_returns_array(
            *returns, interval, date=date, num_dates=num_dates,
            dates_interval=dates_interval, high_precision=high_precision)
    # Get this value here to avoid repeating that work in called methods
    if dates_interval is None:
        dates_interval = infer_interval(returns, sample=DATES_INTERVAL_SAMPLES)
    # Get a list of dates spaced apart by `interval` on or after `date`
    regularized_dates = _get_regularized_dates(
        returns, date, interval,
        num_dates=num_dates, dates_interval=dates_interval, is_start_date=True)
    # To regularize returns, determine the total return for each time
    # period of length `interval` in the dateset.
    regularized_returns = OrderedDict(
        (date, return_over_period(
            returns, date - interval, date,
            high_precision=high_precision))
        for date in regularized_dates)
    return regularized_returns

def _regularize_returns_array(
        dates, returns, interval,
        date=None, num_dates=None, dates_interval=None, high_precision=None):
    """ Generates a sequence of returns with regularly-spaced dates.

    Equivalent to `regularize_returns`, except that instead of
    `dict`-type `returns`, this method receives separate sequences of
    `dates` and `returns` and returns a tuple of regularized
    `(dates, returns)`.
    """
    # Get this value here to avoid repeating that work in called methods
    if dates_interval is None:
        dates_interval = infer_interval(dates, sample=DATES_INTERVAL_SAMPLES)
    # Get a list of dates spaced apart by `interval` on or after `date`
    regularized_dates = _get_regularized_dates(
        dates, date, interval,
        num_dates=num_dates, dates_interval=dates_interval, is_start_date=True)
    # To regularize returns, determine the total return for each time
    # period of length `interval` in the dateset.
    regularized_returns = [
        _return_over_period_array(
            dates, returns, date - interval, date,
            dates_interval=dates_interval, high_precision=high_precision)
        for date in regularized_dates]
    return (regularized_dates, regularized_returns)

def _get_regularized_dates(
        dates, date, interval,
        num_dates=None, dates_interval=None, is_start_date=False):
    """ Gets a list of dates spaced apart by `interval`.

    This function finds all periods of length `interval` in `dates` that
    are offset from `date` by an integer multiple of `interval` (and
    which are entirely within the range of dates in `dates`) and returns
    the dates that represent them.

    In other words, `date` is one of the output dates (unless it's not
    in range of `dates`), and all output dates are offset by from
    `date` by some multiple of `interval`.

    The first date in `dates` is treated as if it covers a period of
    length of `dates_interval`. If not provided, this interval will be
    inferred from the spacing of dates in `dates`.

    If `num_dates` is provided, up to `num_dates` dates will be
    generated. This can be helpful when working with large datasets.

    If `is_start_date=True`, only dates _on or after_ `date` are
    generated.

    Returns:
        (list[datetime]): A list of dates spaced apart by `interval`,
        relating to periods falling in range of `returns`, and offset
        from `date` by a multiple of `interval`.
    """
    # Expand the range of dates to include the beginning of the period
    # ending on the start date:
    if dates_interval is None:
        dates_interval = infer_interval(dates)
    first_date = get_first_date(dates) - dates_interval
    last_date = get_last_date(dates)
    # Start with the first date in the dataset if `date` is not provided
    if date is None:
        date = first_date
    # If `date` is not a start date, we want to find dates _prior to_
    # `date` as well. In that case, get as close as possible to
    # `first_date` by backing up to `first_date` or just before:
    if is_start_date is False:
        while date > first_date:
            date -= interval
    # Deal with dates outside the range of `returns` by moving forward
    # to the earliest date where returns over the full period are known:
    earliest_date = first_date + interval
    while date < earliest_date:
        date += interval
    # Get a list of dates spaced apart by `interval` starting on `date`:
    if num_dates is None:
        # Get as many dates as possible (0, 1, 2, ...)
        counter = count(start=0)
    else:
        # Get only `num_dates` dates (0, 1, 2, ..., num_dates)
        counter = range(num_dates)
    regularized_dates = takewhile(
        lambda x: x <= last_date,
        map(lambda x: date + x * interval, counter))
    return list(regularized_dates)  # Convert iterator to list

def _is_array_pair(val):
    """ Returns `True` if `val` is a pair of arrays. """
    return (
        isinstance(val, (list, tuple)) and
        len(val) == 2 and
        all(isinstance(col, (list, tuple)) for col in val))

def infer_interval(dates, sample=None):
    """ Infers the interval between dates in `dates`.

    This method returns the most common (i.e. modal) interval between
    dates in `dates`. Where there are multiple modes, the one that
    first appears closest to the first date in `dates` is returned.

    If working with large datasets, it may help to set `sample=100` or
    similar, so as to avoid iterating over the entire dataset.

    Arguments:
        dates (Iterable[datetime]): An iterable container of datetimes,
            in sorted order from earliest to latest.
        sample (int | None): The number of intervals to sample.
            Optional. If not provided, all intervals are sampled.

    Returns:
        (relativedelta | None): The modal interval between dates in
        `dates`, or `None` if this cannot be determined.
    """
    # If this is a pair of arrays, assume it's a pair of date-value
    # arrays, so infer based on dates in the first array of the pair:
    if _is_array_pair(dates):
        return infer_interval(dates[0], sample=sample)
    # Limit the number of date-pairs sampled, if requested:
    if sample is not None and len(dates) > sample:
        if isinstance(dates, dict):
            dates = takewhile(lambda x: x <= sample, dates)
        else:
            dates = dates[0:sample]  # Slicing is faster, if supported
    # Find all intervals between adjacent dates:
    intervals = (
        relativedelta(end, start) for (start, end) in pairwise(dates))
    # Return the modal interval. (If there are multiple modes, this
    # returns the one that first appears closest to the start date)
    try:
        return mode(intervals)
    except StatisticsError:
        # If there's not enough data to infer from, return `None`
        return None

def values_from_returns(
        returns, interval=None, start_val=100):
    """ Converts returns to portfolio values.

    The resulting sequence of values has the same dates as `returns`,
    except that it also adds a a date preceding the first date in
    returns by `interval`. The value at the added date is `start_val`.
    For each other date, the corresponding value is the new portfolio
    value after growing (or shrinking, for negative values) the previous
    portfolio value by the value for that date in `returns`.

    If `interval` is not provided, `values_from_returns` will insert a
    date based on the apparent frequency of data in `returns` (c.f.
    `infer_interval`).

    Example:
        ```
        returns = {
            datetime(2000,1,1): 2,
            datetime(2001,1,1): 2}
        values = values_from_returns(returns)
        ```
        In this example, `values` is given by:
        ```
        {
            datetime(1999,1,1): 100,
            datetime(2000,1,1): 200,
            datetime(2001,1,1): 400}
        ```

    Arguments:
        returns (OrderedDict[date, HighPrecisionOptional]):
            An ordered mapping of dates to portfolio values.
        interval (timedelta | relativedelta): The spacing of dates, used
            for inserting a new date at the start of the dataset.
            Optional; if not provided, this will be inferred from the
            dates of `returns`.
        start_val (HighPrecisionOptional): The value for the first
            date in the output. Optional; defaults to 100. Recommend
            providing a high-precision datatype if `returns` uses
            high-precision datatypes for values.

    Returns:
        (OrderedDict[date, HighPrecisionOptional]):
            An ordered mapping of dates to percentage returns.
    """
    # Deal with array-style inputs:
    if isinstance(returns, (tuple, list)):
        return _values_from_returns_array(
            *returns, interval=interval, start_val=start_val)
    if interval is None:
        interval = infer_interval(returns)
    # Add a date just before the start of our dataset with $100 in value
    start_date = get_first_date(returns) - interval
    values = OrderedDict()
    values[start_date] = start_val
    # Now convert each entry of `returns` to a new portfolio value:
    prev_date = start_date
    for date in returns:
        # The value at `date` is just the previously-recorded value
        # adjusted by the return at `date`:
        values[date] = values[prev_date] * (1 + returns[date])
        prev_date = date
    return values

def _values_from_returns_array(
        dates, returns, interval=None, start_val=100):
    """ Array-based companion to `values_from_returns` """
    if interval is None:
        interval = infer_interval(dates)
    # Add a date just before the start of our dataset with $100 in value
    start_date = get_first_date(dates) - interval
    expanded_dates = [start_date] + dates
    values = [start_val]
    # Now convert each entry of `returns` to a new portfolio value:
    for (i, return_val) in enumerate(returns, start=1):
        # The value at `date` is just the previously-recorded value
        # adjusted by the return at `date`:
        values.append(values[i-1] * (1 + return_val))
    return (expanded_dates, values)

def _return_interval(dates, date):
    """ Gets the interval for which `date` represents the return.

    Returns:
        (relativedelta | None): The size of the interval over which the
        return at `date` is calculated. This value is always positive.
        Or, if the interval cannot be determined, returns `None`.
    """
    # Get the date immediately preceding `date`:
    if isinstance(dates, dict):
        prev_date = max(
            # Stop iterating at `date` (this assumes `dates` is ordered)
            takewhile(lambda x: x < date, dates),
            default=None)
    else:
        index = bisect_left(dates, date)
        prev_date = dates[index - 1] if index > 0 else None
    # The interval is the time between `date` and the preceding date:
    if prev_date is not None:
        return relativedelta(date, prev_date)
    # Special case: `date` is or precedes the very first date.
    first_date = get_first_date(dates)
    # If `date` is within the (extended) bounds of `returns`, try to
    # return the interval from the extended lower bound:
    interval = infer_interval(dates)
    if date > first_date - interval:
        return interval
    # If `date` is even earlier than that, can't infer the interval:
    return None

def return_for_date(values, date, interval=None, high_precision=None):
    """ Determines return for `date`.

    Each return value for a given `date` is the return observed over the
    preceding period of length `interval`. That is, the return is
    calculated over a period _ending_ at `date`.

    Arguments:
        values (OrderedDict[datetime, HighPrecisionOptional]): A mapping
            of dates to absolute values, e.g. portfolio values.
        date (datetime): A date within the range represented by the keys
            of `values` (i.e. no earlier than the earliest key-date and
            no later than the latest key-date). `date` does not need to
            be (and usually isn't) a key in `values`.
        interval (timedelta): The period between dates. Optional.
            If not provided, determines an interval for each date based
            on proximity of adjacent dates.
        high_precision (Callable[[float], HighPrecisionType] | None): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Returns:
        (OrderedDict[date, HighPrecisionOptional] | None):
            An ordered mapping of dates to percentage returns (or, if
            the data needed to determine a return over `interval` is
            not present, `None`).
    """
    # Deal with array-style inputs:
    if isinstance(values, (tuple, list)):
        return _return_for_date_array(
            *values, date, interval=interval, high_precision=high_precision)
    # If interval is not provided, infer it from the spacing of dates
    # in `values`:
    if interval is None:
        interval = _return_interval(values, date)
        if interval is None:
            return None
    start_date = date - interval
    end_date = date
    # If the interval in question doesn't fall within the bounds of our
    # data, we can't calculate the return:
    if start_date < min(values) or end_date > max(values):
        return None
    # Get the values on `start_date` and `end_date`, interpolating from
    # surrounding data if necessary:
    start_val = interpolate_value(
        values, start_date, high_precision=high_precision)
    end_val = interpolate_value(
        values, end_date, high_precision=high_precision)
    # Return is just the amount by which the ratio exceeds 1:
    return end_val / start_val - 1

def _return_for_date_array(
        dates, values, date, interval=None, high_precision=None):
    """ Array-based companion to `return_for_date` """
    # If interval is not provided, infer it from the spacing of dates
    # in `values`:
    if interval is None:
        interval = _return_interval(dates, date)
        if interval is None:
            return None
    start_date = date - interval
    end_date = date
    # If the interval in question doesn't fall within the bounds of our
    # data, we can't calculate the return:
    if start_date < get_first_date(dates) or end_date > get_last_date(dates):
        return None
    # Get the values on `start_date` and `end_date`, interpolating from
    # surrounding data if necessary:
    start_val = _interpolate_value_array(
        dates, values, start_date, high_precision=high_precision)
    end_val = _interpolate_value_array(
        dates, values, end_date, high_precision=high_precision)
    # Return is just the amount by which the ratio exceeds 1:
    return end_val / start_val - 1

def returns_from_values(values, interval=None, high_precision=None):
    """ Generates returns for each date in `values`.

    By default, this is the return for each date since the preceding
    date. This behaviour can be customized via the `interval` parameter.
    If `interval` is provided, the return for each date will be the
    return for a period of length `interval` preceding `date`.

    Dates for which porfolio values are not known at least `interval`
    into the past are not included in the result. With default
    parameters, this means that the first date in `values` will be
    excluded from the result.
    For instance, assuming a one-year `interval`, if the dataset
    includes portfolio values for 2000, 2001, and 2002, the returned
    dict will include returns only for dates in 2000 and 2001 (but not
    2002, as no portfolio values are known for 2003 or later).

    Args:
        values (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to portfolio values.
            Optional. Defaults to `self.values`.
        interval (timedelta): The interval over which returns are to be
            calculated for each date. Optional. If not provided,
            determines an interval for each date based on proximity of
            adjacent dates.
        high_precision (Callable[[float], HighPrecisionType] | None): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Returns:
        (OrderedDict[date, float | HighPrecisionType]): An ordered
            mapping of dates to percentage returns representing the
            return for a time period of length `interval` following
            each key date (or preceding, for negative `interval`).
    """
    # Deal with array-style inputs:
    if isinstance(values, (tuple, list)):
        return _returns_from_values_array(
            *values, interval=interval, high_precision=high_precision)
    # Otherwise, assume dict-like:
    interval_returns = OrderedDict()
    for date in values:
        returns = return_for_date(
            values, date, interval=interval, high_precision=high_precision)
        if returns is not None:
            interval_returns[date] = returns
    return interval_returns

def _returns_from_values_array(
        dates, values, interval=None, high_precision=None):
    """ Array-based companion to `returns_from_values` """
    # In the simple case, just calculate returns between adjacent dates:
    if interval is None:
        return_dates = dates[1:]
        return_values = [
            next_val / prev_val - 1
            for (prev_val, next_val) in pairwise(values)]
        return (return_dates, return_values)
    # Otherwise, we need to calculate return over each interval:
    return_dates = []
    return_values = []
    for date in dates:
        returns = _return_for_date_array(
            dates, values, date,
            interval=interval, high_precision=high_precision)
        if returns is not None:
            return_dates.append(date)
            return_values.append(returns)
    return (return_dates, return_values)

def get_date_index(dates, date):
    """ Finds the index of `date` in `dates`.

    If `date` is not in `dates`, returns the index of the first
    subequent date. `dates` must be sorted.
    """
    return bisect_left(dates, date)

def get_first_date(dates):
    """ Gets the first date represented in `dates` """
    if isinstance(dates, dict):
        return min(dates)
    return dates[0]

def get_last_date(dates):
    """ Gets the last date represented in `dates` """
    if isinstance(dates, dict):
        return max(dates)
    return dates[-1]

def mapping_to_arrays(vals):
    """ Converts `vals` to pairs of lists. """
    # Convert dict-like to a pair of lists:
    if isinstance(vals, Mapping):
        # In Python 3.6+, `dict` is order-preserving.
        return (list(vals.keys()), list(vals.values()))
    # Convert tuple/list/etc of dict-likes to tuple of pairs of lists:
    if (
            isinstance(vals, Sequence) and
            all(isinstance(val, dict) for val in vals)):
        return list(mapping_to_arrays(val) for val in vals)
    # Otherwise, return `vals` as-is
    return vals

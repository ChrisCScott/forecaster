""" Utility methods for `forecaster.scenario`. """

from bisect import bisect_left
from itertools import pairwise
from functools import reduce
from statistics import mode
from collections import OrderedDict
from dateutil.relativedelta import relativedelta

def interpolate_value(values, date):
    """ Determines a portfolio value on `date` based on nearby dates.

    This method is aimed at sequences like
    `{datetime(2000,1,1): 100, datetime(2002,1,1): 300}`
    where it would be sensible to interpolate a value of `200` for
    `datetime(2001,1,1)` because each value is absolute and is not
    expressed relative to preceding values.

    If values in `values` are relative, such as rates of return
    expressed in percentage terms, then use `interpolate_return`.

    Arguments:
        values (OrderedDict[datetime, HighPrecisionOptional]): A mapping
            of dates to absolute values, e.g. portfolio values.
        date (datetime): A date within the range represented by the keys
            of `values` (i.e. no earlier than the earliest key-date and
            no later than the latest key-date). `date` does not need to
            be (and usually isn't) a key in `values`.

    Returns:
        (HighPrecisionOptional): A value at `date`. If `date` is not
        in `values`, this is the *weighted average* of the values
        nearest in time to `date` (before and after).

    Raises:
        (KeyError): `date` is out of range.
    """
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
    # Weight values based on how close they are to `date`:
    days_total = (next_date - prev_date).days
    days_prev = (date - prev_date).days
    days_next = (next_date - date).days
    weighted_prev = days_prev * values[prev_date]
    weighted_next = days_next * values[next_date]
    # Interpolate a value on `date` based on the dates before/after:
    weighted_total = (weighted_next + weighted_prev) / days_total
    return weighted_total

def return_over_period(returns, start_date, end_date, high_precision=None):
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
                    returns, start_date, end_date, high_precision))
        return reduce(accum_returns, pairwise(dates), 1) - 1
    # We only need to do the above on the first call, not on recursion.
    # So split off the remaining logic into a separate function call:
    return _return_over_period(returns, start_date, end_date, high_precision)

def _return_over_period(returns, start_date, end_date, high_precision):
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
                returns, start_date, next_date, high_precision))
        trimmed_return = (1 + _return_over_period(
                returns, end_date, next_date, high_precision))
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
        interval = _infer_interval(returns)
        prev_date = end_date - interval
        if start_date < prev_date:
            # Don't extrapolate past prev_date
            raise KeyError(str(start_date) + " is out of range.")
    interval = end_date - prev_date
    elapsed = end_date - start_date
    # Assume that the rate of growth is constant over `interval` and
    # compounds daily. Then the return over `interval` is given by:
    # `P(1+r_t)=P(1+r_d)^d`
    # where P is a portfolio value, `r_t` is the return over `interval`,
    # `r_d` is the daily rate or return, and `d` is the number of days
    # in `interval`. We can thus solve for `r_d`:
    # Convert exponents to high-precision if needed:
    interval_pow = 1 / interval.days
    elapsed_pow = elapsed.days
    if high_precision is not None:
        interval_pow = high_precision(interval_pow)
        elapsed_pow = high_precision(elapsed_pow)
    daily_return = ((1 + returns[end_date]) ** interval_pow) - 1
    # Then compound the daily return over the elapsed number of days:
    return (1 + daily_return) ** elapsed_pow - 1

def regularize_returns(returns, interval, date=None, high_precision=None):
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
    # Expand the range of dates to include the beginning of the period
    # ending on the start_date:
    returns_interval = _infer_interval(returns)
    first_date = min(returns) - returns_interval
    expanded_returns = OrderedDict(returns)  # Avoid mutating input
    expanded_returns.update({first_date: 0})
    expanded_returns.move_to_end(first_date, last=False)
    # Get a list of dates falling within the expanded range:
    dates = _get_regularized_dates(expanded_returns, date, interval)
    # To regularize returns, determine the total return for each time
    # period of length `interval` in the dateset.
    regularized_returns = OrderedDict(
        (date, return_over_period(
            expanded_returns, date - interval, date,
            high_precision=high_precision))
        for date in dates)
    return regularized_returns

def _get_regularized_dates(returns, date, interval):
    """ Gets a list of dates spaced apart by `interval`.

    This function finds all periods of length `interval` that are offset
    from `date` by an integer multiple of `interval` (and which are
    entirely within the range of dates in `returns`) and returns the
    dates that represent them.

    In other words, `date` is one of the output dates (unless it's not
    in range of `returns`), and all output dates are offset by from
    `date` by some multiple of `interval`.

    Returns:
        (list[datetime]): A list of dates spaced apart by `interval`,
        relating to periods falling in range of `returns`, and offset
        from `date` by a multiple of `interval`.
    """
    # Get the bounds of the range of dates in `returns`:
    first_date = min(returns)
    last_date = max(returns)
    # Start with the first date in the dataset if `date` is not provided
    if date is None:
        date = first_date
    # We want `date` to be as close to `first_date` as possible.
    # Deal with dates past `first_date` by backing up to `first_date` or
    # just before:
    while date > first_date:
        date -= interval
    # Deal with dates before `first_date` by moving ahead to
    # `first_date` or just past it:
    while date < first_date:
        date += interval
    # Exclude dates whose periods extend outside the range of `returns`:
    date += interval
    # Get a list of dates spaced apart by `interval` starting on `date`:
    # There's probably a clever comprehension for this, but... oh well.
    dates = []
    while date <= last_date:
        dates.append(date)
        date += interval
    return dates

def _infer_interval(returns):
    """ Infers the interval between dates in `returns`. """
    # Find all intervals between adjacent dates:
    intervals = [
        relativedelta(end, start) for (start, end) in pairwise(returns)]
    # Return the modal interval. (If there are multiple modes, this
    # returns the one that first appears closest to the start date)
    return mode(intervals)

def values_from_returns(
        returns, interval=None, start_val=100):
    """ Converts returns to portfolio values.

    The resulting sequence of values will start with a value of 100.

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
    if interval is None:
        interval = _infer_interval(returns)
    # Add a date just before the start of our dataset with $100 in value
    start_date = min(returns) - interval
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

def _return_interval(returns, date):
    """ Gets the interval for which `date` represents the return.

    Returns:
        (relativedelta | None): The size of the interval over which the
        return at `date` is calculated. This value is always positive.
        Or, if the interval cannot be determined, returns `None`.
    """
    # Get the date immediately preceding `date`:
    earlier_dates = list(val for val in returns if val < date)
    if earlier_dates:
        return relativedelta(date, max(earlier_dates))
    # Special case: This precedes is the very first date.
    # If `date` is within the (extended) bounds of `returns`, try to
    # return the interval from the extended lower bound:
    first_date = min(returns)
    if date < first_date:
        interval = _infer_interval(returns)
        if date > first_date - interval:
            return interval
    # Otherwise: Who knows?
    return None

def return_for_date_from_values(values, date, interval=None):
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

    Returns:
        (OrderedDict[date, HighPrecisionOptional] | None):
            An ordered mapping of dates to percentage returns (or, if
            the data needed to determine a return over `interval` is
            not present, `None`).
    """
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
    start_val = interpolate_value(values, start_date)
    end_val = interpolate_value(values, end_date)
    # Return is just the amount by which the ratio exceeds 1:
    return end_val / start_val - 1

def returns_for_dates_from_values(values, interval=None):
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

    Returns:
        (OrderedDict[date, float | HighPrecisionType]): An ordered
            mapping of dates to percentage returns representing the
            return for a time period of length `interval` following
            each key date (or preceding, for negative `interval`).
    """
    interval_returns = OrderedDict()
    for date in values:
        returns = return_for_date_from_values(
            values, date, interval=interval)
        if returns is not None:
            interval_returns[date] = returns
    return interval_returns

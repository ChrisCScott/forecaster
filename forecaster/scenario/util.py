""" Utility methods for `forecaster.scenario`. """

from bisect import bisect_left
from collections import OrderedDict

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

def interpolate_return(returns, date, lookahead=True):
    """ Determines a portfolio return on `date` based on nearby dates.

    This method is aimed at sequences like
    `{datetime(2000,1,1): 0.10, datetime(2002,1,1): 0.20}`
    where it would be sensible to interpolate a value of `0.10` for
    `datetime(2001,1,1)` because each value is relative to preceding
    values.

    If values in `values` are absolute, such as portfolio values
    expressed in dollar terms, then use `interpolate_value`.

    NOTE: Values determined by this method are not safe to insert into
    `returns`. E.g. if a value of `0.10` is inserted at
    `datetime(2001,1,1)` as in the above example, the total return for
    the sequence of returns will become 10% larger.

    Arguments:
        returns (OrderedDict[datetime, HighPrecisionOptional]): A
            mapping of dates to relative values, e.g. rates of return.
        date (datetime): A date within the range represented by the keys
            of `returns` (i.e. no earlier than the earliest key-date and
            no later than the latest key-date). `date` does not need to
            be (and usually isn't) a key in `returns`.
        lookahead (bool): If True, each return value is interpreted as
            the return experienced _after_ its key-date, and so
            interpolated values will be determined by scaling the
            _previous_ value (since in this case `date` falls within
            the previous value's interval). Optional; defaults to False.

    Returns:
        (HighPrecisionOptional): A return at `date`. If `date` is not
        in `returns`, this is the return of the following date scaled
        down based on the proximity of `date` to the following date.

    Raises:
        (KeyError): `date` is out of range.
    """
    # Check to see if the date is available exactly:
    if date in returns:
        return returns[date]
    if not min(returns) <= date <= max(returns):
        raise KeyError(str(date) + ' is out of range.')
    # Get the dates on either side of `date`:
    dates = list(returns)
    index = bisect_left(dates, date)
    prev_date = dates[index-1]
    next_date = dates[index]
    next_return = returns[next_date]
    prev_return = returns[prev_date]
    # Scale the return at the next timestep based on the amount of time
    # elapsed since the previous timestep, as a proportion of the total
    # time between the previous and next timesteps:
    interval = next_date - prev_date
    elapsed = date - prev_date
    # Scale the return at the previous timestep for lookahead returns:
    if lookahead:
        scaled = (prev_return * elapsed.days) / interval.days
    # Otherwise, scale the return at the next timestep:
    else:
        scaled = (next_return * elapsed.days) / interval.days
    return scaled

def accumulate_return(returns, start_date, end_date, lookahead=False):
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
        lookahead (bool): If True, each return value is interpreted as
            the return experienced _after_ its key-date, and so
            interpolated values will be determined by scaling the
            _previous_ value (since in this case `date` falls within
            the previous value's interval). Optional; defaults to False.

    Returns:
        (HighPrecisionOptional): The total return between `start_date`
        and `end_date`. If `start_date` and `end_date` are not in
        `returns`, returns are interpolated for them via
        `interpolate_returns`.

    Raises:
        (KeyError): `date` is out of range.
    """
    # Rather than start with 0, use whatever value/datatype is provided
    # by `returns` by grabbing the starting (or ending) value first:
    # TODO: Only interpolate one endpoint (end_date if lookahead,
    # start_date otherwise) via `interpolate_return`. For the other
    # endpoint, we need to reverse the logic to find an interpolated
    # value based on an _out-of-range_ date (e.g. for lookahead returns,
    # need to look at the last value _before_ `start_date` (call it the
    # the precursor date) and determine how much return was calculated
    # _after_ start date based on the return for the precursor date.
    # This would be easy to implement as another flag to
    # `interpolate_returns`, but think about whether this would
    # overcomplicate things - maybe a separate method is better?)
    # TODO: Lookahead implies that each date covers
    # `[date, date+interval)`, whereas no-lookahead implies that each
    # date covers `(date-interval,date]`. So, if we're using lookahead
    # returns, we should interpolate end_date only if it is not in
    # `returns` (and exclude it if it is in `returns`); similarly, in
    # a no-lookahead scenario, we may need to discard `start_date`.
    if lookahead:
        total_return = interpolate_return(
            returns, end_date, lookahead=lookahead)
    else:
        total_return = interpolate_return(
            returns, start_date, lookahead=lookahead)
    # Get the product of all returns between the start and end dates:
    for (date, val) in returns.items():
        # (There are more efficient ways to iterate over a subrange
        # in an ordered array, but this is not performance-critical):
        if start_date < date < end_date:
            total_return *= 1 + val
    # end_date might not be in `returns`, so interpolate it:
    total_return *= interpolate_return(returns, end_date)
    return total_return

def regularize_returns(returns, interval, start_date=None):
    """ Generates a sequence of returns with regularly-spaced dates.

    The resulting sequence starts on `start_date` and provides a return
    value for each date some number of (integer) `interval`s into the
    future.

    Note that the return for a given date is the return over the
    _following_ time period of length `interval`. So for a one-year
    interval starting on 2000-01-01, the value for 2000-01-01 would be
    the total return between 2000-01-01 and 2001-01-01.

    Arguments:
        returns (OrderedDict[datetime, HighPrecisionOptional]): A
            mapping of dates to relative values, e.g. rates of return.
        interval (relativedelta): The period between dates.
        start_date (datetime): A date within the range represented by
            the keys of `returns` (i.e. no earlier than the earliest
            key-date and no later than the latest key-date). `date` does
            not need to be a key in `returns`.
            Optional; defaults to the first date in `returns`.

    Returns:
        (OrderedDict[datetime, HighPrecisionOptional]): A mapping of
        dates to relative values, e.g. rates of return, where the dates
        are regularly spaced apart by `interval`. Returns are
        interpolated wherever necessary based on `interpolate_return`.

    Raises:
        (KeyError): `start_date` is out of range.
    """
    # For convenience, find the first and last dates in the dataset:
    first_date = min(returns)
    last_date = max(returns)
    # Start with the first date in the dataset if no starting date is
    # provided:
    if start_date is None:
        date = first_date
    else:
        date = start_date
    # Allow start dates earlier than `lower_bound` for convenience,
    # to make it easier for client code to align several datasets
    # covering different date ranges:
    while date < first_date:
        date = date + interval
    # To regularize returns, determine the total return for each time
    # period of length `interval` in the dateset.
    regularized_returns = OrderedDict()
    while date <= last_date:
        next_date = date + interval
        # Note that the return for a given date is the return over the
        # _following_ time interval.
        regularized_returns[date] = accumulate_return(
            returns, date, next_date)
        date = next_date
    return regularized_returns

""" Provides tools for reading historical returns from CSV files. """

import csv
import datetime
from collections import OrderedDict
import dateutil
from dateutil.parser import parse
from forecaster.scenario.util import interpolate_value, regularize_returns
from forecaster.utility import resolve_data_path, HighPrecisionHandler

# Assume incomplete dates are in the first month/day:
DATE_DEFAULT = datetime.datetime(2000, 1, 1)
INTERVAL_DEFAULT = dateutil.relativedelta.relativedelta(years=1)

class HistoricalValueReader(HighPrecisionHandler):
    """ Reads historical value data from CSV files.

    This reads in a UTF-8 encoded CSV file with the following format:

    | Date Header | Value Header |
    |-------------|--------------|
    | date        | 100.0        |

    The header row is optional and is not used. Columns must be in the
    order shown above (e.g. the first column must be dates). Dates must
    be sequential and may be yearly, monthly, or daily.

    Data in the date column is converted from `str` to
    `datetime.datetime` via `dateutils.parse`. Data in the value
    column is converted to `float` or to a high-precision numeric type
    (if `high_precision` is provided.)

    Every non-blank row must have no blank entries.

    Arguments:
        filename (str): The filename of a CSV file to read. The file
            must be UTF-8 encoded. Relative paths will be resolved
            within the package's `data/` directory.
        return_values (bool): If True, the value column is interpreted
            as a portfolio value (e.g. $10,000). If False, the value
            column is interpreted as a series of percentage returns
            (relative to the previous entry). Defaults to True.
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` or `str` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Attributes:
        returns (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to percentage returns since
            the previous date.
    """

    def __init__(
            self, filename=None, return_values=False, *,
            high_precision=None):
        # Set up high-precision support:
        super().__init__(high_precision=high_precision)
        # Declare member attributes:
        self.values = OrderedDict()
        # For convenience, allow file read on init:
        if filename is not None:
            self.read(filename, return_values=return_values)

    def read(self, filename, return_values=False):
        """ Reads in a CSV file with stock, bond, and other returns.

        See docs for `__init__` for the format of the CSV file.
        """
        # If it's a relative path, resolve it to the `data/` dir:
        filename = resolve_data_path(filename)
        # Read in the CSV file:
        # (newline='' is recommended for file objects. See:
        # https://docs.python.org/3/library/csv.html#id3)
        with open(filename, encoding='utf-8', newline='') as file:
            # Detect the dialect to reduce the odds of application-
            # specific incompatibilities.
            sample = file.read(1024)
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample)
            has_header = sniffer.has_header(sample) # we'll use this later
            file.seek(0) # return to beginning of file for processing
            # Get ready to read in the file:
            reader = csv.DictReader(
                file, fieldnames=('date', 'return'), dialect=dialect)
            # Discard the header row, if any:
            if has_header:
                next(reader)
            # Read the file one row at a time:
            returns = {}
            for row in reader:
                # Convert the str-encoded date to `date`:
                date = parse(row['date'], default=DATE_DEFAULT)
                # Convert each non-empty entry to a numeric type:
                if row['return']:
                    returns[date] = self._convert_entry(row['return'])
        # Sort by date to make it easier to build rolling-window
        # scenarios, and to convert to percentages:
        self.values = OrderedDict(sorted(returns.items()))
        # Convert a sequence of returns to portfolio values, if needed.
        if return_values is True:
            self.values = self._convert_return_values(self.values)

    def returns(self, values=None, interval=INTERVAL_DEFAULT):
        """ Generates return over `interval` for each date in `values`.

        This is the return _following_ each date (i.e. looking forward
        in time), assuming positive `interval`. Dates for which porfolio
        values are not known at least `interval` into the future are not
        included in the result.

        For instance, assuming default one-year `interval`, if the
        dataset includes portfolio values for 2000, 2001, and 2002, the
        returned dict will include returns only for dates in 2000 and
        2001 (but not 2002, as no portfolio values are known for 2003 or
        later).

        Args:
            values (OrderedDict[date, float | HighPrecisionType]):
                An ordered mapping of dates to portfolio values.
                Optional. Defaults to `self.values`.
            interval (dateutil.relativedelta.relativedelta): The
                interval over which returns are to be calculated for
                each date. Optional. Defaults to one year.

        Returns:
            (OrderedDict[date, float | HighPrecisionType]): An ordered
                mapping of dates to percentage returns representing the
                return for a time period of length `interval` following
                each key date (or preceding, for negative `interval`).
        """
        interval_returns = OrderedDict()
        for date in values:
            returns = self._generate_return_from_date(
                values, date, interval=interval)
            if returns is not None:
                interval_returns[date] = returns
        return interval_returns

    def _generate_return_from_date(
            self, values, date, interval=INTERVAL_DEFAULT):
        """ Returns return over `interval` starting on `date`. """
        # We will compare values on `date` and on a date in the future:
        end_date = date + interval
        # If there's no data a year out, we can't get the annual return:
        if end_date > max(values):
            return None
        # Get the values on `date` and `end_date`, interpolating from
        # surrounding data if necessary:
        start_val = interpolate_value(values, date)
        end_val = interpolate_value(values, end_date)
        # Return is just the amount by which the ratio exceeds 1:
        return end_val / start_val - 1

    def _convert_entry(self, entry):
        """ Converts to str entry to a numeric type. """
        if self.high_precision is not None:
            return self.high_precision(entry)
        else:
            return float(entry)

    def _convert_return_values(self, returns):
        """ Converts returns to portfolio values.

        Arguments:
            returns (OrderedDict[date, float | HighPrecisionType]):
                An ordered mapping of dates to portfolio values.

        Returns:
            (OrderedDict[date, float | HighPrecisionType]):
                An ordered mapping of dates to percentage returns.
        """
        # Add a new date just before the first date. Space it appropriately
        # (e.g. one day before for daily values, one year before for annual)
        returns_iter = iter(returns)
        first_date = next(returns_iter)
        second_date = next(returns_iter)
        date_interval = dateutil.relativedelta.relativedelta(
            second_date, first_date)
        new_date = first_date - date_interval
        values = OrderedDict({new_date: self.precision_convert(100)})
        # Now convert each entry of `returns` to a new portfolio value:
        prev_date = new_date
        for (date, return_) in returns.items():
            values[date] = values[prev_date] * (1 + return_)
            prev_date = date
        return values

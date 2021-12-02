""" Provides tools for reading historical returns from CSV files. """

import csv
import datetime
from collections import OrderedDict
from dateutil.parser import parse
from forecaster.utility import resolve_data_path, HighPrecisionOptional

class HistoricalReturnReader(HighPrecisionOptional):
    """ Reads historical return data from CSV files.

    This reads in a UTF-8 encoded CSV file with the following format:

    | Date Header | Return Header |
    |-------------|---------------|
    | date        | 0.06          |

    The header row is optional and is not used. Columns must be in the
    order shown above (e.g. the first column must be dates). Dates must
    be sequential and may be yearly, monthly, or daily.

    Data in the `date` columns is converted from `str` to `date` via
    `dateutils.parse`. Data in the 'return' column is converted to
    `float` or to a high-precision numeric type (if `high_precision` is
    provided.)

    Every non-blank row must have no blank entries.

    Arguments:
        filename (str): The filename of a CSV file to read. The file
            must be UTF-8 encoded. Relative paths will be resolved
            within the package's `data/` directory.
        portfolio_values (bool): If True, the `return` column is
            interpreted as a portfolio value (e.g. $10,000 rather than
            5%) and will be converted to a percentage return, with
            the first row discarded.
            If False, values in the `return` column will be interpreted
            as percentage returns since the immediately-preceding date.
            Optional; will attempt to detect if not provided.
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` or `str` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.
    """

    def __init__(
            self, filename=None, portfolio_values=None, *,
            high_precision=None):
        # Set up high-precision support:
        super().__init__(high_precision=high_precision)
        # Declare member attributes:
        self.returns = OrderedDict()
        # For convenience, allow file read on init:
        if filename is not None:
            self.read(filename, portfolio_values=portfolio_values)

    def read(self, filename, portfolio_values=None):
        """ Reads in a CSV file with stock, bond, and other returns.

        See docs for `__init__` for the format of the CSV file.
        """
        # If it's a relative path, resolve it to the `data/` dir:
        filename = resolve_data_path(filename)
        # Read in the CSV file:
        with open(filename, encoding='utf-8') as file:
            # Detect the dialect to reduce the odds of application-
            # specific incompatibilities.
            sample = file.read(1024)
            sniffer = csv.Sniffer()
            dialect = sniffer.sniff(sample)
            has_header = sniffer.has_header(sample) # we'll use this later
            file.seek(0) # return to beginning of file for processing
            # Get ready to read in the file:
            reader = csv.DictReader(
                file, fieldnames=('date', 'return'), dialect=dialect,
                 # Recommended for file objects. See:
                 # https://docs.python.org/3/library/csv.html#id3
                newline='')
            # Discard the header row, if any:
            if has_header:
                next(reader)
            # Read the file one row at a time:
            returns = {}
            for row in reader:
                # Convert the str-encoded date to `date`:
                date = parse(row['date'], default=datetime.date)
                # Convert each non-empty entry to a numeric type:
                if row['return']:
                    returns[date] = self._convert_entry(row['return'])
        # Sort by date to make it easier to build rolling-window
        # scenarios, and to convert to percentages:
        self.returns = OrderedDict(sorted(returns.items()))
        # If portfolio_values is not provided, try to infer whether
        # this is a portfolio value or a percentage. As a rule of thumb,
        # we don't expect to see percentages of 1,000%+, so assume
        # values > 10 are portfolio values:
        if portfolio_values is None:
            first_val = self.returns[next(iter(self.returns))]
            portfolio_values = first_val >= 10
        # Convert from portfolio values to returns, if needed:
        if portfolio_values:
            _convert_portfolio_value(self.returns)

    def _convert_entry(self, entry):
        """ Converts to str entry to a numeric type. """
        if self.high_precision is not None:
            return self.high_precision(entry)
        else:
            return float(entry)

def _convert_portfolio_value(returns):
    """ Converts portfolio values to returns.

    This method mutates the input, both by modifying values (to be in
    percentage terms) and by deleting the first key-value pair (because
    the percentage change for the first value is unknown).

    Arguments:
        returns (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to portfolio values.
    """
    # Get the first entry:
    returns_iter = iter(returns)
    first_date = next(returns_iter)
    prev_value = returns[first_date]
    # Iterate over every entry *except* the first, in order,
    # dividing it by the previous value to get the return:
    for date in returns_iter:
        this_value = returns[date]
        # The percentage change is `new/old-1` (so losses are negative)
        returns[date] = (returns[date] / prev_value) - 1
        prev_value = this_value
    # Remove the first entry (since we don't know what its
    # return is relative to the previous timestep)
    del returns[first_date]

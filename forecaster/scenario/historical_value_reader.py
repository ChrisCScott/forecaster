""" Provides tools for reading historical returns from CSV files. """

import csv
from collections import OrderedDict
import datetime
import dateutil
from forecaster.scenario.util import (
    values_from_returns, returns_from_values)
from forecaster.utility import resolve_data_path, HighPrecisionHandler

# Assume incomplete dates are in the first month/day:
DATE_DEFAULT = datetime.datetime(2000, 1, 1)
INTERVAL_ANNUAL = dateutil.relativedelta.relativedelta(years=1)

class HistoricalValueReader(HighPrecisionHandler):
    """ Reads historical value data from CSV files.

    This reads in a UTF-8 encoded, comma-delimited CSV file with the
    following format:

    | Date Header | Value Header | Value Header | ...
    |-------------|--------------|--------------|
    | date        | 100.0        | 100.0        | ...

    The header row is optional and is not used. Headers may have any
    non-numeric value and are allowed only for human-readability.

    The first column must be dates. Data in the date column is converted
    from `str` to `datetime.datetime` via `dateutils.parse`. Non-empty
    data in value columns is converted to `float` or to a high-precision
    numeric type (if `high_precision` is provided.)

    By default, results are returned as a mapping of `{date: value}`
    pairs. Users desiring options for more efficient operations may
    consider passing `as_arrays=True`,

    If the data file is very large, it's recommended to pre-process it
    so that dates are in sorted (increasing) order and values are
    float-convertible (e.g. no spaces or commas; enclosing quotes are
    permitted, as these are stripped by `csv.reader`). In that case,
    pass the arg `fast_read=True`.

    Arguments:
        filename (str): The filename of a CSV file to read. The file
            must be UTF-8 encoded. Relative paths will be resolved
            within the package's `data/` directory.
        returns (bool): Set to `True` if data is formatted as relative
            returns over a period (e.g. "1" means 100%).
            Set to `False` if data is formatted as absolute values at
            a point in time (e.g. "1" means $1).
            Optional. If not provided, this will be inferred - see
            `_infer_returns` for more details.
        fast_read (bool): If `True`, data is presumed to be arranged in
            sorted order (i.e. with dates in increasing order) and
            values are assumed to be float-convertible without
            additional processing. If `False`, data will be sorted
            on read and values will be parsed to remove characters
            that are not legally float-convertible.
            Optional; defaults to `False`.
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` or `str` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Attributes:
        data (tuple[OrderedDict[date, HighPrecisionOptional]]):
            Each entry in `data` is a column of data, starting with the
            _second_ column. The keys of each entry are dates, taken
            from the _first_ column. So a file with three columns
            (A, B, C) will result in `data` having two entries, mapping
            `A` to `B` and `A` to `C`.
    """

    def __init__(
            self, filename=None, returns=None, fast_read=False, *,
            high_precision=None):
        # Set up high-precision support:
        super().__init__(high_precision=high_precision)
        # Declare member attributes:
        self.data = None
        self.fast_read = fast_read
        self._returns_values = None
        # For convenience, allow file read on init:
        if filename is not None:
            self.read(filename, returns=returns)

    def read(self, filename, returns=None):
        """ Reads in a CSV file with dates and portfolio values.

        See docs for `__init__` for the format of the CSV file.
        """
        # If it's a relative path, resolve it to the `data/` dir:
        filename = resolve_data_path(filename)
        # Read in the CSV file:
        # (newline='' is recommended for file objects. See:
        # https://docs.python.org/3/library/csv.html#id3)
        with open(filename, encoding='utf-8', newline='') as file:
            reader = self._get_csv_reader(file)
            data = self._get_data_from_csv_reader(reader)
        # Sort by date to make it easier to build rolling-window
        # scenarios (unless we're in fast-read mode):
        if not self.fast_read:
            self.data = self._sort_data(data)
        else:
            self.data = data
        # Find out if we're reading returns (vs. portfolio values) and
        # store that information for later processing:
        if returns is None and data:  # Don't try for empty dataset
            returns = self._infer_returns(data[0])
        self._returns_values = returns

    def returns(self, convert=None):
        """ Returns `data` as a dict of returns values. """
        # Convert data if the user hasn't hinted that we're reading in
        # returns-formatted values:
        if convert is None:
            convert = not self._returns_values
        if convert:
            return tuple(
                returns_from_values(
                    column, high_precision=self.high_precision)
                for column in self.data)
        return self.data

    def values(self, convert=None):
        """ Returns `data` as a dict of portfolio values. """
        # Convert data if the user has hinted that we're reading in
        # returns-formatted values:
        if convert is None:
            convert = self._returns_values
        if convert:
            return tuple(values_from_returns(column) for column in self.data)
        return self.data

    @staticmethod
    def _infer_returns(column):
        """ Infers whether `column` is likely a sequence of returns.

        `column` is presumed to be returns-values if:
            - Any value in `column` is negative
            - More than half of the non-zero values in `column` are
              less than 1.
        Otherwise, `column` is presumed to represent portfolio values.

        Argument:
            values (Iterable[HighPrecisionOptional] |
                Iterator[HighPrecisionOptional] |
                dict[Any, HighPrecisionOptional]): An iterator or
                iterable over numeric values (e.g. the values of a dict
                of date-value pairs). If a `dict` or subclass is
                provided, its `dict.values()` ValueView will be used.

        Returns:
            (bool): `True` if `values` is inferred to be a sequence of
            returns, `False` otherwise.
        """
        if isinstance(column, dict):
            column = column.values()
        num_vals = 0
        num_small_vals = 0
        for val in column:  # `values` may be an iterator, so iterate just once
            # Assume returns-values if any value is negative:
            if val < 0:
                return True
            # Keep track of how big any non-zero values are:
            if val == 0: # ignore 0 values
                continue
            if val < 1:  # Count small values
                num_small_vals += 1
            num_vals += 1  # Count all values
        # Find the proportion of values that look like percentages
        # (i.e. < 1), infer returns if >50% do look like percentages:
        return num_small_vals / num_vals > 0.5

    def _convert_entry(self, entry):
        """ Converts str entry to a numeric type.

        Raises:
            ValueError: If `entry` is not convertible to `float` (or to
            the high-precision type, if in high-precision mode).
        """
        # Remove leading/trailing spaces and commas (unless in fast-read mode):
        if not self.fast_read:
            # Remove any characters that aren't digits, dots, or signs.
            # (This does not guarantee that )
            entry = ''.join(i for i in entry if i.isdigit() or i in '+-.')
        if self.high_precision is not None:
            return self.high_precision(entry)
        return float(entry)

    def _get_csv_reader(self, file):
        """ Determines the dialect of `file` and whether it has a header """
        # Detect the dialect to reduce the odds of application-
        # specific incompatibilities.
        sample = file.read(1024)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample, delimiters=',')
        # We want to discard the header, if the file has one.
        has_header = sniffer.has_header(sample)
        # Sniffer.has_header is unreliable, so test manually too.
        if not has_header:
            # Return to beginning of file to read in the first row for
            # manual tests:
            file.seek(0)
            reader = csv.reader(file, dialect=dialect)
            first_row = next(reader)
            # Attempt to cast the second column to float; if it fails,
            # infer that this file has a header:
            try:
                _ = self._convert_entry(first_row[1])
            except:  # pylint: disable=bare-except
                # We don't know what type of exception `high_precision`
                # might throw
                has_header = True
        # Return to beginning of file for later processing:
        file.seek(0)
        reader = csv.reader(file, dialect=csv.excel)
        if has_header:  # discard header, if provided:
            next(reader)
        return reader

    def _get_data_from_csv_reader(self, reader):
        """ Reads in non-header rows of a CSV file and returns rows/cols """
        # Read the file one row at a time:
        data = []
        for row in reader:
            row_iter = iter(row)
            # Convert the str-encoded date to `date`:
            date = dateutil.parser.parse(
                next(row_iter), default=DATE_DEFAULT)
            # Process each non-date entry for the row:
            for (i, entry) in enumerate(row_iter):
                # Skip empty values:
                if not entry:
                    continue
                # We don't know how many columns are in the data
                # in advance, so add them dynamically:
                while len(data) <= i:
                    self._add_column(data)
                self._add_entry(data[i], date, entry)
        return data

    @staticmethod
    def _sort_data(data):
        """ Sorts each column of `data` by date. """
        return tuple(
            OrderedDict(sorted(column.items())) for column in data)

    @staticmethod
    def _add_column(data):
        """ Adds an empty column to `data`. MUTATES `data`! """
        data.append({})

    def _add_entry(self, column, date, val):
        """ Adds an entry for value `val` at date `date` to `column`. """
        column[date] = self._convert_entry(val)

class HistoricalValueReaderArray(HistoricalValueReader):
    """ Reads historical value data from CSV files as arrays.

    This class is functionally identical to `HistoricalValueReader`,
    except that data is represented as pairs of lists rather than as
    arrays. See `HistoricalValueReader` for more information.

    Attributes:
        data (tuple[tuple[list[date], list[HighPrecisionOptional]]]):
            Each entry in `data` is a column of data, starting with the
            _second_ column. Each column is represented as a tuple of
            two lists. The first list is an ordered list of dates.
            The second list is a list of values, in the same order (i.e.
            `column[0][i]` is the date for the value at `column[1][i]`).
            So a file with three columns (A, B, C) will result in `data`
            having two entries; the first is the tuple `(A, B)` and the
            second is the tuple `(A, C)`.
    """

    @classmethod
    def _infer_returns(cls, column):
        """ Extends _infer_returns to deal with pairs of arrays. """
        # If we get a pair of arrays, use the second one:
        if isinstance(column, (list, tuple)) and len(column) == 2:
            column = column[1]
        return super()._infer_returns(column)

    @staticmethod
    def _sort_data(data):
        """ Sorts each column of `data` by date. """
        # `data` has the form:
        # ((dates1, values1), (dates2, values2), ..., (datesn, valuesn))
        # where each dates item is a list and the corresponding values
        # item is a list of the same length. Each 2-tuple of dates and
        # values corresponds to a non-date column in the CSV file.
        # We want to sort all of the columns by date.
        # To do this, for each column, we zip together the dates and
        # values, sort on dates, and then un-zip (i.e. zip again) to get
        # sorted dates and values.
        # For more on this Deep Python(TM) expression, see here:
        # https://www.kite.com/python/answers/how-to-sort-two-lists-together-in-python
        return tuple(
            tuple(list(val) for val in zip(*sorted(zip(*column))))
            for column in data)

    @staticmethod
    def _add_column(data):
        """ Adds an empty column to `data`. MUTATES `data`! """
        # Append a pair of empty lists:
        data.append(([],[]))

    def _add_entry(self, column, date, val):
        """ Adds an entry for value `val` at date `date` to `column`. """
        # Insert parallel values into the two lists of `column`:
        column[0].append(date)
        column[1].append(self._convert_entry(val))

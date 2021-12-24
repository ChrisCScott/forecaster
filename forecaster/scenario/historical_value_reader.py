""" Provides tools for reading historical returns from CSV files. """

import csv
from collections import OrderedDict
import datetime
import dateutil
from forecaster.scenario.util import (
    values_from_returns, returns_from_values,
    values_from_returns_array, returns_from_values_array)
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
        as_arrays (bool): If `True`, each column of data is represented
            as a `(dates, values)` tuple, where `dates` and `values`
            are both lists. If `False`, each colum of data is
            represented as a `{date: value}` mapping.
            Optional; defaults to `False` (i.e. mapping behaviour)
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

    def __init__(self, filename=None, returns=None, *, high_precision=None):
        # Set up high-precision support:
        super().__init__(high_precision=high_precision)
        # Declare member attributes:
        self.data = None
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
        # scenarios:
        self.data = tuple(
            OrderedDict(sorted(column.items())) for column in data)
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
    def _infer_returns(values):
        """ Infers whether `values` is likely a sequence of returns.

        `values` is presumed to be returns-values if:
            - Any value in `values` is negative
            - More than half of the non-zero values in `values` are
              less than 1.
        Otherwise, `values` is presumed to represent portfolio values.

        Returns:
            (bool): `True` if `values` is inferred to be a sequence of
            returns, `False` otherwise.
        """
        # Check for negative values, infer returns if any are found:
        if any(val < 0 for val in values.values()):
            return True
        # Find the proportion of values that look like percentages
        # (i.e. < 1), infer returns if >50% do look like percentages:
        non_zero_values = tuple(val for val in values.values() if val != 0)
        num_small = sum(1 for val in non_zero_values if val < 1)
        if num_small / len(non_zero_values) > 0.5:
            return True
        # Otherwise, infer that these are portfolio values, not returns:
        return False

    def _convert_entry(self, entry):
        """ Converts str entry to a numeric type. """
        # Remove leading/trailing spaces and commas:
        entry = entry.strip(' ').replace(',', '')
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
                    data.append({})
                data[i][date] = self._convert_entry(entry)
        return data

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

    def __init__(self, filename=None, returns=None, *, high_precision=None):
        # Set up class (but don't read in the file yet!)
        super().__init__(returns=None, high_precision=high_precision)
        # Read in the file using this class's overloaded `read`
        if filename is not None:
            self.read(filename, returns=returns)

    def read(self, filename, returns=None):
        """ Reads in a CSV file with dates and portfolio values.

        See docs for `HistoricalValueReader.__init__` for the format of
        the CSV file.
        """
        # If it's a relative path, resolve it to the `data/` dir:
        filename = resolve_data_path(filename)
        # Read in the CSV file:
        # (newline='' is recommended for file objects. See:
        # https://docs.python.org/3/library/csv.html#id3)
        with open(filename, encoding='utf-8', newline='') as file:
            reader = self._get_csv_reader(file)
            data = self._get_data_from_csv_reader(reader)
        # `data` is a tuple of N lists (for N-1 non-date columns).
        # We want to sort all of the columns by date.
        # To do this, we can zip the columns together, sort on the first
        # element of the N-tuples, re-zip the N-tuples into lists.
        # For more on this Deep Python(TM) expression, see here:
        # https://www.kite.com/python/answers/how-to-sort-two-lists-together-in-python
        sorted_data = tuple(list(elm) for elm in zip(*sorted(zip(*data))))
        # TODO: Revisit this. `_get_data_from_csv_reader` should
        # probably return 2-tuples of (dates, values) with None values
        # omitted. We can then sort each column independently.
        # Whereas this logic assumes we're reciving each column verbatim
        # (incl. the dates column) and need to wrap it into 2-tuples.
        # That would be fine, but this only makes sense if every column
        # has the same dates - if we allow omitted dates, then we should
        # generate a different dates array for each non-date column,
        # which is best done in `_get_data_from_csv_reader`
        dates = sorted_data[0]
        self.data = tuple((dates, column) for column in sorted_data[1:])
        # Find out if we're reading returns (vs. portfolio values) and
        # store that information for later processing:
        if returns is None and data:  # Don't try for empty dataset
            returns = self._infer_returns(data[0])
        self._returns_values = returns

    def returns(self, convert=None):
        """ Returns `data` as arrays of returns values. """
        # Convert data if the user hasn't hinted that we're reading in
        # returns-formatted values:
        if convert is None:
            convert = not self._returns_values
        if convert:
            dates = self.data[0]
            # TODO: Revise this to reflect the actual format of
            # self.data, which is an array of 2-tuples (and not an array
            # of lists starting with the list of dates, as this assumes)
            return tuple(
                returns_from_values_array(
                    dates, column, high_precision=self.high_precision)
                for column in self.data[1:])
        return self.data

    def values(self, convert=None):
        """ Returns `data` as a dict of portfolio values. """
        # Convert data if the user has hinted that we're reading in
        # returns-formatted values:
        if convert is None:
            convert = self._returns_values
        if convert:
            dates = self.data[0]
            # TODO: Revise this to reflect the actual format of
            # self.data, which is an array of 2-tuples (and not an array
            # of lists starting with the list of dates, as this assumes)
            return tuple(
                values_from_returns_array(dates, column)
                for column in self.data)
        return self.data

    @staticmethod
    def _infer_returns(values):
        """ Infers whether `values` is likely a sequence of returns.

        `values` is presumed to be returns-values if:
            - Any value in `values` is negative
            - More than half of the non-zero values in `values` are
              less than 1.
        Otherwise, `values` is presumed to represent portfolio values.

        Returns:
            (bool): `True` if `values` is inferred to be a sequence of
            returns, `False` otherwise.
        """
        # Check for negative values, infer returns if any are found:
        if any(val < 0 for val in values):
            return True
        # Find the proportion of values that look like percentages
        # (i.e. < 1), infer returns if >50% do look like percentages:
        non_zero_values = tuple(val for val in values if val != 0)
        num_small = sum(1 for val in non_zero_values if val < 1)
        return num_small / len(non_zero_values) > 0.5

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
                    # For the array-based implementation, add a tuple
                    # with two lists. The first is for dates, the second
                    # is for values:
                    data.append(([],[]))
                data[i][0].append(date)
                data[i][1].append(self._convert_entry(entry))
        return data

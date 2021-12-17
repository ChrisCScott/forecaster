""" Provides tools for reading historical returns from CSV files. """

import csv
from collections import OrderedDict
import datetime
import dateutil
from forecaster.scenario.util import (
    regularize_returns, values_from_returns, returns_from_values)
from forecaster.utility import resolve_data_path, HighPrecisionHandler

# Assume incomplete dates are in the first month/day:
DATE_DEFAULT = datetime.datetime(2000, 1, 1)
INTERVAL_ANNUAL = dateutil.relativedelta.relativedelta(years=1)

class HistoricalValueReader(HighPrecisionHandler):
    """ Reads historical value data from CSV files.

    This reads in a UTF-8 encoded CSV file with the following format:

    | Date Header | Value Header | Value Header | ...
    |-------------|--------------|--------------|
    | date        | 100.0        | 100.0        | ...

    The header row is optional and is not used. This should generally be
    identified correctly, as long as your header isn't a number.

    The first column must be dates. Data in the date column is converted
    from `str` to `datetime.datetime` via `dateutils.parse`. Non-empty
    data in value columns is converted to `float` or to a high-precision
    numeric type (if `high_precision` is provided.)

    Arguments:
        filename (str): The filename of a CSV file to read. The file
            must be UTF-8 encoded. Relative paths will be resolved
            within the package's `data/` directory.
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` or `str` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Attributes:
        values (tuple[OrderedDict[date, HighPrecisionOptional]]):
            A sequence of ordered mappings of dates to portfolio values,
            each element of the sequence corresponding to one (non-date)
            column of data.
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

    def annualized_returns(self, convert=None, start_date=None):
        """ Returns `data` as a dict of annual returns values.

        The returns values start on `start_date` or, if that is not
        provided, on the first date in `self.data`. Dates are spaced
        one year apart.

        Arguments:
            convert (Optional[bool]): If `True`, columns of `self.data`
                are treated as containing portfolio values, which must
                be converted to returns. Optional. If not provided,
                the instance's default behaviour will be used.
        """
        # Convert data if the user hasn't hinted that we're reading in
        # returns-formatted values:
        if convert is None:
            convert = not self._returns_values
        if convert:
            # Generate
            return tuple(
                regularize_returns(
                    column, INTERVAL_ANNUAL,
                    date=start_date, high_precision=self.high_precision)
                for column in self.data)
        return self.data

    def returns_samples(self, convert=None, interval=INTERVAL_ANNUAL):
        """ Returns the return over `interval` for each date.

        The result of this method is _not_ a sequence of returns that
        can be converted to a sequence of portfolio values. The dates
        in the returned data are the same as in `self.data`, but each
        return value is the return over `interval` for the given date.

        So, for example, if you have a sequence of two years of daily
        datapoints and provide an interval of one year (the default),
        the resulting dict will have ~365 date-keys mapping to 365
        values representing the return from that date over the following
        year. This is useful for samplers, but dangerous to call
        `values_from_returns` on.
        """

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
        """ Converts to str entry to a numeric type. """
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
        dialect = sniffer.sniff(sample)
        # We want to discard the header, if the file has one.
        # Sniffer.has_header is unreliable, so test manually too.
        has_header = sniffer.has_header(sample)
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
        # Return to beginning of file again for later processing:
        file.seek(0)
        reader = csv.reader(file, dialect=dialect)
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

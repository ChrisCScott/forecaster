""" Samplers for generating time-series data for Scenario objects. """

from itertools import product, pairwise, islice
import numpy
from forecaster.scenario.util import (
    return_over_period, regularize_returns, infer_interval, get_date_index,
    mapping_to_arrays, get_first_return_period)
from forecaster.utility import HighPrecisionHandler

def get_values(array_pair):
    """ Gets a list of values from a column of data """
    return array_pair[1]

def get_dates(array_pair):
    """ Gets a list of dates from a column of data """
    return array_pair[0]

class SamplerABC(HighPrecisionHandler):
    """ Abstract base class for generating samples from data. """

    def __init__(self, data, *, high_precision=None):
        super().__init__(high_precision=high_precision)
        # Convert `data` to arrays if needed:
        self.data = mapping_to_arrays(data)

    def sample(self, num_samples=None, sample_length=None):
        """ Generates `num_samples` samples.

        Arguments:
            num_samples (int | None): The number of samples to generate.
                Optional. If omitted, a single sample is generated.
            sample_length (int | None): The number of values to
                generate for each variable. Optional. If omitted, a
                single value is generated for each variable.

        Returns:
            (tuple[HighPrecisionOptional,...] |
            list[tuple[HighPrecisionOptional,...]]): A sample of `N`
            variables (where `N` is the size of `data`), as an N-tuple.
            Or, if `num_samples` is passed, an array of `num_samples`
            samples.
        """
        raise NotImplementedError('Cannot call ABC method.')

    def _align_data(self, data):
        """ Aligns data by dates.

        Arguments:
            data (list[tuple[list[datetime], list[HighPrecisionOptional]]]):
                Two or more columns of date:value pairs.

        Returns:
            (list[list[HighPrecisionOptional]] | None): A dataset of
            values (dates are omitted) where each value at the `i`th
            index of a column corresponds to the same date as the values
            at the `i`th indices of all other columns. That is, a matrix
            where columns correspond to variables and rows correspond to
            dates.
        """
        # We want to find if there's any overlapping period in the
        # dataseries, so expend the dataseries to include the starting
        # date for their first return periods:
        expanded_dates = [
            # Include the start of the first return period:
            [get_first_return_period(get_dates(column))[0]] + get_dates(column)
            for column in data]
        # Get the range of overlapping dates:
        min_date = max(min(column) for column in expanded_dates)
        max_date = min(max(column) for column in expanded_dates)
        # We can't meaningfully align data if columns don't overlap:
        if min_date >= max_date:
            return None
        # Use dates in the range (min_date, max_date) from the sparser
        # dataset. This reduces the amount of interpolation, which is
        # good because interpolating lots of points into a sparse
        # dataset to compare with a dense dataset will degrade measures
        # of covariance.
        dates = min(
            ([  # Get all dates in range (exclusive) for each column
                date for date in column if min_date < date < max_date]
            for column in expanded_dates),
            #  Select the shorted list of dates
            key=len)
        # Ensure that the bounds of the range are represented:
        dates.insert(0, min_date)
        dates.append(max_date)
        # Get a value for each period and build a 2xn array for the `n` dates:
        aligned_data = [
            (
                dates[1:],  # All dates except the first date
                list(
                    return_over_period(
                        column, start_date, end_date,
                        high_precision=self.high_precision)
                    for (start_date, end_date) in pairwise(dates)))
            for column in data]
        return aligned_data

def _precision_convert_arrays(arrays, high_precision):
    """ Converts values of an n-dimensional array to high-precision. """
    # If this is a list of lists, recurse:
    if arrays.ndim > 1:
        return list(
            _precision_convert_arrays(column, high_precision)
            for column in arrays)
    return list(high_precision(val) for val in arrays)

class MultivariateSampler(SamplerABC):
    """ Generates samples of returns from historical data.

    This class models a distribution for an arbitrary number of
    variables based on historical data and generates samples from that
    distribution. Variables are not presumed to be i.i.d.; covariance
    is measured and used when generating samples.

    Statistics determined from historical data can be selectively
    overridden by providing `means` and `covariances` args. If only
    some variables' statistics should be overridden, simply use `None`
    values for non-overridden variables' values.

    Arguments:
        data (list[dict[datetime, HighPrecisionOptional]] |
            list[tuple[list[datetime], list[HighPrecisionOptional]]]):
            An array of size `N` of data for each of `N` variables. The
            element at index `i` is a dataset of date: value pairs (
            either as a dict or as parallel lists) for the `i`th
            variable.
            Data must be in sorted order. If using dicts in Python<3.6,
            use `OrderedDict` to preserve order.
        means (list[HighPrecisionOptional]): An array of mean values for
            the variables, where the `i`th element is the mean for the
            `i`th variable. These values will be used if provided
            instead of mean statistics generated from `data`. (`None`
            values are ignored.) Optional.
        covariances (list[list[HighPrecisionOptional]]): A 2D covariance
            matrix for the variables being sampled. These values will be
            used if provided instead of covariance statistics generated
            from `data`. (`None` values are ignored.) Optional.
        high_precision (Callable[[float], HighPrecisionType] | None): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Attributes:
        data (list[tuple[list[datetime], list[HighPrecisionOptional]]]):
            An array of size `N` of data for each of `N` variables. The
            element at index `i` is a pair of lists `(dates, values)`
            representing a series of date-value pairs for the `i`th
            variable.
        means (list[HighPrecisionOptional]): An array of mean values for
            the variables, where the `i`th element is the mean for the
            `i`th variable.
        covariances (list[list[HighPrecisionOptional]]): A 2D covariance
            matrix for the variables. (This is calculated via
            `numpy.cov` using `ddof=0` for compatibility.)
    """

    # Allows for easy patching by unit tests.
    random = numpy.random.default_rng()

    def __init__(
            self, data, means=None, covariances=None, high_precision=None):
        # Initialize `data` and `high_precision` attrs:
        super().__init__(data, high_precision=high_precision)
        # Initialize member attributes:
        self.means = self._generate_means(self.data, means)
        self.covariances = self._generate_covariances(self.data, covariances)

    def sample(self, num_samples=None, sample_length=None):
        """ Generates `num_samples` multivariate samples.

        Arguments:
            num_samples (int | None): The number of multivariate samples
                to generate. Optional. If omitted, a single sample is
                generated.
            sample_length (int | None): The number of values to generate
                for each variable in each sample. Optional. If omitted,
                a single value is generated.

        Returns:
            (tuple[HighPrecisionOptional,...] |
            list[tuple[HighPrecisionOptional,...]] |
            list[tuple[list[HighPrecisionOptional],...]]):
            A sample of `N` variables (where `N` is the size of `data`),
            or (if `num_samples` is provided) a list of `num_samples`
            samples. If `sample_length` is provided, each sample
            includes a list of length `sample_length` for each variable.
        """
        if num_samples is None and sample_length is None:
            size = None
        elif num_samples is not None and sample_length is None:
            size = num_samples
        elif sample_length is not None and num_samples is None:
            size = sample_length
        else:
            size = (num_samples, sample_length)
        # Get random values for each variable that we model, based on
        # the means and covariances that we found in the data (or which
        # the user provided, if they chose to do so.)
        samples = self.random.multivariate_normal(
            self.means, self.covariances, size=size)
        # numpy.multivariate_normal returns an array with axes
        # (num_samples, sample_length, N), where N is the number of
        # variables. We want to swap the last two axes.
        if sample_length is not None:
            samples = samples.swapaxes(samples.ndim - 1, samples.ndim - 2)
        # Convert to list(s) of high precision values if appropriate:
        # (This also converts to list)
        if self.high_precision is not None:
            return _precision_convert_arrays(samples, self.high_precision)
        # If no high-precision conversion needed, convert to list:
        return samples.tolist()

    @staticmethod
    def _generate_means(data, means=None):
        """ Generates missing means for each variable in `data`.

        Where `means` provides a value, that is used. Only `None` values
        in `means` are inferred from `data`.

        Arguments:
            data (list[tuple[list[datetime], list[HighPrecisionOptional]]]):
                An array of size `N` of data for each of `N` variables.
                The element at index `i` is a pair of lists
                `(dates, values)` representing a series of date-value
                pairs for the `i`th variable. Each pair of lists must
                be in sorted order (by date, ascending).
            means (list[HighPrecisionOptional]): An array of mean values
                for the variables, where the `i`th element is the mean
                for the `i`th variable. These values will be used if
                provided instead of mean statistics generated from
                `data`. (`None` values are ignored.) Optional.
        """
        # Use means from `data` if no means are expressly provided:
        if means is None or not means:
            return list(numpy.mean(get_values(column)) for column in data)
        # Otherwise, fill in `None` values from `means` based on `data`:
        return list(
            means[i] if means[i] is not None
            else numpy.mean(get_values(column))
            for (i, column) in enumerate(data))

    def _generate_covariances(self, data, covariances=None):
        """ Generates missing covariances for each variable in `data`.

        Any `None` entries will be filled in based on covariances
        extracted from `data`. Where no data is available, covariance
        will be set to 0.

        Args:
            data (list[tuple[list[datetime], list[HighPrecisionOptional]]]):
                An array of size `N` of data for each of `N` variables.
                The element at index `i` is a pair of lists
                `(dates, values)` representing a series of date-value
                pairs for the `i`th variable. Each pair of lists must
                be in sorted order (by date, ascending).
            covariances (Optional[tuple[Optional[tuple[
                Optional[HighPrecisionOptional]]]]]):
                A two-dimensional array of (co)variance values,
                where data[index] and variances[index] describe the same
                variable. Optional. Each first- and second-dimensional
                element is optional as well (e.g. `covariance[i]` or
                `covariance[i][j]` may be `None`.)

        Returns:
            (list(list(HighPrecisionOptional))): A two-dimensional
            array of covariance values.
        """
        # Find the caovariance matrix for the data provided.
        # Use `ddof=0` to get `numpy.cov` to agree with `numpy.var`
        # See here for more:
        # https://stackoverflow.com/questions/21030668/why-do-numpy-cov-diagonal-elements-and-var-functions-have-different-values

        # Build an n*n array to slot covariance coefficients into:
        cov_matrix = numpy.zeros((len(data), len(data)), dtype=int).tolist()
        for (i, column1) in enumerate(data):
            # Covariance matrixes are triangular, so only calculate
            # covariance coefficients for (i,j) where j<=i:
            for (j, column2) in enumerate(islice(data, i+1)):
                # Prefer entries in `covariances`:
                if (
                        covariances is not None and
                        covariances[i] is not None and
                        covariances[i][j] is not None):
                    cov_matrix[i][j] = covariances[i][j]
                    cov_matrix[j][i] = covariances[j][i]
                    continue
                # Otherwise, calculate covariance between columns i/j:
                aligned_data = [
                    get_values(column)  # we don't need dates for `cov`
                    for column in self._align_data((column1, column2))]
                # If there's no aligned data, assume no covariance:
                if aligned_data is None:
                    continue
                # If there is aligned data, find the covariance:
                if self.high_precision is None:
                    # This returns a 2x2 covariance matrix; the
                    # covariance coefficient for the two variables is
                    # found in either one of the off-diagonal elements:
                    cov_2x2 = numpy.cov(aligned_data, ddof=0)
                    cov = cov_2x2[0][1]
                    # (This works for the case i=j as well. Usually we'd
                    # refer to the element at [0][0] to get the
                    # autocorrelation of column i, but when i=j all
                    # elements are identical so we can use any one.)
                else:
                    # Support high-precision numeric types:
                    # numpy doesn't support custom numeric types; we
                    # don't need exact values when sampling anyways, so
                    # "support" high-precision types by casting them to
                    # `float`, calling numpy, and then casting back:
                    array = numpy.array(aligned_data).astype(numpy.dtype(float))
                    cov_2x2 = numpy.cov(array, ddof=0).astype(object)
                    cov = self.high_precision(cov_2x2[0][1])
                cov_matrix[i][j] = cov
                cov_matrix[j][i] = cov
        return cov_matrix

class WalkForwardSampler(SamplerABC):
    """ Generates walk-forward samples of returns from historical data.

    This class generates sequences of returns for any number of
    variables based on historical data based on a "walk-forward"
    simulation. Returns are taken from the historical data, with the
    sequence of returns retained. The starting date for each
    walk-forward simulation is randomized.

    By default, a walk-forward sequence is generated for each variable
    independently. Sequences for each variable can be synchronized (i.e.
    so that their returns remained aligned as in the historical data)
    via the `synchronize` argument.

    By default, walk-forward sequences will not extend beyond the end
    of historical data - e.g. so a 50-year walk-forward sequence with
    100 years of return data could only start in years 1-50. Sequences
    can be permitted to wrap around from the end of historical returns
    back to the beginning via the `wrap_data` argument.

    Arguments:
        data (list[dict[datetime, HighPrecisionOptional]] |
            list[tuple[list[datetime], list[HighPrecisionOptional]]]):
            An array of size `N` of data for each of `N` variables. The
            element at index `i` is a dataset of date: value pairs (
            either as a dict or as parallel lists) for the `i`th
            variable.
            Data must be in sorted order. If using dicts in Python<3.6,
            use `OrderedDict` to preserve order.
        synchronize (bool): If `True`, walk-forward sequences for each
            variable will be synchronized so that they each start on
            the same date. Optional, defaults to `False`.
        wrap_data (bool): If `True`, walk-forward sequences may be
            generated by wrapping around from the end of historical
            data back to the beginning. Optional, defaults to `False`.
        interval (relativedelta | None): If provided, value of `data`
            are interpreted as returns (i.e. percentage
            increase/decrease relative to a previous timestep) and are
            recalculated over successive time periods of length
            `interval` starting on the first date for each variable. For
            annual returns, you can provide `INTERVAL_ANNUAL` from this
            module. See `scenario.util.regularize_returns` for more
            details on this conversion.
            Optional; if not provided, returns are sampled as-is.
        high_precision (Callable[[float], HighPrecisionType] | None): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Attributes:
        data (list[tuple[list[datetime], list[HighPrecisionOptional]]]):
            An array of size `N` of data for each of `N` variables. The
            element at index `i` is a pair of lists `(dates, values)`
            representing a series of date-value pairs for the `i`th
            variable.
        synchronize (bool): If `True`, walk-forward sequences for each
            variable will be synchronized so that they each start on
            the same date.
        wrap_data (bool): If `True`, walk-forward sequences may be
            generated by wrapping around from the end of historical
            data back to the beginning.
        interval (relativedelta | None): A period over which the return
            for each date is calculated.
    """

    # Allows for easy patching by unit tests:
    random = numpy.random.default_rng()
    # Constant used to determine when to sample variables independently
    # (with potential duplication) vs. attempting to produce unique
    # samples
    SAMPLE_THRESHOLD = 100

    def __init__(
            self, data, synchronize=False, wrap_data=False, interval=None,
            high_precision=None):
        # Init private property attrs
        self._data = None
        self._data_synchronized = None
        self._synchronize = None
        # Init `data` and `high_precision` via superclass
        # (do this _after_ initting private property attrs)
        super().__init__(data, high_precision=high_precision)
        # Init attrs
        self.synchronize = synchronize
        self.wrap_data = wrap_data
        self.interval = interval

    @property
    def data(self):
        """ Matrix of data values """
        if self.synchronize:
            # Synchronize data lazily (i.e. when requested), since in
            # theory the user could change the value of `synchronize`:
            if self._data_synchronized is None:
                self._data_synchronized = self._align_data(self._data)
            return self._data_synchronized
        return self._data

    @data.setter
    def data(self, val):
        """ Sets `data` attr """
        # Convert `data` to arrays:
        self._data = mapping_to_arrays(val)
        # Clear synchronized data cache; we'll re-generate it lazily
        self._data_synchronized = None

    @property
    def synchronize(self):
        """ Matrix of data values """
        return self._synchronize

    @synchronize.setter
    def synchronize(self, val):
        """ Sets `synchronize` attr """
        self._synchronize = val
        # Clear synchronized data cache; we'll re-generate it lazily
        self._data_synchronized = None

    def sample(self, num_samples=None, sample_length=None):
        """ Generates walk-forward time-series data.

        Samples are generated differently depending on the number of
        samples, the size of the dataset, and whether sample dates are
        synchronized.

        If the `synchronized` attribute is set to `True`, then
        walk-forward sequences for each variable in a sample will use
        the same dates. For instance, if one variable has returns
        sampled from 2000-1-1 for its first value, all of the variables
        will have returns sampled from 2000-1-1 for their first values.

        Otherwise, start dates for walk-forward sequences are chosen
        indepedently for each variable. This is done in various ways:
            1. If `num_samples` is not provided, 1 sample is generated.
            2. If the number of possible samples is very large (by
               default, >100 times larger than `num_samples`; this is
               customizable via the `SAMPLE_THRESHOLD` attr) then
               samples are not guaranteed to be unique (although
               duplicate samples should be rare).
            3. If the number of possible samples is just moderately
               larger than `num_samples`, then samples are guaranteed
               to be unique.
            4. If the number of possible samples is no larger than
               `num_samples`, all possible samples are generated.
               There may be fewer samples than `num_samples`, as there
               is no duplication of samples.

        Arguments:
            num_samples (int | None): The number of walk-forward samples
                to generate. Optional. If omitted, a single sample is
                generated.
            sample_length (int | None): The length of each sampled
                walk-forward sequence.

        Returns:
            (tuple[HighPrecisionOptional,...] |
            list[tuple[HighPrecisionOptional,...]]): A sample of `N`
            walk-forward sequences (where `N` is the size of `data`),
            as an N-tuple.
            Or, if `num_samples` is passed, an array of up to
            `num_samples` samples.
        """
        # Find `num_samples` valid N-tuples of valid start dates:
        starts = self._get_start_combos(sample_length, num_samples)
        # Build a sequence of returns for each set of start dates:
        samples = list(
            # Get the walk-forward sequence of returns for each asset
            # class (this is None for any classes with no data):
            list(
                self._get_walk_forward_sequence(
                    # pylint: disable=unsubscriptable-object
                    # Pylint seems to be confused about `start`
                    index, sample_starts, sample_length)
                    # pylint: enable=unsubscriptable-object
                for index in range(len(sample_starts)))
            for sample_starts in starts)
        # Don't wrap the samples in a list if we're only generating one
        # sample:
        if num_samples is None:
            return samples[0]
        return samples

    def _get_walk_forward_sequence(self, index, starts, walk_length):
        """ Gets sequence of annual returns starting on `start_date` """
        # Unpack variables from `data` for efficient iteration:
        start_date = starts[index]
        dates = self.data[index][0]
        returns = self.data[index][1]
        # `start_date` can be None, so handle that first:
        if start_date is None:
            return None
        # Adjust dates/returns to the selected interval if provided:
        if self.interval is not None:
            dates, returns = regularize_returns(
                (dates, returns), self.interval,
                date=start_date, high_precision=self.high_precision)
        # Get list of dates, starting from `start_date` (up to `walk_length`):
        start_index = get_date_index(dates, start_date)
        sequence = returns[start_index:start_index + walk_length]
        # Extend the list if we're wrapping to ensure it's long enough:
        if self.wrap_data:
            while len(sequence) < walk_length:
                sequence += returns
        # Trim the sequence to just `walk_length`:
        return sequence[0:walk_length]

    def _get_start_combos(self, walk_length, num_samples):
        """ Get tuples of valid starts for all columns of data.

        Returns:
            (numpy.array): A 2D array of start dates. Each column is a
            sample and has the same length as `data` (e.g. if `data`
            covers 4 variables then each sample is of length 4).
        """
        # Time and space complexity are important in this method.
        #
        # We are operating over a 2D matrix of dates, `data`, of approx.
        # size `n*m`, where `n` is the number of columns (i.e. the
        # number of variables represented in the data) and `m` is the
        # number of observations/dates for each variable (). (Technically
        # the variables can have different numbers of observations - let
        # m be the upper bound on these, i.e. the length of the longest
        # column).
        #
        # If we're synchronizing dates, then there are only O(m)
        # possible samples, which can be generated with O(m*n)
        # space/time complexity. That is acceptable.
        #
        # If we are not synchronizing dates, then there are O(m^n)
        # possible samples. Even modest real-world datasets are
        # intractable if we try to construct a list of all possible
        # combinations of start dates. So we cannot build a list of
        # dates and then sample from it - we need to sample `num_sample`
        # indexes from a distribution and transform those indexes into
        # samples of start-date combinations.
        #
        # The simplest way to deal with the unsynchronized case is
        # simply to sample from each axis independently. This brings
        # time/space complexity down to `O(n*m)`, but also does not
        # guarantee that each sample will be unique.
        #
        # It is possible to obtain unique samples (via the
        # `replace=False` arg to `self.random.choice`), which might be
        # desirable for small datasets, e.g. those where `num_samples`
        # is smaller than `c*m^n` for some small c (2? 100?).
        # For now, we avoid the additional code complexity and just
        # independently sample for each variable (in the unsynchronized
        # case).

        # Get valid starts for each variable:
        valid_starts = list(
            self._get_valid_starts(returns, walk_length)
            for returns in self.data)
        # If we're synchronizing start dates between variables, use the
        # same dates for each variable:
        if self.synchronize:
            # Pick any column of data and find the dates that are in
            # all the columns. (This has complexity O(N*m) where m is
            # the length of the longest column in `data`)
            base = valid_starts[0]
            return [
                [date] * len(self.data) for date in base
                if all(date in column for column in valid_starts)]
        # If we're not synchronizing dates, sample valid dates for each
        # column (which we do differently depending on the size of the
        # dataset relative to the number of samples, as described above)
        max_combos = numpy.prod([len(column) for column in valid_starts])
        if num_samples is None:
            # Select 1 sample if `num_samples` not provided:
            starts = numpy.array(  # rows correspond to variables
                [self.random.choice(column, 1) for column in valid_starts])
            starts = starts.transpose()  # rows correspond to samples
        elif max_combos > self.SAMPLE_THRESHOLD * num_samples:
            # For large datasets, sample independently:
            starts = numpy.array(list(  # rows correspond to variable
                self.random.choice(column, num_samples)
                for column in valid_starts))
            starts = starts.transpose()  # rows correspond to samples
        elif max_combos > num_samples:
            # For medium-sized datasets, where more than `num_samples`
            # samples are possible (but not, like, _way_ more),
            # pick unique combos randomly:
            start_combos = list(product(*valid_starts))
            starts = self.random.choice(
                start_combos, num_samples, replace=False)
        else:
            # If we can't make `num_samples` scenarios, use them all:
            starts = numpy.array(list(product(*valid_starts)))
            # Use random order, just in case the client only iterates
            # over a portion of the results:
            self.random.shuffle(starts)
        return starts

    def _get_valid_starts(self, returns, walk_length):
        """ Get valid starts for a single column of data. """
        dates = get_dates(returns)
        # All dates work if we're wrapping:
        if self.wrap_data:
            return dates
        # If there's no `interval`, get all the dates that are at
        # least `walk_length` from the end.
        if self.interval is None:
            last_index = len(dates)-walk_length+1
            return dates[0:last_index]
        # If there is an `interval`, treat this as a series of returns.
        # We want to cover only dates that (a) are far enough into the
        # time period covered by `returns` to capture a period of length
        # `interval` beforehand (use `_infer_interval`) and (b) are far
        # enough from the end of the time period to leave enough room
        # to fit a walk-forward sequence afterwards:
        start_of_returns = min(dates) - infer_interval(dates)
        first_date = start_of_returns + self.interval
        last_date = max(dates) - (self.interval * (walk_length - 1))
        valid_dates = list(
            date for date in dates if first_date <= date <= last_date)
        # The above gets all dates _already represented as keys in the
        # data_, but there's one special date we want to include: the
        # first valid date (which might need to be interpolated if
        # `interval` is different from the interval between keys). This
        # represents the longest possible sequence, which we want to be
        # sure gets included:
        if first_date not in valid_dates:
            valid_dates.insert(0, first_date)
        return valid_dates

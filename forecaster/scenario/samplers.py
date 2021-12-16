""" Samplers for generating time-series data for Scenario objects. """

from itertools import product, pairwise
from dateutil.relativedelta import relativedelta
import numpy
from forecaster.scenario.util import (
    return_over_period, regularize_returns, _infer_interval)
from forecaster.utility import HighPrecisionHandler

class MultivariateSampler(HighPrecisionHandler):
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
        data (list[dict[datetime, HighPrecisionOptional]]): An array
            of size `N` of data for each of `N` variables. The element
            at index `i` is a dataset of date: value pairs for the `i`th
            variable.
        means (list[HighPrecisionOptional]): An array of mean values for
            the variables, where the `i`th element is the mean for the
            `i`th variable. These values will be used if provided
            instead of mean statistics generated from `data`. (`None`
            values are ignored.) Optional.
        covariances (list[list[HighPrecisionOptional]]): A 2D covariance
            matrix for the variables being sampled. These values will be
            used if provided instead of covariance statistics generated
            from `data`. (`None` values are ignored.) Optional.

    Attributes:
        data (list[dict[datetime, HighPrecisionOptional]]): An array
            of size `N` of data for each of `N` variables. The element
            at index `i` is a dataset of date: value pairs for the `i`th
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
        super().__init__(high_precision=high_precision)
        # Initialize member attributes:
        self.data = data
        self.means = self._generate_means(data, means)
        self.covariances = self._generate_covariances(data, covariances)

    def sample(self, num_samples=None):
        """ Generates `num_samples` multivariate samples.

        Arguments:
            num_samples (int): The number of multivariate samples to
                generate. Optional. If omitted, a single sample is
                generated.

        Returns:
            (tuple[HighPrecisionOptional,...] |
            list[tuple[HighPrecisionOptional,...]]): A sample of `N`
            variables (where `N` is the size of `data`), as an N-tuple.
            Or, if `num_samples` is passed, an array of `num_samples`
            samples.
        """
        # Get random values for each variable that we model, based on
        # the means and covariances that we found in the data (or which
        # the user provided, if they chose to do so.)
        samples = self.random.multivariate_normal(
            self.means, self.covariances, size=num_samples)
        # Convert numpy.array to list:
        if num_samples is not None:
            return list(tuple(sample) for sample in samples)
        return tuple(samples)

    @staticmethod
    def _generate_means(data, means=None):
        """ Generates missing means for each variable in `data`.

        Where `means` provides a value, that is used. Only `None` values
        in `means` are inferred from `data`.
        """
        size = len(data)
        # Use means from `data` if no means are expressly provided:
        if means is None or not means:
            return list(numpy.mean(list(var.values())) for var in data)
        # Otherwise, fill in `None` values from `means` based on `data`:
        return list(
            means[i] if means[i] is not None
            else numpy.mean(list(data[i].values()))
            for i in range(size))

    def _generate_covariances(self, data, covariances=None):
        """ Generates missing covariances for each variable in `data`.

        Any `None` entries will be filled in based on covariances
        extracted from `data`. Where no data is available, covariance
        will be set to 0.

        Args:
            data (tuple[Optional[OrderedDict[datetime,
                HighPrecisionOptional]]]):
                An array of date-value sequences (each in sorted order).
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
        data_array = list(list(column.values()) for column in data)
        # Support high-precision numeric types:
        if self.high_precision is not None:
            # We don't need exact values when sampling, so support
            # high-precision types by casting them to `float`:
            array = numpy.array(data_array).astype(numpy.dtype(float))
            cov_matrix = numpy.cov(array, ddof=0).astype(object)
            # Cast back to high-precision type on return:
            for (index, val) in numpy.ndenumerate(cov_matrix):
                cov_matrix[index] = self.high_precision(val)
        else:
            cov_matrix = numpy.cov(data_array, ddof=0)
        # If no `covariances` was provided, nothing left to do:
        if covariances is None:
            return list(list(column) for column in cov_matrix)
        # Otherwise, overwrite each entry of `cov_matrix` if there's a
        # corresponding non-None entry in `covariances`:
        for (i, column) in enumerate(covariances):
            # Skip empty columns:
            if column is None:
                continue
            for (j, entry) in enumerate(column):
                if entry is not None:
                    cov_matrix[i][j] = entry
        # Cast numpy.ndarry back to a familiar type:
        return list(list(column) for column in cov_matrix)

    @staticmethod
    def _align_data(data1, data2):
        """ Turns dicts of date-keyed data into arrays of aligned data. """
        # Get the range of overlapping dates:
        min_date = max(min(data1), min(data2))
        max_date = min(max(data1), max(data2))
        # Use the dates in the first dataset, limited to dates within the
        # range of overlapping dates:
        dates = list(
            date for date in data1 if date >= min_date and date <= max_date)
        # If there's not enough overlapping data, assume no covariance:
        if len(dates) < 2:  # Need 2 vals for each var to get 2x2 covariance
            return ((0,0), (0,0))
        # Get a value for each period and build a 2xn array for the `n` dates:
        aligned_data = tuple(
            list(
                return_over_period(column, start_date, end_date)
                for (start_date, end_date) in pairwise(dates))
            for column in (data1, data2))
        return aligned_data

class WalkForwardSampler:
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
        data (list[dict[datetime, HighPrecisionOptional]]): An array
            of size `N` of data for each of `N` variables. The element
            at index `i` is a dataset of date: value pairs for the `i`th
            variable.
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

    Attributes:
        data (list[dict[datetime, HighPrecisionOptional]]): An array
            of size `N` of data for each of `N` variables. The element
            at index `i` is a dataset of date: value pairs for the `i`th
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

    def __init__(
            self, data, synchronize=False, wrap_data=False, interval=None):
        self.data = data
        self.synchronize = synchronize
        self.wrap_data = wrap_data
        self.interval = interval

    def sample(self, walk_length, num_samples=None):
        """ Generates walk-forward time-series data.

        Arguments:
            walk_length (int): The length of each sampled walk-forward
                sequence.
            num_samples (int): The number of walk-forward samples to
                generate. Optional. If omitted, a single sample is
                generated.

        Returns:
            (tuple[HighPrecisionOptional,...] |
            list[tuple[HighPrecisionOptional,...]]): A sample of `N`
            walk-forward sequences (where `N` is the size of `data`),
            as an N-tuple.
            Or, if `num_samples` is passed, an array of `num_samples`
            samples.
        """
        # Find all valid N-tuples of valid start dates:
        start_combos = self._get_start_combos(walk_length)
        # Select 1 sample if `num_samples` not provided:
        if num_samples is None:
            starts = self.random.choice(start_combos, 1)
        # More than `num_samples` samples possible? Pick randomly:
        elif num_samples is not None and len(start_combos) > num_samples:
            starts = self.random.choice(start_combos, num_samples)
        # If we can't make `num_samples` scenarios, use them all:
        else:
            starts = start_combos
        # Build a sequence of returns for each set of start dates:
        samples = list(
            # Get the walk-forward sequence of returns for each asset
            # class (this is None for any classes with no data):
            list(
                self._get_walk_forward_sequence(
                    # pylint: disable=unsubscriptable-object
                    # Pylint seems to be confused about `start`
                    self.data[i], start[i], walk_length)
                    # pylint: enable=unsubscriptable-object
                for i in range(len(start)))
            for start in starts)
        # Don't wrap the samples in a list if we're only generating one
        # sample:
        if num_samples is None:
            return samples[0]
        return samples

    def _get_valid_walk_forward_starts(self, returns, walk_length):
        """ Finds dates in `returns` to start a walk-forward scenario. """
        # If wrapping is allowed, every date is a valid start date:
        if self.wrap_data:
            return list(returns)
        # Only dates that are at least `num_years` away from the end
        # of the dataset can be used to build a walk-forward scenario
        # that is `num_years` long:
        interval = relativedelta(years=walk_length)
        valid_starts = [
            year for year in returns
            if year + interval <= max(returns)]
        # For any empty lists, populate with `None`, otherwise calling
        # `product` with this list will return no items.
        if not valid_starts:
            valid_starts.append(None)
        return valid_starts

    def _get_walk_forward_sequence(self, returns, start_date, walk_length):
        """ Gets sequence of annual returns starting on `start_date` """
        # `start_date` can be None, so handle that first:
        if start_date is None:
            return None
        # Adjust returns to the selected interval if provided:
        if self.interval is not None:
            returns = regularize_returns(
                returns, self.interval, date=start_date)
        # Start the returns at `start_date`:
        sequence = [
            val for (date, val) in returns.items() if date >= start_date]
        # Extend the list if we're wrapping to ensure it's long enough:
        if self.wrap_data:
            while len(sequence) < walk_length:
                return_vals = list(returns.values())
                sequence += return_vals
        # Trim the sequence to just `walk_length`:
        return sequence[0:walk_length]

    def _get_start_combos(self, walk_length):
        """ Get tuples of valid starts for all columns of data. """
        # Get valid starts for each variable:
        valid_starts = list(
            self._get_valid_starts(returns, walk_length)
            for returns in self.data)
        # If we're synchronizing start dates between variables, use the
        # same dates for each variable:
        if self.synchronize:
            # Pick any column of data and find the dates that are in
            # all the columns:
            base = valid_starts[0]
            return [
                [date] * len(self.data) for date in base
                if all(date in column for column in valid_starts)]
        # If we're not synchronizing dates, find every combination of
        # start dates across variables:
        return list(product(*valid_starts))

    def _get_valid_starts(self, returns, walk_length):
        """ Get valid starts for a single column of data. """
        dates = list(returns.keys())
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
        start_of_returns = min(dates) - _infer_interval(dates)
        first_date = start_of_returns + self.interval
        last_date = max(returns) - (self.interval * (walk_length - 1))
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

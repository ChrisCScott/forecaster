""" Samplers for generating time-series data for Scenario objects. """

from itertools import product
import random
from dateutil.relativedelta import relativedelta
import numpy
from forecaster.scenario.util import interpolate_return, regularize_returns

class MultivariateSampler:
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

    def __init__(
            self, data, means=None, covariances=None):
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
        generator = numpy.random.default_rng()
        samples = generator.multivariate_normal(
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

    @classmethod
    def _generate_covariances(cls, data, covariances=None):
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
        # If no `covariances` was provided, this is easy; use numpy.cov:
        if covariances is None:
            data_array = list(list(var.values()) for var in data)
            # Use `ddof=0` to get `numpy.cov` to agree with `numpy.var`
            # See here for more:
            # https://stackoverflow.com/questions/21030668/why-do-numpy-cov-diagonal-elements-and-var-functions-have-different-values
            covariances = numpy.cov(data_array, ddof=0)
            return list(list(var) for var in covariances)
        # Otherwise, we need to iterate over `covariances` and replace
        # `None` values with statistics from `data`.
        size = len(data)  # Rows/cols must be this size. Use this below.
        if None in covariances:
            # If no row/col of covariances is provided for a given variable,
            # expand it to a row/col of `None` values for later replacement:
            covariances = [
                val if val is not None else [None] * size
                for val in covariances]
        # We need to change entries in `covariances`. To avoid mutating
        # the input matrix, and to ensure that we don't try to mutate a
        # tuple or similar, convert `covariances` to a 2D list-matrix:
        covariances = list(list(var) for var in covariances)
        # Iterate over the 2D covariance matrix and replace each `None`
        # value with the pairwise covariance:
        for i in range(size):
            # Fill in the diagonal elements:
            if covariances[i][i] is None:
                covariances[i][i] = numpy.var(list(data[i].values()))
            # Fill in the non-diagonal elements:
            for j in range(i+1, size):
                if covariances[i][j] is None or covariances[j][i] is None:
                    aligned_data = cls._align_data(data[i], data[j])
                    # Use `ddof=0` to get `numpy.cov` to agree with
                    # `numpy.var`. See here for more:
                    # https://stackoverflow.com/questions/21030668/why-do-numpy-cov-diagonal-elements-and-var-functions-have-different-values
                    cov_matrix = numpy.cov(aligned_data, ddof=0)
                    # numpy.cov returns a 2x2 covariance matrix, but what we
                    # actually want is just one of the two (identical)
                    # off-diagonal entries to get the pairwise covariance:
                    covariance = cov_matrix[1][0]
                    # A covariance matrix is symmetric, so we can fill in
                    # the (i,j) and (j,i) entries at the same time:
                    covariances[i][j] = covariance
                    covariances[j][i] = covariance
        return covariances

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
        # Get a value for each date and build a 2xn array for the `n` dates:
        aligned_data = (
            list(interpolate_return(data1, date) for date in dates),
            list(interpolate_return(data2, date) for date in dates))
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
            starts = random.sample(start_combos,1)
        # More than `num_samples` samples possible? Pick randomly:
        elif num_samples is not None and len(start_combos) > num_samples:
            starts = random.sample(start_combos, num_samples)
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
        # Find the dates that can be used as the start of a walk-forward
        # scenario:
        valid_starts = list(returns.keys())
        # All dates work if we're wrapping:
        if self.wrap_data:
            return valid_starts
        # If there's no `interval`, get all the dates that are at
        # least `walk_length` from the end.
        if self.interval is None:
            last_index = len(valid_starts)-walk_length+1
            return valid_starts[0:last_index]
        # If there is an `interval`, get all the dates that are
        # at least `interval` from the last date:
        last_date = max(returns) - self.interval
        return list(date for date in valid_starts if date <= last_date)

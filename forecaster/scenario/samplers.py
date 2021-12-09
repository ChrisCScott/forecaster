""" Samplers for generating time-series data for Scenario objects. """

from bisect import bisect_left
from itertools import product
import random
from collections import OrderedDict
from dateutil.relativedelta import relativedelta
import numpy

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
            matrix for the variables.
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
            Or, if num_samples` is passed, an array of `num_samples`
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
            covariances = numpy.cov(data_array)
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
                # It's not clear why `numpy.var` returns a different
                # value here than `numpy.cov`. Use `numpy.cov` for
                # consistency of results.
                cov = numpy.cov(list(data[i].values()))
                covariances[i][i] = numpy.ndarray.item(cov)
            # Fill in the non-diagonal elements:
            for j in range(i+1, size):
                if covariances[i][j] is None or covariances[j][i] is None:
                    aligned_data = cls._align_data(data[i], data[j])
                    # numpy.cov returns a 2x2 covariance matrix, but what we
                    # actually want is just one of the two (identical)
                    # off-diagonal entries to get the pairwise covariance:
                    covariance = numpy.cov(aligned_data)[1][0]
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
            list(_interpolate_value(data1, date) for date in dates),
            list(_interpolate_value(data2, date) for date in dates))
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
        interval (relativedelta): The period over which the return for
            each date is calculated. Optional, defaults to 1 year (i.e.
            `relativedelta(years=1)`), so that returns for each date is
            calculated over the year following the date.

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
        interval (relativedelta): The period over which the return for
            each date is calculated.
    """

    def __init__(
            self, data, synchronize=False, wrap_data=False,
            interval=relativedelta(years=1)):
        self.data = data
        self.synchronize = synchronize
        self.wrap_data = wrap_data
        self.interval = interval

    def sample(self, num_years, num_samples=None):
        """ Generates walk-forward time-series data. """
        # Get annual returns for each date in the dataset:
        returns = list(self._generate_returns(values) for values in self.data)
        # Find the dates that can be used as the start of a walk-forward
        # scenario:
        # TODO: Consider allowing wrap-around walk-forward scenarios,
        # where we treat every start date as valid and simply wrap
        # around to the start of the dataset when we reach the end.
        # This would probably need to be set as a flag on __init__;
        # consider how to handle this (receive as a kwarg, store a copy
        # of kwargs as attrs? Abandon `MethodRegister` approach and
        # simply provide each different sampler as a subclass with its
        # own init args? Consider how this would impact `Settings`; but
        # maybe this class doesn't need to have its behaviour provided
        # by `Settings` - maybe `Forecaster` doesn't need to build it?)
        valid_starts = list(
            self._get_valid_walk_forward_starts(values, num_years)
            for values in self.data)
        # Build a list of all possible unique combinations of indexes
        # that can be used as the start of a walk-forward scenario,
        # namely keys that are at least `num_years` from the end of the
        # dataset:
        start_combos = list(product(valid_starts))
        # If we can make lots of scenarios, pick `num_samples` of them
        # at random:
        if num_samples is not None and len(start_combos) > num_samples:
            starts = random.sample(start_combos, num_samples)
        # If we can't make `num_samples` scenarios, just make all we can
        else:
            starts = start_combos
        # Build a sequence of returns for each set of start dates:
        samples = list(
            # Get the walk-forward sequence of returns for each asset
            # class (this is None for any classes with no data):
            list(
                self._get_walk_forward_sequence(returns[i], start[i], num_years)
                for i in range(len(start)))
            for start in starts)
        return samples

    def _get_valid_walk_forward_starts(self, returns, num_years):
        """ Finds dates in `returns` to start a walk-forward scenario. """
        # Only dates that are at least `num_years` away from the end
        # of the dataset can be used to build a walk-forward scenario
        # that is `num_years` long:
        interval = relativedelta(years=num_years)
        valid_starts = [
            year for year in returns
            if year + interval <= max(returns)]
        # For any empty lists, populate with `None`, otherwise calling
        # `product` with this list will return no items.
        if not valid_starts:
            valid_starts.append(None)
        return valid_starts

    def _get_walk_forward_sequence(self, returns, start_date, num_years):
        """ Gets sequence of annual returns starting on `start_date` """
        # `start_date` can be None, so handle that first:
        if start_date is None:
            return None
        # Get the annualized return for `start_date` and each
        # anniversary of that date going `num_years` into the future:
        return [
            self._generate_return_from_date(
                returns, start_date + relativedelta(years=i))
            for i in range(num_years)]

    # TODO: Move this and _generate_return_from_date to
    # `HistoricalValueReader`
    def _generate_returns(self, values):
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

        Returns:
            (OrderedDict[date, float | HighPrecisionType]): An ordered
                mapping of dates to percentage returns representing the
                return for a one-year period following each key date.
        """
        annualized_returns = OrderedDict()
        for date in values:
            returns = self._generate_return_from_date(values, date)
            if returns is not None:
                annualized_returns[date] = returns
        return annualized_returns

    def _generate_return_from_date(self, values, date):
        """ Returns annual return starting on `date`. """
        # We will compare `date` to a date one year later:
        end_date = date + self.interval
        # If there's no data a year out, we can't get the annual return:
        if end_date > max(values):
            return None
        # Get the values on `date` and `end_date`, interpolating from
        # surrounding data if necessary:
        start_val = _interpolate_value(values, date)
        end_val = _interpolate_value(values, end_date)
        # Return is just the amount by which the ratio exceeds 1:
        return end_val / start_val - 1

def _interpolate_value(values, date):
    """ Determines a portfolio value on `date` based on nearby dates """
    # Check to see if the date is available exactly:
    if date in values:
        return values[date]
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

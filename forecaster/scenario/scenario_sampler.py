""" Provides a ScenarioSampler class for producing Scenario objects. """

from collections import OrderedDict
from bisect import bisect_left
from random import sample
from itertools import product
import numpy
from dateutil.relativedelta import relativedelta
from forecaster.scenario import Scenario, HistoricalValueReader
from forecaster.utility import (
    HighPrecisionHandler, MethodRegister, registered_method_named)

DEFAULT_STOCK_FILENAME = 'msci_world.csv'
DEFAULT_BOND_FILENAME = 'treasury_bond_1-3_years.csv'
DEFAULT_OTHER_FILENAME = 'nareit.csv'
DEFAULT_INFLATION_FILENAME = 'cpi.csv'
DEFAULT_FILENAMES = (
    DEFAULT_STOCK_FILENAME, DEFAULT_BOND_FILENAME,
    DEFAULT_OTHER_FILENAME, DEFAULT_INFLATION_FILENAME)

# TODO: REFACTOR!!!! Create a wrapper for HistoricalValueReader that
# reads in multiple files (from an arbitrary-length tuple/list),
# stores results (in tuples). Expand HistoricalValueReader to
# provides helper functions for:
#   1. generating annual returns over a date range
#   2. generating annualized returns for a given date
#   3. generating annualized returns for all dates
#      (or dates in a set/list/tuple?)
#   4. interpolating a value for a date within the bounds of a
#      dataset
#
# Revise `ScenarioSampler` to be a `MethodRegister` that reads in
# files to get data, then passes in appropriately-processed data
# to sampling classes (e.g. MultivariateSampler) which
# yield tuples of sampled results (via `sample()`).
# `ScenarioSamper` processes these to build `Scenario` objects and
# yields them via `__iter__`. Consider using a `NamedTuple` for
# convenience in `ScenarioSampler` and casting to/from this when
# calling a sampling class.

class ScenarioSampler(HighPrecisionHandler, MethodRegister):
    """ A generator for `Scenario` objects.

    Arguments:
        num_samples (int): The maximum number of `Scenario` objects to
            generate. (Fewer samples may be generated, e.g. if the
            relevant sampler does not have sufficient data to generate
            more uniquely.)
        default_scenario (Scenario | tuple | list | dict): A `Scenario`
            object, or args (as *args tuple/list or **kwargs dict) from
            which a Scenario may be initialized.
        filenames (tuple[str | None, str | None, str | None , str | None]):
            Filenames for CSV files providing stock returns, bond
            returns, other property returns, and inflation, in that
            order. `None` values will not be read; if the tuple is
            shorter than expected, omitted values are treated as `None`.
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.

    Attributes:
        num_samples (int): The maximum number of `Scenario` objects to
            generate. (Fewer samples may be generated, e.g. if the
            relevant sampler does not have sufficient data to generate
            more uniquely.)
        default_scenario (Scenario): A `Scenario` object, or args (as
            *args tuple/list or **kwargs dict) from which a Scenario may
            be initialized.
        stocks (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to stock values.
        bonds (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to bond values.
        other (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to other property values.
        inflation (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to inflation values.
    """

    def __init__(
            self, sampler, num_samples, default_scenario,
            filenames=DEFAULT_FILENAMES, *, high_precision=None, **kwargs):
        super().__init__(high_precision=high_precision, **kwargs)
        # Unroll `filenames`:
        if len(filenames) < len(DEFAULT_FILENAMES):
            # Pad filenames with `None` if it's too short:
            filenames += (None,)*(len(DEFAULT_FILENAMES) - len(filenames))
        stock_filename, bond_filename, other_filename, inflation_filename = (
            filenames)
        # Declare instance variables:
        self.sampler = sampler
        self.num_samples = num_samples
        self.default_scenario = default_scenario
        # Read in historical return/inflation data from CSV files:
        # (`None` filenames will produce an empty dict)
        self.stocks = HistoricalValueReader(
            stock_filename, high_precision=high_precision).values
        self.bonds = HistoricalValueReader(
            bond_filename, high_precision=high_precision).values
        self.other = HistoricalValueReader(
            other_filename, high_precision=high_precision).values
        self.inflation = HistoricalValueReader(
            inflation_filename, high_precision=high_precision).values

    def __iter__(self):
        """ Yields `num_samples` `Scenario` objects using `sampler`. """
        yield self.call_registered_method(self.sampler)

    @registered_method_named('walk-forward')
    def sampler_walk_forward(self):
        """ Yields `Scenario` objects via walk-forward backtests. """
        # Get annual returns for each date in the dataset:
        stock_returns, bond_returns, other_returns, inflation_returns = (
            self.annualize_returns_all())
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
        valid_stock_starts = self._get_valid_walk_forward_starts(stock_returns)
        valid_bond_starts = self._get_valid_walk_forward_starts(bond_returns)
        valid_other_starts = self._get_valid_walk_forward_starts(other_returns)
        valid_inflation_starts = self._get_valid_walk_forward_starts(
            inflation_returns)
        # Build a list of all possible unique combinations of indexes
        # that can be used as the start of a walk-forward scenario,
        # namely keys that are at least `num_years` from the end of the
        # dataset:
        all_scenarios = list(product(
            valid_stock_starts, valid_bond_starts,
            valid_other_starts, valid_inflation_starts))
        # If we can make lots of scenarios, pick `num_samples` of them
        # at random:
        if len(all_scenarios) > self.num_samples:
            scenarios = sample(all_scenarios, self.num_samples)
        # If we can't make `num_samples` scenarios, just make all we can
        else:
            scenarios = all_scenarios
        # Build the scenarios!
        for scenario in scenarios:
            # Get the walk-forward sequence of returns for each asset
            # class (this is None for any classes with no data):
            stock = self._get_walk_forward_sequence(
                stock_returns, scenario[0])
            bond = self._get_walk_forward_sequence(
                bond_returns, scenario[1])
            other = self._get_walk_forward_sequence(
                other_returns, scenario[2])
            inflation = self._get_walk_forward_sequence(
                inflation_returns, scenario[3])
            # None values are automatically ignored by _build_scenario:
            yield self._build_scenario(stock, bond, other, inflation)

    def _get_valid_walk_forward_starts(self, returns):
        """ Finds dates in `returns` to start a walk-forward scenario. """
        # Only dates that are at least `num_years` away from the end
        # of the dataset can be used to build a walk-forward scenario
        # that is `num_years` long:
        interval = relativedelta(years=self.default_scenario.num_years)
        valid_starts = [
            year for year in returns
            if year + interval <= max(returns)]
        # For any empty lists, populate with `None`, otherwise calling
        # `product` with this list will return no items.
        if not valid_starts:
            valid_starts.append(None)
        return valid_starts

    def _get_walk_forward_sequence(self, returns, start_date):
        """ Gets sequence of annual returns starting on `start_date` """
        # `start_date` can be None, so handle that first:
        if start_date is None:
            return None
        # Get the annualized return for `start_date` and each
        # anniversary of that date going `num_years` into the future:
        return [
            self.annualize_return_from_date(
                returns, start_date + relativedelta(years=i))
            for i in range(self.default_scenario.num_years)]

    @registered_method_named('random returns')
    def sampler_random_returns(self):
        """ Yields `Scenario` objects with random returns. """
        # Get annual returns for each date in the dataset:
        stock_returns, bond_returns, other_returns, inflation_returns = (
            self.annualize_returns_all())
        # For each year, sample from a normal distribution with the mean
        # and variance found in the returns data for each asset class:
        stock_samples = []
        bond_samples = []
        other_samples = []
        inflation_samples = []
        for _ in range(self.default_scenario.num_years):
            stock_samples.append(self._sample_return(stock_returns))
            bond_samples.append(self._sample_return(bond_returns))
            other_samples.append(self._sample_return(other_returns))
            inflation_samples.append(self._sample_return(inflation_returns))
        # Build a `Scenario` object with the sampled rates of return:
        yield self._build_scenario(
            stock_samples, bond_samples, other_samples, inflation_samples)

    @registered_method_named('constant returns')
    def sampler_constant_returns(self):
        """ Yields `Scenario` objects with constant-valued returns. """
        # Get annual returns for each date in the dataset:
        stock_returns, bond_returns, other_returns, inflation_returns = (
            self.annualize_returns_all())
        # Sample from a normal distribution with the mean and variance
        # found in the returns data for each asset class:
        stock_sample = self._sample_return(stock_returns)
        bond_sample = self._sample_return(bond_returns)
        other_sample = self._sample_return(other_returns)
        inflation_sample = self._sample_return(inflation_returns)
        # Build a `Scenario` object with the sampled rates of return,
        # keeping them constant across time:
        yield self._build_scenario(
            stock_sample, bond_sample, other_sample, inflation_sample)

    def _build_scenario(self, stock, bond, other, inflation):
        """ Builds a `Scenario` object based on args and `self.default` """
        # Use values from `default_scenario` if not provided via args:
        if stock is None:
            stock = self.default_scenario.stock_return
        if bond is None:
            bond = self.default_scenario.bond_return
        if other is None:
            other = self.default_scenario.other_return
        if inflation is None:
            inflation = self.default_scenario.inflation_return
        # Build a Scenario:
        return Scenario(
            self.default_scenario.initial_year,
            self.default_scenario.num_years,
            management_fees=self.default_scenario.management_fees,
            inflation=inflation, stock_return=stock,
            bond_return=bond, other_return=other)

    def _sample_return(self, returns):
        """ Samples from a normal distribution based on `returns`. """
        # Don't sample if there is no data:
        if not returns:
            return None
        # Otherwise, just sample from a straightforward normal dist.:
        mean = numpy.mean(returns.values())
        std_dev = numpy.std(returns.values())
        return numpy.random.normal(mean, std_dev)

    def annualize_returns_all(self):
        """ Convenience wrapper for calling `annualize_returns`.

        Returns:
            tuple (
                OrderedDict[datetime, float | HighPrecisionType],
                OrderedDict[datetime, float | HighPrecisionType],
                OrderedDict[datetime, float | HighPrecisionType],
                OrderedDict[datetime, float | HighPrecisionType]):
            A tuple of percentage returns (as returned by
            `annualize_returns`) for each of the `stocks`, `bonds`,
            `other`, and `inflation` attributes of this object.
        """
        return (
            self.annualize_returns(self.stocks),
            self.annualize_returns(self.bonds),
            self.annualize_returns(self.other),
            self.annualize_returns(self.inflation))

    def annualize_returns(self, values):
        """ Generates the one-year return for each date in `values`.

        This is the return _following_ each date (i.e. looking forward
        in time). Dates for which porfolio values are not known one year
        into the future are not included in the result.

        For instance, if the dataset includes portfolio values for 2000,
        2001, and 2002, the returned dict will include returns only for
        dates in 2000 and 2001 (but not 2002, as no portfolio values are
        known for 2003 or later).

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
            returns = self.annualize_return_from_date(values, date)
            if returns is not None:
                annualized_returns[date] = returns
        return annualized_returns

    def annualize_return_from_date(self, values, date):
        """ Returns annual returns starting on `date`. """
        # We will compare `date` to a date one year later:
        interval = relativedelta(years=1)
        end_date = date + interval
        # If there's no data a year out, we can't get the annual return:
        if end_date > max(values):
            return None
        # Get the values on `date` and `end_date`, interpolating from
        # surrounding data if necessary:
        start_val = _interpolate_value(values, date)
        end_val = _interpolate_value(values, end_date)
        # Return is just the amount by which the ratio exceeds 1:
        return end_val / start_val - 1

class MultivariateSampler:
    """ An iterator yielding samples objects with constant returns.

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
            tuple[tuple[HighPrecisionOptional,...]]): A sample of `N`
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
            return tuple(numpy.mean(var) for var in data)
        # Otherwise, fill in `None` values from `means` based on `data`:
        return tuple(
            means[i] if means[i] is not None else numpy.mean(data[i])
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
            (tuple(tuple(HighPrecisionOptional))): A two-dimensional
            array of covariance values.
        """
        # If no `covariances` was provided, this is easy; use numpy.cov:
        if covariances is None:
            data_array = tuple(tuple(var.values()) for var in data)
            return numpy.cov(data_array)
        # Otherwise, we need to iterate over `covariances` and replace
        # `None` values with statistics from `data`:
        size = len(data)
        if None in covariances:
            # If no row/col of covariances is provided for a given variable,
            # expand it to a row/col of `None` values for later replacement:
            covariances = [
                val if val is not None else [None] * size
                for val in covariances]
        # Iterate over the 2D covariance matrix and replace each `None`
        # value with the pairwise covariance:
        for i in range(size):
            # Fill in the diagonal elements:
            if covariances[i][i] is None:
                covariances[i][i] = numpy.var(data[i].values())
            # Fill in the non-diagonal elements:
            for j in range(i+1, size):
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
        min_date = max(min(data1, data2))
        max_date = min(max(data1, data2))
        # Use the dates in the first dataset, limited to dates within the
        # range of overlapping dates:
        dates = tuple(
            date for date in data1 if date >= min_date and date <= max_date)
        # If there's not enough overlapping data, assume no covariance:
        if len(dates) < 2:  # Need 2 vals for each var to get 2x2 covariance
            return ((0,0), (0,0))
        # Get a value for each date and build a 2xn array for the `n` dates:
        aligned_data = (
            tuple(_interpolate_value(data1, date) for date in dates),
            tuple(_interpolate_value(data2, date) for date in dates))
        return aligned_data

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

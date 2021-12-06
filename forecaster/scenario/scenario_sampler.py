""" Provides a ScenarioSampler class for producing Scenario objects. """

from collections import OrderedDict
from bisect import bisect_left
from random import sample
from itertools import product
import numpy
from dateutil.relativedelta import relativedelta
from forecaster.scenario import Scenario, HistoricalValueReader
from forecaster.utility import (
    HighPrecisionOptional, MethodRegister, registered_method_named)

DEFAULT_STOCK_FILENAME = 'msci_world.csv'
DEFAULT_BOND_FILENAME = 'treasury_bond_1-3_years.csv'
DEFAULT_OTHER_FILENAME = 'nareit.csv'
DEFAULT_INFLATION_FILENAME = 'inflation.csv'
DEFAULT_FILENAMES = (
    DEFAULT_STOCK_FILENAME, DEFAULT_BOND_FILENAME,
    DEFAULT_OTHER_FILENAME, DEFAULT_INFLATION_FILENAME)

class ScenarioSampler(HighPrecisionOptional, MethodRegister):
    """ A generator for `Scenario` objects.

    Arguments:
        sampler (str, Callable[[int], Scenario]): Either a str-valued
            key for a `registered_method_named` or a reference to such
            a method. This method will be used to generate `Scenario`
            objects when instances of this class are iterated over.
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
        sampler (str, Callable[[int], Scenario]): Either a str-valued
            key for a `registered_method_named` or a reference to such
            a method. This method will be used to generate `Scenario`
            objects when instances of this class are iterated over.
        num_samples (int): The maximum number of `Scenario` objects to
            generate. (Fewer samples may be generated, e.g. if the
            relevant sampler does not have sufficient data to generate
            more uniquely.)
        default_scenario (Scenario): A `Scenario` object, or args (as
            *args tuple/list or **kwargs dict) from which a Scenario may
            be initialized.
        stocks (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to portfolio values.
        bonds (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to portfolio values.
        other (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to portfolio values.
        inflation (OrderedDict[date, float | HighPrecisionType]):
            An ordered mapping of dates to portfolio values.
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
        interval = relativedelta(years=1)
        end_date = date + interval
        if end_date in values:
            return values[end_date] / values[date]
        if end_date > max(values):
            return None
        # If we don't have the portfolio value exactly one year after
        # `date`, but we do have values before and after it, interpolate
        # a value based on those dates:
        return self._interpolate_value(values, date)

    def _interpolate_value(self, values, date):
        """ Determines a portfolio value on `date` based on nearby dates """
        # Get the dates on either side of `date`:
        dates = list(values)
        index = bisect_left(dates, date)
        prev_date = dates[index-1]
        next_date = dates[index]
        # Weight values based on how close they are to `date`:
        days_total = (next_date - prev_date).days
        days_prev = (date - prev_date).days
        days_next = (next_date - date).days
        weight_prev = self.precision_convert(days_prev / days_total)
        weight_next = self.precision_convert(days_next / days_total)
        # Interpolate a value on `date` based on the dates before/after:
        return (
            values[prev_date] * weight_prev + values[next_date] * weight_next)

""" Provides a ScenarioSampler class for producing Scenario objects. """

from collections import namedtuple
from forecaster.scenario.samplers import MultivariateSampler, WalkForwardSampler
from forecaster.scenario import Scenario, HistoricalValueReader
from forecaster.utility import (
    HighPrecisionHandler, MethodRegister, registered_method_named)

ReturnsTuple = namedtuple(
    "ReturnsTuple", ['stocks', 'bonds', 'other', 'inflation'])

DEFAULT_FILENAMES = ReturnsTuple(
    stocks='msci_world.csv',
    bonds='treasury_bond_1-3_years.csv',
    other='nareit.csv',
    inflation='cpi.csv')

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
        if not isinstance(filenames, ReturnsTuple):
            filenames = ReturnsTuple(*filenames)
        # Declare instance variables:
        self.sampler = sampler
        self.num_samples = num_samples
        self.default_scenario = default_scenario
        self.filenames = filenames
        # Read in historical return/inflation data from CSV files:
        # (`None` filenames will produce an empty dict)
        # TODO: Convert values to percentage returns by moving
        # _generate_returns out of `WalkForwardSampler` and into
        # HistoricalValueReader
        self.data = ReturnsTuple(*(HistoricalValueReader(
            filename, high_precision=high_precision).values
            for filename in self.filenames))

    def __iter__(self):
        """ Yields `num_samples` `Scenario` objects using `sampler`. """
        yield self.call_registered_method(self.sampler)

    @registered_method_named('walk-forward')
    def sampler_walk_forward(self):
        """ Yields `Scenario` objects with walk-forward returns. """
        sampler = WalkForwardSampler(self.data)
        samples = sampler.sample(
            self.default_scenario.num_years, num_samples=self.num_samples)
        for sample in samples:
            yield self._build_scenario(*sample)

    @registered_method_named('random returns')
    def sampler_random_returns(self):
        """ Yields `Scenario` objects with random returns. """
        sampler = MultivariateSampler(self.data)
        # Get `num_samples` samples with `num_years` values for each variable:
        samples = sampler.sample(
            num_samples=(self.num_samples, self.default_scenario.num_years))
        # Build a `Scenario` object with each collection of sampled
        # rates of return, keeping them constant across time:
        for sample in samples:
            yield self._build_scenario(*sample)

    @registered_method_named('constant returns')
    def sampler_constant_returns(self):
        """ Yields `Scenario` objects with constant-valued returns. """
        sampler = MultivariateSampler(self.data)
        # Get `num_samples` samples with 1 value for each variable:
        samples = sampler.sample(num_samples=self.num_samples)
        # Build a `Scenario` object with each collection of sampled
        # rates of return, keeping them constant across time:
        for sample in samples:
            yield self._build_scenario(*sample)

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

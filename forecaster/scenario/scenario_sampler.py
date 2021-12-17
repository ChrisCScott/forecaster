""" Provides a ScenarioSampler class for producing Scenario objects. """

from collections import namedtuple
from forecaster.scenario.samplers import MultivariateSampler, WalkForwardSampler
from forecaster.scenario.scenario import Scenario
from forecaster.scenario.historical_value_reader import HistoricalValueReader
from forecaster.utility import (
    HighPrecisionHandler, MethodRegister, registered_method_named)

ReturnsTuple = namedtuple(
    "ReturnsTuple", ['stocks', 'bonds', 'other', 'inflation'])

DEFAULT_FILENAMES = ReturnsTuple(
    stocks='msci_world.csv',
    bonds='treasury_bond_1-3_years.csv',
    other='nareit.csv',
    inflation='cpi.csv')

class ScenarioSampler(HighPrecisionHandler, MethodRegister):
    """ A generator for `Scenario` objects.

    Data can be read from one or more CSV files to provide material for
    sampling. See documentation for `read_data` for more on this.

    If you don't want to read from a file, pass `filenames=None` and
    set the `data` attribute manually after init.

    Arguments:
        num_samples (int): The maximum number of `Scenario` objects to
            generate. (Fewer samples may be generated, e.g. if the
            relevant sampler does not have sufficient data to generate
            more uniquely.)
        default_scenario (Scenario | tuple | list | dict): A `Scenario`
            object, or args (as *args tuple/list or **kwargs dict) from
            which a Scenario may be initialized.
        filenames (list[str] | None): Filenames for CSV files providing
            historical portfolio returns and/or portfolio values.
            Optional; defaults to `DEFAULT_FILENAMES`. If None, no files
            are read.
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
        data (ReturnsTuple[OrderedDict[date, HighPrecisionOptional]]):
            A sequence of ordered mappings of dates to returns.
    """

    def __init__(
            self, sampler, num_samples, default_scenario,
            filenames=DEFAULT_FILENAMES,
            *, returns=None, high_precision=None, **kwargs):
        super().__init__(high_precision=high_precision, **kwargs)
        # Declare instance variables:
        self.sampler = sampler
        self.num_samples = num_samples
        self.default_scenario = default_scenario
        self.data = ReturnsTuple(*((tuple(),) * 4))
        if filenames is not None:
            self.data = self.read_data(filenames, returns=returns)

    def __iter__(self):
        """ Yields `num_samples` `Scenario` objects using `sampler`. """
        return self.call_registered_method(self.sampler)

    def read_data(self, filenames, returns=None):
        """ Reads data from `filenames` and merges results.

        Each file in `filenames` may provide any number of data columns,
        which are ingested in sequence (preserving order within and
        between files). The total number of data columns across all
        files must match the number of fields on `ReturnsTuple`.

        For instance, if `file1.csv` provides columns for stocks and
        bonds (in that order) and `file2.csv` provides data for other
        and inflation (in that order), then passing
        `filenames=['file1.csv','file2.csv']` will result in the `data`
        attribute having four columns, in the order (stocks, bonds,
        other, inflation). Reversing this (i.e. passing
        `filenames=['file2.csv','file1.csv']`) would result in the order
        (other, inflation, stocks, bonds), which may not be desired, so
        be careful about order of files and also ordering of columns
        within files.

        Returns:
            (ReturnsTuple[OrderedDict[date, HighPrecisionOptional]])
        """
        # Read in historical return/inflation data from CSV files:
        returns_tuples = tuple(
            HistoricalValueReader(
                filename, returns=returns, high_precision=self.high_precision
            ).returns()
            for filename in filenames)
        # The above produces a tuple where each element is another tuple
        # of one or more columns. Reduce this to a tuple of columns:
        return ReturnsTuple(*sum(returns_tuples, ()))

    @registered_method_named('walk-forward')
    def sampler_walk_forward(self):
        """ Yields `Scenario` objects with walk-forward returns. """
        sampler = WalkForwardSampler(
            self.data, high_precision=self.high_precision)
        samples = sampler.sample(
            self.default_scenario.num_years, num_samples=self.num_samples)
        for sample in samples:
            yield self._build_scenario(*sample)

    @registered_method_named('random returns')
    def sampler_random_returns(self):
        """ Yields `Scenario` objects with random returns. """
        sampler = MultivariateSampler(
            self.data, high_precision=self.high_precision)
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
        sampler = MultivariateSampler(
            self.data, high_precision=self.high_precision)
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

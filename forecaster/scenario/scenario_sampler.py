""" Provides a ScenarioSampler class for producing Scenario objects. """

from collections import namedtuple
from forecaster.scenario.samplers import MultivariateSampler, WalkForwardSampler
from forecaster.scenario.scenario import Scenario
from forecaster.scenario.historical_value_reader import (
    HistoricalValueReaderArray)
from forecaster.utility import (
    HighPrecisionHandler, MethodRegister, registered_method_named)

# Provide this for convenience for client code:
RETURNS_FIELDS = ('stocks', 'bonds', 'other', 'inflation')
ReturnsTuple = namedtuple(
    "ReturnsTuple", RETURNS_FIELDS, defaults=(None,) * len(RETURNS_FIELDS))

class ScenarioSampler(HighPrecisionHandler, MethodRegister):
    """ A generator for `Scenario` objects.

    Samples are generated based on `data`, which can be passed directly,
    or can be read from one or more CSV files. See documentation for
    `read_data` for more on this.

    All `Scenario`-specific logic is provided by `_build_scenario`.
    Subclasses that use different scenario types should overload that
    method.

    Arguments:
        sampler (str, Callable, Hashable): The key for a
            `registered_method_named` method of this class, or the
            method itself. This is the method used to generate samples.
        data (tuple[tuple[list[datetime], list[HighPrecisionOptional]] | None] |
            list[str | None]): Either data readable by samplers of the
            `sampler` module or a sequence of filenames from which
            data can be read. (`None` entries may be provided in either
            case, in which case the corresponding value of
            `default_scenario` will be used when generating scenarios.)
        default_scenario (Scenario | tuple | list | dict): A `Scenario`
            object, or args (as *args tuple/list or **kwargs dict) from
            which a Scenario may be initialized.
        num_samples (int | None): The maximum number of `Scenario`
            objects to generate. (Fewer samples may be generated, e.g.
            if a walk-forward sampler does not have sufficient data to
            generate more uniquely.)
            Optional. If not provided, one sample will be generated.
        returns (bool | None): If True, data in `filenames` will be
            interpreted as returns (i.e. in percentage terms). If
            False, data in `filenames` will be interpreted as portfolio
            values (i.e. in absolute terms). If not provided, each file
            will be analyzed by `HistoricalValueReader` and interpreted
            accordingly.
        fast_read (bool): If `True`, data is presumed to be arranged in
            sorted order (i.e. with dates in increasing order) and
            values are assumed to be float-convertible without
            additional processing. If `False`, data will be sorted
            on read and values will be parsed to remove characters
            that are not legally float-convertible.
            Optional; defaults to `False`.
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
        data (tuple[tuple[list[datetime], list[HighPrecisionOptional]]]):
            A sequence of ordered mappings of dates to returns.
    """

    def __init__(
            self, sampler, data, default_scenario, num_samples=None, *,
            returns=None, fast_read=False, high_precision=None, **kwargs):
        super().__init__(high_precision=high_precision, **kwargs)
        # Declare instance variables:
        self.sampler = sampler
        self.num_samples = num_samples
        self.default_scenario = default_scenario
        # Read from files, if filenames were provided:
        if all(isinstance(val, str) for val in data):
            self.data = self.read_data(
                data, returns=returns, fast_read=fast_read)
        # Otherwise, use the data as-is:
        else:
            self.data = data

    def __iter__(self):
        """ Yields `num_samples` `Scenario` objects using `sampler`. """
        samples = self.call_registered_method(self.sampler)
        # Samplers return only a single arg if num_samples = None,
        # so wrap those in a list for iteration:
        if self.num_samples is None:
            samples = [samples]
        # Turn each set of sampled returns into `Scenario` objects and
        # yield them one at a time:
        for sample in samples:
            scenario_args = self._sample_to_scenario_args(sample)
            # pylint: disable=no-value-for-parameter
            # `scenario_args` has 4 elements iff `data` does.
            # We could cast this to `ReturnTuple` to make pylint happy,
            # but this would make subclassing harder.
            yield self._build_scenario(*scenario_args)
            # pylint: enable=no-value-for-parameter

    def sample(self, num_samples=None):
        """ Returns `num_samples` `Scenario` objects using `sampler`.

        The return value of this method is identical to calling
        `list(sampler)`, where `sampler` is a `ScenarioSampler` object.

        For convenience, `num_samples` can be passed to `sample` and,
        if passed, will override the instance's `num_samples` attribute
        value.

        Arguments:
            num_samples (int | None): The maximum number of `Scenario`
                objects to generate. Optional. If not provided, the
                value of the instance attribute `num_samples` will be
                used. See `ScenarioSampler` for more.

        Returns:
            (list[Scenario]): A list of `num_samples` `Scenario` objects
        """
        # If `num_samples` was passed, update the instance attribute
        # to match:
        old_num_samples = self.num_samples
        if num_samples is not None:
            self.num_samples = num_samples
        # Use the logic of `__iter__`:
        scenarios = list(self)
        # Restore the original value of `num_samples`:
        self.num_samples = old_num_samples
        return scenarios

    def read_data(self, filenames, returns=None, fast_read=False):
        """ Reads data from `filenames` and merges results.

        Each file in `filenames` may provide any number of data columns,
        which are ingested in sequence (preserving order within and
        between files).

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

        Arguments:
            filenames (tuple[str, ...] | list[str]): A collection of
                filenames, as strings, which will be read in for data.
                Defaults to `DEFAULT_FILENAMES`, which point to files
                provided in `forecaster.data` with real-world historical
                data for each asset class (and inflation).
            returns (bool | None): If True, data in `filenames` will be
                interpreted as returns (i.e. in percentage terms). If
                False, data in `filenames` will be interpreted as
                portfolio values (i.e. in absolute terms).
                If not provided, each file will be analyzed by
                `HistoricalValueReader` and interpreted accordingly.
            fast_read (bool): If `True`, data is presumed to be arranged
                in sorted order (i.e. with dates in increasing order)
                and values are assumed to be float-convertible without
                additional processing. If `False`, data will be sorted
                on read and values will be parsed to remove characters
                that are not legally float-convertible.
                Optional; defaults to `False`.

        Returns:
            (tuple[tuple[list[datetime], list[HighPrecisionOptional]]]):
            A sequence of data columns, each column being a pair of
            lists (one for dates and one for values). See docs for the
            `sampler` module or `HistoricalValueReaderArray` for more.
        """
        # Read in historical return/inflation data from CSV files:
        returns_tuples = tuple(
            (HistoricalValueReaderArray(
                filename, returns=returns, fast_read=fast_read,
                high_precision=self.high_precision
            ).returns() if filename is not None else (None,))
            for filename in filenames)
        # The above produces a tuple where each element is another tuple
        # of one or more columns. Reduce this to a tuple of columns:
        return tuple(sum(returns_tuples, ()))

    @registered_method_named('walk-forward')
    def sampler_walk_forward(self):
        """ Samples walk-forward returns. """
        data = self._data_for_sampler()
        sampler = WalkForwardSampler(data, high_precision=self.high_precision)
        samples = sampler.sample(
            num_samples=self.num_samples,
            sample_length=self.default_scenario.num_years)
        return samples

    @registered_method_named('random returns')
    def sampler_random_returns(self):
        """ Samples random, annually-varying returns. """
        data = self._data_for_sampler()
        sampler = MultivariateSampler(data, high_precision=self.high_precision)
        # Get `num_samples` samples with `num_years` values for each variable:
        samples = sampler.sample(
            num_samples=self.num_samples,
            sample_length=self.default_scenario.num_years)
        return samples

    @registered_method_named('constant returns')
    def sampler_constant_returns(self):
        """ Samples constant, random returns. """
        data = self._data_for_sampler()
        sampler = MultivariateSampler(data, high_precision=self.high_precision)
        # Get `num_samples` samples with 1 value for each variable:
        samples = sampler.sample(num_samples=self.num_samples)
        return samples

    def _data_for_sampler(self):
        """ Returns a matrix of data suitable for processing by samplers """
        # Need to remove all `None` entries from `self.data`:
        return tuple(val for val in self.data if val is not None)

    def _sample_to_scenario_args(self, sample):
        """ Converts samples received from `data` to a `ReturnTuple` """
        # Re-insert None entries that were stripped by `_data_for_sampler`:
        expanded_sample = []
        sample_iter = iter(sample)
        for column in self.data:
            if column is None:
                expanded_sample.append(None)
            else:
                expanded_sample.append(next(sample_iter))
        return expanded_sample

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
            inflation = self.default_scenario.inflation
        # Build a Scenario:
        return Scenario(
            self.default_scenario.initial_year,
            self.default_scenario.num_years,
            management_fees=self.default_scenario.management_fees,
            inflation=inflation, stock_return=stock,
            bond_return=bond, other_return=other)

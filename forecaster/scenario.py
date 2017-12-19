""" Basic economic classes, such as `Scenario` and `Money`. """

import collections
from decimal import Decimal


class Scenario(object):
    """ Describes an economic scenario over the course of a simulation.

    For example, provides inflation rates and rates of return for each
    year of the simulation.

    This is the foil to `Strategy`; all `Scenario` information is
    reflective of broader economic trends and is independent of any user
    action.

    Attributes:
        initial_year (int): The first year of the simulation.
        num_years (int): The number of years in the simulation.
        inflation (dict[int, Decimal]): `{year, inflation}` pairs, where
            `inflation` is a percentage rate (e.g. `Decimal(0.5)` is
            50%).
        stock_return (dict[int, Decimal]): `{year, return}` pairs where
            `return` is the rate of return for stocks in the given year.
        bond_return (dict[int, Decimal]): `{year, return}` pairs where
            `return` is the rate of return for bonds in the given year.
        other_return (dict[int, Decimal]): `{year, return}` pairs where
            `return` is the rate of return for other property (e.g.
            real estate) in the given year. Optional.
        management_fees (dict[int, Decimal]): `{year, fees}` pairs
            where `fees` is the rate at which management fees are
            charged in invested assets in the given year. Optional.
    """

    def __init__(
        self, initial_year, num_years,
        inflation=0, stock_return=0, bond_return=0, other_return=0,
        management_fees=0
    ):
        """ Constructor for `Scenario`.

        Arguments may be dicts (of {year, value} pairs), lists (or
        similar `Sequence`) or scalar values.

        Args:
            inflation (Decimal, list, dict): The rate of inflation.
            stock_return (dict[int, Decimal]): `{year: return}` pairs
                for stocks.
            bond_return (dict[int, Decimal]): `{year: return}` pairs
                for bonds.
            other_return (dict[int, Decimal]): `{year: return}` pairs
                for other assets (not stocks/bonds), e.g. real estate.
            management_fees (Decimal, list, dict): The management fees
                charged on investments.
            person1_raise_rate (Decimal, list, dict): The amount that is
                expected for a raise for person1 this year, expressed as
                a percentage (e.g. 0.05 for a 5% raise).
            person2_raise_rate (Decimal, list, dict): The amount that is
                expected for a raise for person2 this year, expressed as
                a percentage (e.g. 0.05 for a 5% raise).
            initial_year (int): The first year of the projection.
            num_years (int): The number of years in the projection.

        Raises:
            ValueError: num_years must be positive.
            ValueError: input object cannot be processed by _build_dict.
        """
        # This object needs to model several economic indicators over
        # the course of several years. We could accept these implicitly
        # via kwargs (or group them into a more complex container), but
        # the present call signature is preferred because it's more
        # explicit and assists Intellisense.
        # pylint: disable=too-many-arguments

        # Set the years that the Scenario spans:
        self.initial_year = int(initial_year)
        self.num_years = int(num_years)
        if num_years < 1:
            raise ValueError('Scenario: num_years must be positive.')

        # Now build dicts from the inputs
        self.inflation = self._build_dict(inflation, self.initial_year)
        self.stock_return = self._build_dict(stock_return, self.initial_year)
        self.bond_return = self._build_dict(bond_return, self.initial_year)
        self.other_return = self._build_dict(other_return, self.initial_year)
        self.management_fees = self._build_dict(management_fees,
                                                self.initial_year)

    @staticmethod
    def _build_dict(in_val=None, initial_year=None, default=None):
        """ Helper function that turns `input` into a dict.

        The resulting dict has {year, value} pairs. If the in_val is a
        list, the dict starts with `initial_year` and builds
        sequentially from there.

        Args:
            in_val (Any, list, dict): A object that may be a list (or
                other Sequence), dict, or non-list non-dict scalar
                value.

                Optional. If not provided, uses default value.
            initial_year (int): The initial year, used when `in_val` is
                a list. The first element in the list corresponds to
                this year.

                Optional. Only required where `in_val` is a list.
            default (*): If provided, builds a defaultdict with this
                value as the default factory. Must be convertible to
                Decimal. Optional.

        Raises:
            ValueError: initial_year is required if input is a list.
            ValueError: default cannot be set for scalar input.
            ValueError: in_val and default cannot both be None.
        """
        # If no in_val is provided, use default as in_val.
        if in_val is None:
            if default is None:
                raise ValueError(
                    'Scenario: in_val and default cannot both be None.')
            return Scenario._build_dict(default, initial_year)

        # Convert a non-callable `default` to a Decimal-returning
        # default factory:
        if default is not None and not callable(default):
            _default = Decimal(default)

            # pylint: disable=function-redefined
            # This function redefinition is intentional; it's equivalent
            # to default = lambda: _default
            def default():
                """ Wraps default value in a default factory. """
                return _default

        if isinstance(in_val, collections.defaultdict):
            # Update in_val's default factory if `default` was provided:
            if default is not None:
                in_val.default_factory = default
            # Convert elements to {int: Decimal} pairs
            return collections.defaultdict(in_val.default_factory, {
                int(key): Decimal(in_val[key]) for key in in_val
            })

        # IF in_val was a dict, cast to default dict (if default was
        # provided) and type-cast all entries to {int: Decimal} pairs.
        # NOTE: Consider whether we should wrap in_val in a defaultdict
        # to avoid stripping away the properties of custom dict-derived
        # objects that the user decides to pass in.
        if isinstance(in_val, dict):
            if default is not None:
                out_val = collections.defaultdict(default, in_val)
            else:
                out_val = {int(key): Decimal(in_val[key]) for key in in_val}
            return out_val

        # If it's not a dict, but it is iterable then convert it into a
        # [default]dict
        if isinstance(in_val, collections.Iterable):
            if initial_year is None:
                raise ValueError(
                    'Scenario: initial_year is required if input is a list.')
            if default is not None:
                out_val = collections.defaultdict(default, {
                    key: Decimal(in_val[key - initial_year])
                    for key in range(initial_year, initial_year + len(in_val))
                })
            else:
                out_val = {
                    key: Decimal(in_val[key - initial_year])
                    for key in range(initial_year, initial_year + len(in_val))
                }
            return out_val

        # Otherwise, turn a scalar value into a defaultdict:
        # NOTE: default is ignored in this case
        in_val = Decimal(in_val)
        return collections.defaultdict(lambda: in_val)

    def discount_rate(self, year):
        """ Returns the discount rate for `year`.

        This is the same as calling `inflation[year]`.
        """
        return self.inflation[year]

    def accumulation_function(self, year1, year2):
        """ The discount applied in the period from year1 to year2.

        If year2 precedes year1 then the discount rate is inverted.
        """
        accum = 1
        if year1 <= year2:
            # Find the product of all intervening years' discount rates
            for year in range(year1, year2):
                accum = accum * (1 + self.discount_rate(year))
            return accum
        else:  # Same as above, except invert the result ()
            for year in range(year2, year1):
                accum = accum * (1 + self.discount_rate(year))
            return 1 / accum

    def inflation_adjustments(self, base_year):
        """ Annual inflation adjustment factors relative to base_year.

        Returns:
            dict[int, Decimal]: `{year: adjustment}` pairs.

            `adjustment` is the cumulative inflation since `base_year`
            (or, for years prior to `base_year`, it is the present value
            of $1 in base_year)
        """
        return {year: Decimal(self.accumulation_function(year, base_year))
                for year in self}

    @property
    def inflation_adjust(self):
        """ Inflation-adjustment factor from base_year to target_year.

        Args:
            target_year (int): The year for which an
                inflation-adjustment factor is desired.
            base_year (int): The year in which inflation-adjusted
                figures are expressed.

                The inflation adjustment for this year is 1 and the
                inflation adjustment for target_year is defined relative
                to this year.

        Returns:
            Decimal: The inflation-adjustment factor from `base_year` to
            `target_year`. This is the product of inflation-adjustments
            for each year (or its inverse, if target_year precedes
            base_year).
        """
        return InflationAdjust(self)

    def __len__(self):
        """ The number of years modelled by the Scenario. """
        # pylint: disable=invalid-length-returned
        # This returns a positive integer (see type/value-check in init)
        return self.num_years

    def __iter__(self):
        """ Iterates over years modelled by the Scenario.

        Yields:
            int: Each year modelled by the Scenario, in ascending order.
        """
        for year in range(self.initial_year, self.initial_year + len(self)):
            yield year


class InflationAdjust(object):
    """ Callable inflation_adjust object with mutable state.

    Attributes:
        scenario (Scenario): A `Scenario` defining an
            `accumulation_function` for inflation over several years.
    """

    # We do provide public methods, but they're overrides of magic
    # methods (init and call). Anyways, the purpose of this class is
    # to expose its state (which a method/function/lambda does not do).
    # pylint: disable=too-few-public-methods

    def __init__(self, scenario):
        """ Inits InflationAdjust. """
        self.scenario = scenario

    def __call__(self, target_year, base_year=None):
        """ Inflation-adjustment factor from base_year to target_year.

        Args:
            target_year (int): The year for which an
                inflation-adjustment factor is desired.
            base_year (int): The year in which inflation-adjusted
                figures are expressed.

                The inflation adjustment for this year is 1 and the
                inflation adjustment for target_year is defined relative
                to this year.

                Optional. Defaults to the initial year of the object's
                `scenario` attribute.

        Returns:
            Decimal: The inflation-adjustment factor from base_year to
            target_year. This is the product of inflation-adjustments
            for each year (or its inverse, if target_year precedes
            base_year).
        """
        if base_year is None:
            base_year = self.scenario.initial_year
        # TODO: Cache inflation adjustments (memoize accumulation_function?)
        return self.scenario.accumulation_function(base_year, target_year)

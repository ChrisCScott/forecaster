""" Basic economic classes, such as `Scenario` and `Money`. """
import collections
from decimal import Decimal
from settings import Settings


class Scenario(object):
    """ Describes an economic scenario over the course of the simulation.

    For example, provides inflation rates and rates of return for each
    year of the simulation. This is the foil to `Strategy`; all
    `Scenario` information is reflective of broader economic trends and
    is independent of any user action.

    Attributes:
        inflation (dict): A dict of {year, inflation} pairs where the
            year is an int and inflation is a Decimal.
        stock_return (dict): A dict of {int, Decimal} pairs where the
            key is the year and the Decimal is the rate of return for
            stocks.
        bond_return (dict): A dict of {int, Decimal} pairs where the
            key is the year and the Decimal is the rate of return for
            bonds.
        other_return (dict): A dict of {int, Decimal} pairs where the
            key is the year and the Decimal is the rate of return for
            stocks.
            Optional. If not provided, uses value from Settings.
        management_fees (dict): A dict of {int, Decimal} pairs where the
            key is the year and the Decimal is the management fees on
            investments.
            Optional. If not provided, uses value from Settings.
        person1_raise_rate (dict): A dict of {int, Decimal} pairs where
            the key is the year and the Decimal is the percentage rate
            of growth in wages for person1 (e.g. a 3% raise is
            `Decimal(0.03)`).
            Optional. If not provided, uses value from Settings.
        person2_raise_rate (dict): A dict of {int, Decimal} pairs where
            the key is the year and the Decimal is the percentage rate
            of growth in wages for person2 (e.g. a 3% raise is
            `Decimal(0.03)`).
            Optional. If not provided, uses value from Settings.
        initial_year (int): The first year of the simulation.
            Optional. If not provided, uses value from Settings.
    """

    def __init__(self, inflation=None, stock_return=None, bond_return=None,
                 other_return=None, management_fees=None, initial_year=None,
                 num_years=None, settings=Settings, **kwargs):
        """ Constructor for `Scenario`.

        Arguments may be dicts (of {year, value} pairs), lists (or
        similar `Sequence`) or scalar values.

        When an argument is not provided, the corresponding value from
        the defaults provided by `settings` is used.

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
            TypeError: Input with unexpected type.
            ValueError: Input lists not of matching lengths.
        """
        # Set the years that the Scenario spans:
        # NOTE: If we decouple Scenario from Settings for implicit init,
        # it would make sense to implicitly set these values by
        # inspecting other inputs. E.g. Find initial_year by doing
        # `max(min(d) for d in dict_inputs)`
        # and find num years by doing
        # `min(max(d) for d in dict_inputs) - initial_year + 1`
        # (But be sure to check for negative num_year)
        # This won't work if all inputs are non-dict, which is probably
        # OK; test for that situation as well.
        self.initial_year = int(initial_year) if initial_year is not None \
            else int(settings.initial_year)
        self.num_years = int(num_years) if num_years is not None \
            else int(settings.num_years)

        # Now build dicts from the inputs
        self.inflation = self._build_dict(
            inflation, self.initial_year, settings.inflation)
        self.stock_return = self._build_dict(
            stock_return, self.initial_year, settings.stock_return)
        self.bond_return = self._build_dict(
            bond_return, self.initial_year, settings.bond_return)
        self.other_return = self._build_dict(
            other_return, self.initial_year, settings.other_return)
        self.management_fees = self._build_dict(
            management_fees, self.initial_year, settings.management_fees)

    @staticmethod
    def _build_dict(input=None, initial_year=None, default=None):
        """ Helper function that turns `input` into a dict.

        The resulting dict has {year, value} pairs. If the input is a
        list, the dict starts with `initial_year` and builds
        sequentially from there.

        Args:
            input (*, list, dict): A object that may be a list (or other
                Sequence), dict, or non-list non-dict scalar value.
                Optional. If not provided, uses default value.
            initial_year (int): The initial year, used when `input` is
                a list. The first element in the list corresponds to
                this year.
            default (*): If provided, builds a defaultdict with this
                value as the default factory. Must be convertible to
                Decimal.

        Raises:
            ValueError: initial_year is required if input is a list.
            ValueError: default cannot be set for scalar input.
            ValueError: input and default cannot both be None.
        """
        # If no input is provided, use default as input.
        if input is None:
            if default is None:
                raise ValueError(
                    'Scenario: input and default cannot both be None.')
            return Scenario._build_dict(default, initial_year)

        # Convert a non-callable `default` to a Decimal-returning
        # default factory:
        if default is not None and not callable(default):
            _default = Decimal(default)

            def default():
                return _default

        if isinstance(input, collections.defaultdict):
            # Update input's default factory if `default` was provided:
            if default is not None:
                input.default_factory = default
            # Convert elements to {int: Decimal} pairs
            return collections.defaultdict(input.default_factory, {
                int(key): Decimal(input[key]) for key in input
            })

        # IF input was a dict, cast to default dict (if default was
        # provided) and type-cast all entries to {int: Decimal} pairs.
        # NOTE: Consider whether we should wrap input in a defaultdict
        # to avoid stripping away the properties of custom dict-derived
        # objects that the user decides to pass in.
        if isinstance(input, dict):
            if default is not None:
                return collections.defaultdict(default, input)
            else:
                return {int(key): Decimal(input[key]) for key in input}

        # If it's not a dict, but it is iterable then convert it into a
        # [default]dict
        if isinstance(input, collections.Iterable):
            if initial_year is None:
                raise ValueError(
                    'Scenario: initial_year is required if input is a list.')
            if default is not None:
                return collections.defaultdict(default, {
                    key: Decimal(input[key - initial_year])
                    for key in range(initial_year, initial_year + len(input))
                })
            else:
                return {
                    key: Decimal(input[key - initial_year])
                    for key in range(initial_year, initial_year + len(input))
                }

        # Otherwise, turn a scalar value into a defaultdict:
        # NOTE: default is ignored in this case
        input = Decimal(input)
        return collections.defaultdict(lambda: input)

    def discount_rate(self, year):
        """ Returns the discount rate for `year`.
        This is the same as calling `inflation(year)` """
        return self.inflation[year]

    def accumulation_function(self, year1, year2):
        """ Returns the discount to be applied over the period from
        `year1` to `year2`. If `year1 > year2` then the discount rate is
        inverted. """

        # TODO: Cache list of accumulations from Settings.displayYear
        # to each other year? This method gets a lot of use, so it would
        # be more efficient. But remember to check for changes to
        # Settings.displayYear. """
        accum = 1
        if year1 <= year2:
            # Find the product of all intervening years' discount rates
            for year in range(year1, year2):
                accum = accum*(1+self.discount_rate(year))
            return accum
        else:  # Same as above, except invert the result ()
            for year in range(year2, year1):
                accum = accum*(1+self.discount_rate(year))
            return 1/accum

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

    def inflation_adjust(self, target_year, base_year=None):
        """ Inflation-adjustment factor from base_year to target_year.

        Args:
            target_year (int): The year for which an
                inflation-adjustment factor is desired.
            base_year (int): The year in which inflation-adjusted
                figures are expressed.
                The inflation adjustment for this year is 1.

        Returns:
            Decimal: The inflation-adjustment factor from base_year to
            target_year. This is the product of inflation-adjustments
            for each year (or its inverse, if target_year precedes
            base_year).
        """
        if base_year is None:
            base_year = self.initial_year
        # TODO: Cache inflation adjustments (memoize accumulation_function?)
        return self.accumulation_function(base_year, target_year)

    def rate_of_return(self, year, stocks, bonds, other):
        """ The rate of return on a portfolio for a given year.

        Args:
            year (int): The year.
            stocks (Decimal): The proportion of stocks in the portfolio.
            fixed_income (Decimal): The proportion of bonds assets in
                the portfolio.

        Returns:
            Decimal: The rate of return, as a pecentage. For example, a
            5% rate of return would be `Decimal('0.05')`.
        """
        return (stocks * self.stock_return[year] +
                bonds * self.bond_return[year] +
                other * self.other_return[year]) / (stocks + bonds + other)

    def __len__(self):
        """ The number of years modelled by the Scenario. """
        return self.num_years

    def __iter__(self):
        """ Iterates over years modelled by the Scenario.

        Yields:
            int: Each year modelled by the Scenario, in ascending order.
        """
        for year in range(self.initial_year, self.initial_year + len(self)):
            yield year

""" Basic economic classes, such as `Scenario` and `Money`. """
import collections
from numbers import Number
from settings import Settings


class Scenario(object):
    """ Describes an economic scenario over the course of the simulation.

    For example, provides inflation rates and rates of return for each
    year of the simulation. This is the foil to `Strategy`; all
    `Scenario` information is reflective of broader economic trends and
    is independent of any user action.

    Attributes:
        inflation (dict): A dict of {int, Decimal} pairs where the key
            is the year and the Decimal is the rate of inflation.
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

        # If input is already a default dict, update its default factory
        # (if a default was provided) and return it without wrapping.
        if isinstance(input, collections.defaultdict):
            if default is not None:
                input.default_factory = lambda: default
            return input

        # Cast input to a defaultdict if input is a dict (but not a
        # defaultdict).
        # NOTE: Consider whether we should wrap input in a defaultdict
        # to avoid stripping away the properties of custom dict-derived
        # objects that the user decides to pass in.
        if isinstance(input, dict):
            if default is not None:
                return collections.defaultdict(lambda: default, input)
            return input

        # If it's not a dict, but it is some sort of sequence (e.g. a
        # list) then convert it into a [default]dict
        if isinstance(input, collections.Sequence):
            if initial_year is None:
                raise ValueError(
                    'Scenario: initial_year is required if input is a list.')
            if default is not None:
                return collections.defaultdict(
                    lambda: default,
                    zip(range(initial_year, initial_year + len(input)),
                        input)
                    )
            return dict(zip(range(initial_year, initial_year + len(input)),
                            input))

        # Otherwise, turn a scalar value into a defaultdict:
        # NOTE: default is ignored in this case
        return collections.defaultdict(lambda: input)

    def __init__(self, inflation=None, stock_return=None, bond_return=None,
                 other_return=None, management_fees=None,
                 person1_raise_rate=None, person2_raise_rate=None,
                 initial_year=None, settings=Settings):
        """ Constructor for `Scenario`.

        Arguments may be dicts (of {year, value} pairs), lists (or
        similar `Sequence`) or scalar values.

        When an argument is not provided, the corresponding value from
        the defaults provided by `settings` is used.

        Lists must have matching lengths. Each element provides a value
        for a year, starting with `initial_year`. Dicts can be of any
        size; any missing key values are filled in with defaults.

        Args:
            inflation (Decimal, list, dict): The rate of inflation.
            stock_return (Decimal, list, dict): The rate of return for
                stocks.
            bond_return (Decimal, list, dict): The rate of return for
                bonds.
            other_return (Decimal, list, dict): The rate of return for
                other assets.
            management_fees (Decimal, list, dict): The management fees
                charged on investments.
            person1_raise_rate (Decimal, list, dict): The amount that is
                expected for a raise for person1 this year, expressed as
                a percentage (e.g. 0.05 for a 5% raise).
            person2_raise_rate (Decimal, list, dict): The amount that is
                expected for a raise for person2 this year, expressed as
                a percentage (e.g. 0.05 for a 5% raise).
            initial_year (int): The first year of the projection.

        Raises:
            TypeError: Input with unexpected type.
            ValueError: Input lists not of matching lengths.
        """
        # First, take an inventory of the inputs that can be scalars,
        # lists, or dicts:
        inputs = [inflation, stock_return, bond_return, other_return,
                  management_fees, person1_raise_rate, person2_raise_rate]
        # Then store the non-empty list and dict inputs for future use:
        list_inputs = [input for input in inputs if isinstance(input, list) and
                       input != []]
        dict_inputs = [input for input in inputs if isinstance(input, dict) and
                       input != {}]

        # List args are interpreted based on initial_year, so if
        # initial_year either use the initial year from settings or
        # use the earlier year represented in any dict inputs.
        if initial_year is None:
            if dict_inputs != []:
                dict_initial_years = [min(input.keys())
                                      for input in dict_inputs]
                initial_year = min(dict_initial_years)
                initial_year = min(initial_year, settings.initial_year)
            else:
                initial_year = settings.initial_year
        # If initial_year was provided, do a type-check/conversion:
        elif initial_year != int(initial_year):
            raise ValueError(
                'Scenario: initial_year must be convertible to int.')
        else:
            initial_year = int(initial_year)

        # Now build dicts from the inputs
        self.inflation = self._build_dict(
            inflation, initial_year, settings.inflation)
        self.stock_return = self._build_dict(
            stock_return, initial_year, settings.stock_return)
        self.bond_return = self._build_dict(
            bond_return, initial_year, settings.bond_return)
        self.other_return = self._build_dict(
            other_return, initial_year, settings.other_return)
        self.management_fees = self._build_dict(
            management_fees, initial_year,
            settings.management_fees)
        self.person1_raise_rate = self._build_dict(
            person1_raise_rate, initial_year, settings.person1_raise_rate)
        self.person2_raise_rate = self._build_dict(
            person2_raise_rate, initial_year, settings.person2_raise_rate)
        self.initial_year = initial_year

        # If any inputs were lists, confirm they're all the same length:
        # First, get lists of the list/dict input lengths.
        # (NOTE: For dicts, use their span, not the __len__ measure of
        # length, which is just the number of keys. The span is the
        # number of years covered by the dict)
        list_lengths = [len(x) for x in list_inputs]
        dict_lengths = [max(x.keys()) - self.initial_year for x in dict_inputs]
        # Ensure they're all the same length:
        if list_lengths != []:
            if not all(list_lengths[0] == length for length in list_lengths):
                raise ValueError(
                    'Scenario: Input lists must be matching lengths.')
            # Ensure list inputs are at least as long as the longest dict
            if dict_lengths != []:
                if list_lengths[0] < max(dict_lengths):
                    raise ValueError('Scenario: Input lists must cover at ' +
                                     'least the same dates as dict inputs.')

        # While we're at it, let's set __len using *_lengths
        self.__len = 1  # We have at least one year entry
        if list_lengths != []:
            self.__len = max(list_lengths)
        if dict_lengths != []:
            self.__len = max(self.__len, max(dict_lengths))

    # TODO: Update data model based on the new __init__

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

    def real_value(self, value, nominal_year, real_year=None,
                   settings=Settings):
        """ Returns a value expressed in `real_year` terms.

        If `real_year` is not provided, uses the current display year
        (see `Settings`). """
        if real_year is None:
            real_year = settings.display_year
        discount = self.accumulation_function(nominal_year, real_year)
        return value*discount

    def __len__(self):
        """ Returns the number of years modelled by the Scenario. """
        return self.__len

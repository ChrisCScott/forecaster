''' This module provides basic economic classes, such as `Scenario` and `Money` '''
import collections
from numbers import Number
from settings import Settings

# Define `ScenarioYear` to have elements inflation, stock_return, and bond_tuple
ScenarioYear = collections.namedtuple("ScenarioYear", "inflation stock_return bond_return")

class Scenario:
    ''' Describes an economic scenario over the course of the simulation. For example,
    provides inflation rates and rates of return for each year of the simulation. This
    is the foil to `Strategy`; all `Scenario` information is reflective of broader
    economic trends and is independent of any user action. A `Scenario` is immutable.  '''

    def __init__(self, inflation, stock_return, bond_return, initial_year=None):
        ''' Constructor for `Scenario`. Arguments must be lists (or similar `Sequence`) with
        matching lengths. Each element corresponds to a year, starting with `initial_year`.
        If `initial_year` is not provided, the object will use `Settings.initialYear`. '''
        if not (isinstance(inflation, collections.Sequence) and \
                isinstance(stock_return, collections.Sequence) and \
                isinstance(bond_return, collections.Sequence)):
            raise TypeError("Scenario: Unexpected non-sequence object passed to __init__")
        if not (len(inflation) == len(stock_return) and len(inflation) == len(bond_return)):
            raise ValueError("Scenario: Input lists are not of matching lengths")
        if not (initial_year is None or isinstance(initial_year, Number)):
            raise TypeError("Scenario: initial_year must be numeric")
        self._inflation = inflation
        self._stock_return = stock_return
        self._bond_return = bond_return
        self._initial_year = initial_year

    def __index(self, year):
        ''' Returns the list index corresponding to `year` '''
        return year - Settings.initial_year

    def initial_year(self):
        ''' Returns the initial year (`Settings.initial_year` if none is provided) '''
        if self._initial_year is None:
            return Settings.initial_year
        else:
            return self._initial_year

    def inflation(self, year):
        ''' Returns the inflation rate for `year` '''
        return self._inflation[self.__index(year)]

    def stock_return(self, year):
        ''' Returns the rate of return on stocks for `year` '''
        return self._stock_return[self.__index(year)]

    def bond_return(self, year):
        ''' Returns the rate of return on bonds for `year` '''
        return self._bond_return[self.__index(year)]

    def discount_rate(self, year):
        ''' Returns the discount rate for `year`.
        This is the same as calling `inflation(year)` '''
        return self.inflation(year)

    def accumulation_function(self, year1, year2):
        ''' Returns the discount to be applied over the period from `year1`
        to `year2`. If `year1 > year2` then the discount rate is inverted. '''
        ''' TODO: Cache list of accumulations from Settings.displayYear to each
        other year? This method gets a lot of use, so it would be more efficient.
        But remember to check for changes to Settings.displayYear '''
        accum = 1
        if year1 <= year2: # Find the product of all intervening years' discount rates
            for year in range(year1, year2):
                accum = accum*(1+self.discount_rate(year))
            return accum
        else: # Same as above, except invert the result ()
            for year in range(year2, year1):
                accum = accum*(1+self.discount_rate(year))
            return 1/accum

    def real_value(self, value, nominal_year, real_year=None):
        ''' Returns a value expressed in `real_year` terms based on this `Scenario` object.
        If `real_year` is not provided, uses the current display year (see `Settings`) '''
        if real_year is None:
            real_year = Settings.display_year
        discount = self.accumulation_function(nominal_year, real_year)
        return value*discount

    def __len__(self):
        ''' Returns the number of years modelled by the `Scenario` object '''
        return len(self._inflation)

    def __getitem__(self, year):
        ''' `self[year]` returns a `ScenarioYear` named tuple for `year`.
        Thus, `self[year].inflation` is the same as `self.inflation(year)` '''
        return ScenarioYear(inflation=self.inflation(year), stock_return=self.stock_return(year),
                            bond_return=self.bond_return(year))

class ConstantScenario(Scenario):
    ''' A simplified `Scenario` class where values are the same for each year.
    Useful for allowing users to set economic assumptions for simple tests.'''
    def __init__(self, inflation, stock_return, bond_return, initial_year=None): #pylint: disable=W0231
        ''' Constructor for `ConstantScenario`. Arguments must be numeric.
        The same numeric value is used for each year.` '''
        if not isinstance(inflation, Number) or not isinstance(stock_return, Number) or \
           not isinstance(bond_return, Number) or (not isinstance(initial_year, Number) and \
           not initial_year is None):
            raise TypeError("ConstantScenario: Unexpected non-numeric argument")
        self._inflation = inflation
        self._stock_return = stock_return
        self._bond_return = bond_return
        self._initial_year = initial_year

    def inflation(self, year=None): # `year` argument kept to override parent class
        ''' Returns the inflation rate for `year` '''
        return self._inflation

    def accumulation_function(self, year1=None, year2=None):
        ''' Returns the discount to be applied over the period from `year1`
        to `year2`. If `year1 > year2` then the discount rate is inverted. '''
        return pow(1+self.inflation(), year2-year1)

    def stock_return(self, year=None):
        ''' Returns the rate of return on stocks for `year` '''
        return self._stock_return

    def bond_return(self, year=None):
        ''' Returns the rate of return on bonds for `year` '''
        return self._bond_return

    def __len__(self):
        ''' Returns `Settings.num_years` '''
        return Settings.num_years

class DefaultScenario(ConstantScenario):
    ''' A constant `Scenario` that always returns the corresponding values of
    `Settings.DefaultScenario` '''

    def __init__(self): #pylint: disable=W0231
        ''' Constructs a `DefaultScenario` object without calling superclass methods '''
        pass

    def initial_year(self):
        ''' Returns `Settings.initial_year` '''
        return Settings.initial_year

    def inflation(self, year=None):
        ''' Returns `Settings.ScenarioDefaults.inflation` '''
        return Settings.ScenarioDefaults.inflation

    def stock_return(self, year=None):
        ''' Returns `Settings.ScenarioDefaults.stock_return` '''
        return Settings.ScenarioDefaults.stock_return

    def bond_return(self, year=None):
        ''' Returns `Settings.ScenarioDefaults.bond_return` '''
        return Settings.ScenarioDefaults.bond_return

default_scenario = DefaultScenario()

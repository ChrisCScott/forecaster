''' Defines a `Money` class that natively supports conversions between nominal and real values '''

import locale
from decimal import Decimal
from settings import Settings
from scenario import default_scenario

class Money:
    ''' This class represents the nominal (present) value of money in a given year. `Decimal` is
    used internally to represent values. It can generate real/future values (this requires providing
    a `Scenario` object). Basic mathematical operations are provided between `Money` objects. '''

    # TODO: Implement basic math operations (+, -, /, *) via overloading and via methods

    def __init__(self, nominalValue=0, year=None):
        ''' Constructs an instance of `Money`. If a year is not explicitly provided,
        the instance will assume that the amount is expressed in real terms, with
        `Settings.displayYear` as the base year '''
        if isinstance(nominalValue, Money):
            self.__nominal_value = nominalValue.nominal_value()
            self.__year = nominalValue.year()
        else:
            self.__nominal_value = Decimal(nominalValue)
            if year is None:
                self.__year = Settings.display_year
            else:
                self.__year = year

    # TODO: Move real-value operations to Scenario?
    def real_value(self, scenario=None, year=None):
        ''' Determines the real value of this `Money` instance, where `year` is the base year.
        If `year` is not explicitly provided, `Settings.displayYear` will be used.
        If  `scenario` is not explicitly provided, the values of `Settings.Defaults` are used. '''
        if year is None:
            year = Settings.display_year
        if scenario is None:
            scenario = DEFAULT_SCENARIO
        discount = Decimal(scenario.accumulation_function(self.__year, year))
        return self.__nominal_value*discount

    def nominal_value(self):
        ''' Returns the nominal value of the `Money` object '''
        return self.__nominal_value

    def year(self):
        ''' Returns the year in which the `Money` object's nominal value is expressed. '''
        return self.__year

    def nominal_str(self):
        ''' Returns the nominal value as a locale-specific string '''
        return locale.currency(self.nominal_value())

    def real_str(self, scenario=None, year=None):
        ''' Returns the real value as a locale-specific string. See `real_value`
        for argument descriptions. '''
        return locale.currency(self.real_value(scenario, year))

    def __str__(self):
        ''' Returns the nominal value as a locale-specific string '''
        return self.nominal_str()

    def __add__(self, other):
        ''' Overloads the `+` operator. Returns a `Money` object. If adding another
        `Money` object, the objects must be expressed in the same year. '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return Money(self.__nominal_value + other.nominal_value(), self.__year)
        else:
            return Money(self.__nominal_value + Decimal(other), self.__year)

    def __radd__(self, other):
        ''' Overloads the `+` operator for instances where `self` is the second operand. '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return Money(self.__nominal_value + other.nominal_value(), self.__year)
        else:
            return Money(self.__nominal_value + Decimal(other), self.__year)

    def __neg__(self):
        ''' Overloads the unary `-` operator. '''
        return Money(-self.__nominal_value, self.__year)

    def __sub__(self, other):
        ''' Overloads the `-` operator. Returns a `Money` object.
        If adding another `Money` object, the objects must be expressed in the same year. '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return Money(self.__nominal_value - other.nominal_value(), self.__year)
        else:
            return Money(self.__nominal_value - Decimal(other), self.__year)

    def __rsub__(self, other):
        ''' Overloads the `-` operator for instances where `self` is the second operand. '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return Money(other.nominal_value() - self.__nominal_value, self.__year)
        else:
            return Money(Decimal(other) - self.__nominal_value, self.__year)

    def __mul__(self, other):
        ''' Overloads the `*` operator. Returns a `Money` object.
        Must be multiplied by a non-`Money` numeric type. '''
        if isinstance(other, Money):
            raise TypeError("Cannot multiply two objects of type Money.")
        return Money(self.__nominal_value * Decimal(other), self.__year)

    def __rmul__(self, other):
        ''' Overloads the `*` operator for instances where `self` is the second operand. '''
        if isinstance(other, Money):
            raise TypeError("Cannot multiply two objects of type Money.")
        return Money(self.__nominal_value * Decimal(other), self.__year)

    def __truediv__(self, other):
        ''' Overloads the `/` operator for instances where the `Money` object is the
        numerator. If the denominator is also a `Money` object, it must have the same
        year and returns a scalar. If the denominator is scalar, it returns a `Money`
        object with the same year as `self`. '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return self.__nominal_value / other.nominal_value()
        else:
            return Money(self.__nominal_value / Decimal(other), self.__year)

    def __rtruediv__(self, other):
        ''' Overloads the `/` operator for instances where the `Money` object is the
        denominator. If the numerator is also a `Money` object, it must have the same
        year and returns a scalar. If the denominator is scalar, it returns a `Money`
        object with the same year as `self`. '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return other.nominal_value() / self.__nominal_value
        else:
            return Money(Decimal(other) / self.__nominal_value, self.__year)

    def __abs__(self):
        ''' Overloads the `abs()` operator. '''
        return Money(abs(self.__nominal_value), self.__year)

    def __float__(self):
        ''' Overloads the implicit `float` conversion '''
        return float(self.__nominal_value)

    def __round__(self, ndigits=0):
        ''' Overloads the `round([ndigits])` operator. '''
        return Money(round(self.__nominal_value, ndigits), self.__year)

    def __lt__(self, other):
        ''' Overloads the `<` operator. If the other object is of type `Money`,
        then the objects must be expressed in the same year. '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return self.__nominal_value < other.nominal_value()
        else:
            return self.__nominal_value < other

    def __eq__(self, other):
        ''' Overloads the `=` operator. If the other object is of type `Money`,
        then the objects must be expressed in the same year.
        Differs from `Decimal` in that differently-signed 0-values are equal '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return self.__nominal_value == other.nominal_value() or \
                  (self.__nominal_value == 0 and self.nominal_value() == 0)
        else:
            return self.__nominal_value == other

    def __gt__(self, other):
        ''' Overloads the `>` operator. If the other object is of type `Money`,
        then the objects must be expressed in the same year. '''
        if isinstance(other, Money):
            if self.__year != other.year():
                raise ValueError("Money: Attempt to compare objects with different years")
            return self.__nominal_value > other.nominal_value()
        else:
            return self.__nominal_value > other

    def __ne__(self, other):
        ''' Overloads the `!=` operator. '''
        return not self == other

    def __le__(self, other):
        ''' Overloads the `<=` operator. '''
        return self < other or self == other

    def __ge__(self, other):
        ''' Overloads the `>=` operator. '''
        return self > other or self == other

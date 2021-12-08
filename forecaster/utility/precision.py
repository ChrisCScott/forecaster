""" A module relating to precision of arithmetic operations.

Used throughout the application, without any dependency on any other
modules from this project.
"""

from numbers import Real
from typing import TypeVar

EPSILON = 0.00001

_HIGH_PRECISION_ATTR_NAME = 'high_precision'

# A type definition for numbers which optionally use a high-precision
# datatype, such as `Decimal`. For use with type hints throughout the
# application.
HighPrecisionNumber = TypeVar('HighPrecisionNumber', int, Real)
HighPrecisionOptional = float | int | HighPrecisionNumber

class HighPrecisionOptionalProperty(object):
    """ Descriptor for optionally high-precision numerical types.

    Objects with `HighPrecisionOptionalProperty` attributes must have a
    `high_precision` attribute of type
    `Optional[Callable[[float], HighPrecisionType]]`. An easy way to
    provide this is for the class to inherit from
    `HighPrecisionHandler`, although this is not required.

    Type-conversion occurs dynamically each time the property is read.

    Examples:
        ```
        from decimal import Decimal
        class Example(object):
            property = HighPrecisionOptionalProperty()
            def __init__(self, value, *, high_precision=None):
                self.high_precision = high_precision
                self.property = value
        obj = Example(5, high_precision=Decimal)
        obj.property # Returns Decimal(5)
        ```

        An equivalent example using `HighPrecisionHandler`:
        ```
        from decimal import Decimal
        class Example(HighPrecisionHandler):
            property = HighPrecisionOptionalProperty()
            def __init__(self, value, **kwargs):
                super.__init__()
                self.property = value
        obj = Example(5, high_precision=Decimal)
        obj.property # Returns Decimal(5)
        ```
    """

    def __init__(self):
        # Set by __set_name__
        self.public_name = None
        self.private_name = None

    def __set_name__(self, owner, name):
        # This method is called when the class containing properties
        # of this type is defined. It is the standard way
        # (in Python 3.6+) to create a private attribute for storing
        # values accessed by the descriptor.
        # See: https://docs.python.org/3/howto/descriptor.html#customized-names
        self.public_name = name
        self.private_name = '_' + name

    def __get__(self, obj, objtype=None, *, high_precision=None):
        """ Gets the value of the property, in high precision if able.

        This method returns the value that the property it has been set
        to, in a high-precision type if the object to which this
        property belongs supports it (via a non-`None` `high_precision`
        attribute).

        Raises:
            AttributeError: <classname> object has no attribute
                'high_precision'
        """
        # Get the native value to be (potentially) converted:
        value = getattr(obj, self.private_name)

        # Skip ahead if calling code provided `high_precision`:
        if high_precision is None:
            # Get the containing object's `high_precision` attribute.
            # (This raises AttributeError if the attribute is missing.)
            high_precision = getattr(obj, _HIGH_PRECISION_ATTR_NAME)
            # If no conversion required, return the native value:
            if high_precision is None:
                return value

        # Convert the native value and return it:
        if value is not None:
            return high_precision(value)
        return value

    def __set__(self, obj, value):
        # Just a basic setter; all conversion happens on get:
        setattr(obj, self.private_name, value)

class HighPrecisionOptionalPropertyCached(HighPrecisionOptionalProperty):
    """ Descriptor for optionally high-precision numerical types.

    This variant of `HighPrecisionOptionalProperty` caches results to
    improve efficiency when getting the property's value. It is only
    suitable for *immutable* high-precision types! (Conversion methods
    provided by `high_precision` should be stateless as well!) Mutable
    types may result in incorrect returned values if previously-returned
    values are mutated by client code.

    Use is identical to `HighPrecisionOptionalProperty`. See that class
    for examples and further information.
    """

    def __init__(self):
        super().__init__()
        # Cached values (for efficient calls to __get__):
        self._high_precision_cache = None
        self._high_precision_value_cache = None

    def __get__(self, obj, objtype=None, *, high_precision=None):
        # When called by metaclass on class init, `obj` is None:
        if obj is None:
            return

        # Skip ahead if calling code provided `high_precision`:
        if high_precision is None:
            # Get the containing object's `high_precision` attribute.
            # (This raises AttributeError if the attribute is missing.)
            high_precision = getattr(obj, _HIGH_PRECISION_ATTR_NAME)
            # If no conversion required, return the native value:
            if high_precision is None:
                return getattr(obj, self.private_name)

        # Check to see if the previous return value is cached and can
        # be used for these inputs:
        if (
                # Confirm we have a cached value (this fails if a new
                # value has been set since the last call to __get__):
                self._high_precision_value_cache is not None and
                # Confirm that the conversion method is the same:
                self._high_precision_cache == high_precision):
            return self._high_precision_value_cache

        # If we can't use the cache, calculate a fresh value:
        value = super().__get__(
            obj, objtype=objtype,
            # To avoid a second lookup, pass in the `high_precision`
            # method we found here:
            high_precision=high_precision)

        # Update the cache to make the next call more efficient:
        self._high_precision_value_cache = value
        self._high_precision_cache = high_precision

        return value

    def __set__(self, obj, value):
        super().__set__(obj, value)
        # Invalidate the cache
        self._high_precision_value_cache = None

class HighPrecisionHandler(object):
    """ Supports both native and high-precision numerical types.

    This class is intended to be subclassed by classes which, by
    default, use native (lossy) numerical types for various members,
    but which can also be configured to represent those members using
    high-precision types (e.g. `Decimal`).

    This is useful because high-precision types are not always
    arithmetically compatible with native types. For example,
    `5*Decimal(1)` raises an exception, as multiplication and division
    are not supported between `Decimal` and `float`/`int`. Thus, if
    a class has a `float` member which may be multiplied by a user-input
    value, an exception will be raised if the user provides a `Decimal`
    value.

    The solution provided by this class is to allow client code to
    pass a callable object (e.g. the `Decimal` class itself) to convert
    lossy members into high-precision values. These members can be
    easily defined using the `@high_precision_optional` decorator, which
    handles type conversion dynamically.

    Examples:
        ```
        from decimal import Decimal
        class Example(HighPrecisionHandler):
            property = HighPrecisionOptionalProperty()
            def __init__(self, value, **kwargs):
                super.__init__()
                self.property = value
        obj = Example(5, high_precision=Decimal)
        obj.property # Returns Decimal(5)
        ```

    Arguments:
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type.

    Attributes:
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type.
    """

    def __init__(self, *, high_precision=None, **kwargs):
        super().__init__(**kwargs)
        self.high_precision = high_precision

    def precision_convert(self, value):
        """ Converts `value` to high-precision if possible.

        This method returns `value` if no high-precision conversion
        method has been provided (via the `high_precision` attribute).
        Otherwise, it attempts conversion by calling
        `high_precision(value)` and retuns the result.

        Arguments:
            value (float): A value to be converted.

        Returns:
            Either a float or a high-precision value in the type
            provided by `high_precision`'s return type.
        """
        if self.high_precision is not None:
            return self.high_precision(value)
        return value

""" A module providing types common to `forecaster` subpackages. """

from abc import abstractmethod
from typing import (
    Union, Callable, Protocol, TypeVar, runtime_checkable,
    SupportsFloat, SupportsIndex, Text, Type, Any, Optional)
from numbers import Real as PyReal
from decimal import Decimal
from fractions import Fraction


# Much of the below makes use of numeric types. However, mypy is sadly
# incompatible with Number, the broadest numerical type. See:
# https://github.com/python/mypy/issues/3186
# That's OK, since Real is the more-applicable ABC for monetary values.
# Non-Real Number types (like Complex) don't seem appropriate for
# representing monetary values. Sadly, mypy is also incompatible with
# Real (but for different reasons which might get fixed sooner.)
# So explicitly include concrete numeric types - Decimal, Fraction,
# float, and int.
# Note that Decimal is weirdly not of type Real due to its narrower type
# signatures. See:
# https://stackoverflow.com/questions/47237378/why-is-not-decimal-decimal1-an-instance-of-numbers-real
Real = Union[PyReal, Decimal, Fraction, float, int]

# When we define the Money protocol, we want to ensure that methods'
# signatures are consistent re: the Money type they use and the scalar
# types they use. (e.g., if using `float` as a Money type, we don't want
# to require that `__add__` support addition with arbitrary `Money`
# types. For example, `Decimal` does not support addition with `float`
# in general, but is an acceptable Money type.)
_Money = TypeVar('_Money')
_Scalar_contra = (  # pylint: disable=invalid-name
    TypeVar('_Scalar_contra', contravariant=True))

# Money is referenceable as `Money` or as `Money[X,Y]`, were X is the
# money type itself (e.g. `float`, `moneyed.Money`) and Y is the scalar
# type (e.g. `float`, `Decimal`).
@runtime_checkable
class MoneyABC(Protocol[_Money, _Scalar_contra]):
    """ An protocol (quasi-abstract base class) for Money types.

    Money types must support the following builtin operators:

    * Addition (+) and subtraction (-) with other Money values, though
      not necessarily with scalar values (e.g. Money(5) + 1 does not
      need to be well-defined.)
    * Scalar multiplication (*) and scalar division (/), where the other
      operand is a non-Money numeric. (e.g. 5*Money(5) yields Money(25))
    * Division (/) of two Money-typed objects must yield a scalar number
    * Comparison (<,>,=) between Money types, and also with int(0) (to
      test for negative values).
    * Rounding (`round`)
    * Hashing (`hash`)

    Note that multiplication of two Money-typed objects need not be well
    defined. All methods receiving or returing a scalar value must
    support the same scalar values.

    Numeric types implementing the Real protocol will generally
    implement this protocol as well. That is, any numeric value (other
    than Complex) can be interpreted as being of a Money type.

    Examples:
        m: Money  # m implements the `Money` protocol
        m: Money[float, float]  # m uses `float` for money and scalar
        m: Money[moneyed.Money, Decimal]  # m uses `moneyed.Money`
                                          # for money values and
                                          # `Decimal` for scalar values.
    """

    @abstractmethod
    def __add__(self, other: _Money) -> _Money:
        """ Adds two Money values. """
        raise NotImplementedError

    @abstractmethod
    def __sub__(self, other: _Money) -> _Money:
        """ Determines the difference between two Money values. """
        raise NotImplementedError

    @abstractmethod
    def __mul__(self, other: _Scalar_contra) -> _Money:
        """ Scalar multiplication of a Money object. """
        raise NotImplementedError

    @abstractmethod
    def __truediv__(
            self, other: Union[_Money, _Scalar_contra]
        ) -> Union[_Money, _Scalar_contra]:
        """ Division by another Money value or a scalar divisor. """
        raise NotImplementedError

    @abstractmethod
    def __round__(self, ndigits: int = None) -> _Money:
        """ Rounds to ndigits """
        raise NotImplementedError

    @abstractmethod
    def __hash__(self) -> int:
        """ Allows for use in sets and as dict keys. """
        raise NotImplementedError

    @abstractmethod
    def __eq__(self, other: object) -> bool:
        """ Allow comparison between Money objects (and also with 0).

        If a Money type supports multiple currencies, comparing values
        in different currencies may (but do not necessarily) raise a
        ValueError.
        """
        raise NotImplementedError

    @abstractmethod
    def __lt__(self, other: Union[_Money, _Scalar_contra]) -> bool:
        """ Allow comparison between Money objects (and also with 0).

        If a Money type supports multiple currencies, comparing values
        in different currencies may (but do not necessarily) raise a
        ValueError.
        """
        raise NotImplementedError

    @abstractmethod
    def __gt__(self, other: Union[_Money, _Scalar_contra]) -> bool:
        """ Allow comparison between Money objects (and also with 0).

        If a Money type supports multiple currencies, comparing values
        in different currencies may (but do not necessarily) raise a
        ValueError.
        """
        raise NotImplementedError

# Any float-compatible value should be convertible to Money. (Note that
# this does not necessarily include non-numeric Money classes.
# This is because, e.g., `float` doesn't match `Money[Any, Any]`, but
# it should match `Money[Real, Any]`.
MoneyConvertible = Union[
    SupportsFloat, SupportsIndex, Text, bytes, bytearray]

# Define a TypeVar for convenience. Use this to ensure that a specific
# numeric type or custom class implementing MoneyABC is used by a
# Generic class. (e.g. `class Custom(Generic[MoneyType]): ...`)
MoneyType = TypeVar(
    'MoneyType', MoneyABC, float, Decimal, Fraction, int)
# It is conventional to use CamelCase for `TypeVar` names, and to append
# `_co` when they are covariant.
# pylint: disable=invalid-name
MoneyType_co = TypeVar(
    'MoneyType_co', MoneyABC, float, Decimal, Fraction, int, covariant=True)
# pylint: enable=invalid-name

class MoneyFactory(Protocol[MoneyType_co]):
    """ Protocol for callable objects which return `MoneyType`.

    Many classes need to be able to cast numeric values to Money.
    Any 1-ary (excluding optional args) callable that takes a
    Money-convertible object and returns Money can be used for such
    conversion.

    Although this is not a TypeVar, it is bound to one (MoneyType).
    Classes can reference this without binding to MoneyType, in which
    case it will not enforce consistent typing across instance members.
    Classes can conveniently bind to MoneyType by inheriting from
    MoneyHandler, in which case MoneyFactory will return the same
    MoneyType as any other member of the class.

    MoneyFactoryUnion (and the corresponding MoneyUnion) are legacy
    non-Generic/TypeVar alternatives to MoneyFactory and MoneyType.
    """
    # The arg name `x` is what's used by `float.__call__`, so we use it
    # here as well to ensure compatibility:
    # pylint: disable=invalid-name
    @abstractmethod
    def __call__(
            self, x: MoneyConvertible,
            *args: Any, **kwargs: Any
        ) -> MoneyType_co:
        """ Takes a numeric (or other) value and returns Money. """
        raise NotImplementedError
    # pylint: disable=invalid-name

# For convenience, define a base class for any custom class that wants
# to bind the `MoneyType` TypeVar (including indirectly, e.g. to make
# use of MoneyFactoryProtocol)
class MoneyHandler(Protocol[MoneyType]):
    """ Convenience base class for classes taking a `money_factory` arg.

    Args:
        money_factory (MoneyFactory): A callable object that takes any
            Money-convertible type and returns a Money object.
            Keyword argument only. Optional.
        money_type (Money): A type object for the Money type used by
            this MoneyHandler instance. Used for type-checking;
            isinstance(x, money_type) should return True only if x
            is of type Money. Optional.

    Attributes:
        money_factory (MoneyFactory): A callable object that takes any
            Money-convertible type and returns a Money object.
            Keyword argument only. Optional.
        money_type (type): A type object corresponding to the return
            type of money_factory.
    """
    money_factory: MoneyFactory[MoneyType]
    money_type: Type[MoneyType]

    @abstractmethod
    def __init__(
            self, *args,
            money_factory: Optional[MoneyFactory[MoneyType]] = None,
            money_type: Optional[Type[MoneyType]] = None,
            **kwargs
    ) -> None:
        self.money_factory: MoneyFactory[MoneyType]
        self.money_type: Type[MoneyType]
        # We use `None` as a default value so that subclasses don't need
        # to know the default or test for None values.
        if money_factory is None:
            self.money_factory = float
        else:
            self.money_factory = money_factory

        if money_type is None:
            # Use the type of whatever money_factory returns:
            self.money_type = type(self.money_factory(0))
        else:
            self.money_type = money_type

# Classes which are not Generic (or free methods) can use Unions to
# describe Money and MoneyFactory:
MoneyUnion = Union[MoneyABC, float, Decimal, Fraction, int]

MoneyFactoryUnion = Union[
    Callable[[MoneyConvertible], MoneyUnion],  # General def. of money_factory
    Type[float], Type[Decimal], Type[Fraction], Type[int]] # numeric types

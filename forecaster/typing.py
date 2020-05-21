""" A module providing types common to `forecaster` subpackages. """

from abc import abstractmethod
from typing import (Union, Callable, Protocol, TypeVar, runtime_checkable)
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
MoneyType = TypeVar('MoneyType', "Money", Real)
ScalarType = TypeVar(
    'ScalarType', PyReal, Decimal, Fraction, float, int, contravariant=True)

# Money is referenceable as `Money` or as `Money[X,Y]`, were X is the
# money type itself (e.g. `float`, `moneyed.Money`) and Y is the scalar
# type (e.g. `float`, `Decimal`).
@runtime_checkable
class Money(Protocol[MoneyType, ScalarType]):
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
    def __add__(self, other: MoneyType) -> MoneyType:
        """ Adds two Money values. """
        raise NotImplementedError

    @abstractmethod
    def __sub__(self, other: MoneyType) -> MoneyType:
        """ Determines the difference between two Money values. """
        raise NotImplementedError

    @abstractmethod
    def __mul__(self, other: ScalarType) -> MoneyType:
        """ Scalar multiplication of a Money object. """
        raise NotImplementedError

    @abstractmethod
    def __div__(
            self, other: Union[MoneyType, ScalarType]
        ) -> Union[MoneyType, ScalarType]:
        """ Division by another Money value or a scalar divisor. """
        raise NotImplementedError

    @abstractmethod
    def __round__(self, ndigits: int = None) -> MoneyType:
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
    def __lt__(self, other: Union[MoneyType, ScalarType]) -> bool:
        """ Allow comparison between Money objects (and also with 0).

        If a Money type supports multiple currencies, comparing values
        in different currencies may (but do not necessarily) raise a
        ValueError.
        """
        raise NotImplementedError

    @abstractmethod
    def __gt__(self, other: Union[MoneyType, ScalarType]) -> bool:
        """ Allow comparison between Money objects (and also with 0).

        If a Money type supports multiple currencies, comparing values
        in different currencies may (but do not necessarily) raise a
        ValueError.
        """
        raise NotImplementedError

# Types that can be cast to Money should include any real number and
# of course Money itself:
MoneyConvertible = Union[Real, Money]

# Many classes need to be able to cast numeric values to Money.
# Any 1-ary callable that takes a Money-convertible object and returns
# Money can be used for such conversion.
MoneyFactory = Union[Callable[[MoneyConvertible], Money]]

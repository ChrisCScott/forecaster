""" A module providing a `Money` class.

`Money` is an extension of the `py-moneyed` `Money` class, with added
methods for rounding, hashing, and comparison with non-`Money` zero
values.
"""

from abc import abstractmethod
from typing import Union, Protocol
from numbers import Real as PyReal
from decimal import Decimal
from moneyed import Money as PyMoney

# Much of the below makes use of numeric types. However, mypy is sadly
# incompatible with Number, the broadest numerical type. See:
# https://github.com/python/mypy/issues/3186
# That's OK, since Real is the more-applicable ABC for monetary values.
# Non-Real Number types (like Complex) don't seem appropriate for
# representing monetary values. Sadly, mypy is also incompatible with
# Real (but for different reasons which might get fixed sooner.)
# So include float as a concrete fallback (this extends to int - yay!)
# Also explicitly include Decimal, which weirdly isn't a Real. See:
# https://stackoverflow.com/questions/47237378/why-is-not-decimal-decimal1-an-instance-of-numbers-real
Real = Union[PyReal, Decimal, float]

class Money(PyMoney):
    """ Extends py-moneyed to support Decimal-like functions. """

    # We're only extending Money's magic methods for convenience, not
    # adding new public methods.
    # pylint: disable=too-few-public-methods

    default_currency = 'CAD'

    def __init__(self, amount=Decimal('0.0'), currency=None):
        """ Initializes with application-level default currency.

        Also allows for initializing from another Money object.
        """
        if isinstance(amount, Money):
            super().__init__(amount.amount, amount.currency)
        elif currency is None:
            super().__init__(amount, self.default_currency)
        else:
            super().__init__(amount, currency)

    def __round__(self, ndigits=None):
        """ Rounds to ndigits """
        return Money(round(self.amount, ndigits), self.currency)

    def __hash__(self):
        """ Allows for use in sets and as dict keys. """
        # Equality of Money objects is based on amount and currency.
        return hash(self.amount) + hash(self.currency)

    def __eq__(self, other):
        """ Extends == operator to allow comparison with Decimal.

        This allows for comparison to 0 (or other Decimal-convertible
        values), but not with other Money objects in different
        currencies.
        """
        # NOTE: If the other object is also a Money object, this
        # won't fall back to Decimal, because Decimal doesn't know how
        # to compare itself to Money. This is good, because otherwise
        # we'd be comparing face values of different currencies,
        # yielding incorrect behaviour like JPY1 == USD1.
        return super().__eq__(other) or self.amount == other

    def __lt__(self, other):
        """ Extends < operator to allow comparison with 0 """
        if other == 0:
            return self.amount < 0
        return super().__lt__(other)

    def __gt__(self, other):
        """ Extends > operator to allow comparison with 0 """
        if other == 0:
            return self.amount > 0
        return super().__gt__(other)

class MoneyABC(Protocol):
    """ An protocol (quasi-abstract base class) for Money types.

    Money types must support the following builtin operators:

    * Addition (+) and subtraction (-), though not necessarily with
      arbitrary numeric types (e.g. Money(5) + 1 does not need to be
      well-defined.)
    * Scalar multiplication (*) and scalar division (/), where the other
      operand is a non-Money numeric. (e.g. 5*Money(5) yields Money(25))
    * Division (/) of two Money-typed objects must yield a scalar number
    * Comparison (<,>,=) between Money types, and also with int(0) (to
      test for negative values).
    * Rounding (`round`)
    * Hashing (`hash`)

    Note that multiplication of two Money-typed objects need not be well
    defined.

    Numeric types implementing the Real protocol will generally
    implement this protocol as well. That is, any numeric value (other
    than Complex) can be interpreted as being of a Money type.
    """

    @abstractmethod
    def __add__(self, other: "MoneyABC") -> "MoneyABC":
        """ Adds two Money values. """
        raise NotImplementedError

    @abstractmethod
    def __sub__(self, other: "MoneyABC") -> "MoneyABC":
        """ Determines the difference between two Money values. """
        raise NotImplementedError

    @abstractmethod
    def __mul__(self, other: Real) -> "MoneyABC":
        """ ScalaFloatiplication of a Money object. """
        raise NotImplementedError

    @abstractmethod
    def __div__(
            self, other: Union["MoneyABC", Real]
        ) -> Union["MoneyABC", Real]:
        """ Division by another Money value or a scalar divisor. """
        raise NotImplementedError

    @abstractmethod
    def __round__(self, ndigits: int = None) -> "MoneyABC":
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
    def __lt__(self, other: Union["MoneyABC", Real]) -> bool:
        """ Allow comparison between Money objects (and also with 0).

        If a Money type supports multiple currencies, comparing values
        in different currencies may (but do not necessarily) raise a
        ValueError.
        """
        raise NotImplementedError

    @abstractmethod
    def __gt__(self, other: Union["MoneyABC", Real]) -> bool:
        """ Allow comparison between Money objects (and also with 0).

        If a Money type supports multiple currencies, comparing values
        in different currencies may (but do not necessarily) raise a
        ValueError.
        """
        raise NotImplementedError

# For typing purposes, make it explicit that Money includes various
# numerical types.
MoneyType = Union[MoneyABC, Money, Real]

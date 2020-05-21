""" A module providing a `Money` class.

`Money` is an extension of the `py-moneyed` `Money` class, with added
methods for rounding, hashing, and comparison with non-`Money` zero
values.
"""

from decimal import Decimal
from moneyed import Money as PyMoney

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

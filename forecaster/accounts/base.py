""" A module providing the base Account class. """

import math
from decimal import Decimal
from forecaster.person import Person
from forecaster.ledger import (
    Money, TaxSource, recorded_property, recorded_property_cached)
from forecaster.utility import when_conv

class Account(TaxSource):
    """ An account storing a `Money` balance.

    Has a `balance` indicating the balance of the account at the start
    of the period (generally a year). Optionally, a rate of growth,
    `rate`, expressed as an apr (annual percentage rate) can be given.
    For example, a 5% apr could be passed as `rate=0.05`.

    May optionally also recieve one or more transactions defining a time
    series of inflows and outflows from the account. These transactions
    do not modify the `balance` directly; rather, they are applied
    to the balance, with any growth, when `next_year()` is called.
    A new `Account` object with an updated balance is generated; the
    calling object's balance does not change.

    Examples::

        account1 = Account(100, 0.05)
        account2 = account1.next_year()
        account1.balance == 100  # True
        account2.balance == 105  # True

    Attributes:
        balance (Money): The opening account balance for this year.
        balance_history (dict[int, Money]): `{year: balance}` pairs
            covering all years in the range `initial_year: this_year`
        rate (Decimal): The rate of return (or interest) for this year,
            before compounding.
        rate_history (dict[int, Decimal]): `{year: rate}` pairs covering
            all years in the range `initial_year: this_year`
        rate_function (callable): A callable object that gives the rate
            for each year. Has a signature of the form
            `rate(year) -> Decimal`.

            If this callable object relies on `Scenario` or other
            objects defined in the `forecaster` package, recommend
            passing an object that stores these objects explicitly
            as attributes (as opposed to a method/function where these
            objects are stored in the context), otherwise `Forecaster`'s
            object-substitution logic will not work.
        transactions (dict[Decimal, Money]): The transactions to/from
            the account for this year. `{when: value}` pairs, where:

            `when` describes the timing of the transaction in the year.
            In the range [0, 1].

            `value` is the sum of inflows and outflows at time `when`.
            Positive for inflows and negative for outflows.
        transactions_history (dict[int, dict[Decimal, Money]]):
            `{year: transactions}` pairs covering all years in the range
            `initial_year: this_year`
        returns (Money): The returns (losses) of the account for the
            year.
        returns_history (dict[int, Money]): `{year: returns}` pairs
            covering all years in the range `initial_year: this_year`
        nper (int, str): The compounding frequency. May be given as
            a number of periods (an int) or via a code (a str). Codes
            include:

            * C: Continuous (default)
            * D: Daily
            * W: Weekly
            * BW: Biweekly (every two weeks)
            * SM: Semi-monthly (twice a month)
            * M: Monthly
            * BM: Bimonthly (every two months)
            * Q: Quarterly (every 3 months)
            * SA: Semi-annually (twice a year)
            * A: Annually

        initial_year (int): The first year for which account data is
            recorded.
    """

    # Most of these instance attributes are hidden, and several support
    # corresponding properties (e.g. _transactions and transactions), so
    # they get counted twice.
    # pylint: disable=too-many-instance-attributes

    def __init__(
        self, owner,
        balance=0, rate=0, nper=1, inputs=None, initial_year=None
    ):
        """ Constructor for `Account`.

        This constructor receives only values for the first year.

        Args:
            owner (Person): The owner of the account. Optional.
            balance (Money): The balance for the first year
            rate (Decimal, callable): An object that gives the rate for
                each year, either as a constant value (e.g. a Decimal)
                or as a callable object with a signature of the form
                `rate(year) -> Decimal`.

                If this callable object relies on `Scenario` or other
                objects defined in the `forecaster` package, recommend
                passing an object that stores these objects explicitly
                as attributes (as opposed to a method/function where
                these objects are stored in the context), otherwise
                `Forecaster`'s object-substitution logic will not work.
            nper (int): The number of compounding periods per year.
            initial_year (int): The first year (e.g. 2000)
        """
        # This object requires a fair amount of state, and its arguments
        # are closely related. It doesn't make sense to break up the
        # class any further.
        # pylint: disable=too-many-arguments

        # Use the explicitly-provided initial year if available,
        # otherwise default to the owner's initial year:
        if initial_year is None:
            if not hasattr(owner, 'initial_year'):
                raise TypeError(
                    'Account: owner must have initial_year attribute.')
            else:
                initial_year = owner.initial_year
        super().__init__(initial_year=initial_year, inputs=inputs)

        # Set hidden attributes to support properties that need them to
        # be set in advance:
        self._owner = None
        self._transactions = {}
        self._rate_callable = None

        # We don't really have to do this, but it helps the linter
        # to understand that `transactions` is subscriptable:
        self.transactions = {}

        # Set the various property values based on inputs:
        self.owner = owner
        self.balance = Money(balance)
        self.rate_callable = rate
        self.nper = self._conv_nper(nper)
        # NOTE: returns is calculated lazily

    # String codes describing compounding periods (keys) and ints
    # describing the number of such periods in a year (values):
    _nper_mapping = {
        'C': None,
        'D': 365,
        'W': 52,
        'BW': 26,
        'SM': 24,
        'M': 12,
        'BM': 6,
        'Q': 4,
        'SA': 2,
        'A': 1
    }

    @property
    def owner(self):
        """ The account's owner. """
        return self._owner

    @owner.setter
    def owner(self, val):
        """ Sets the account's owner. """
        # Type-check the input
        if not isinstance(val, Person):
            raise TypeError('Account: owner must be of type Person.')
        # Unregister this account from any former owner:
        if self.owner is not None:
            self.owner.accounts.remove(self)
        # Register with new owner:
        val.accounts.add(self)
        self._owner = val

    @recorded_property_cached
    def balance(self):
        """ The balance of the account for the current year (Money).

        This is the balance after applying all transactions and any
        growth/losses from the rate.
        """
        # pylint: disable=method-hidden
        # Pylint gets confused by attributes added by metaclass.
        # This method isn't hidden in __init__; it's assigned to (by a
        # setter defined via metaclass)

        # First, grow last year's initial balance based on the rate:
        balance = self.value_at_time(
            # pylint: disable=no-member
            # Pylint gets confused by attributes added by metaclass.
            self._balance_history[self.this_year - 1], 'start', 'end')

        # Then, grow each transactions and add it to the year-end total.
        # NOTE: This accounts for both inflows and outflows; outflows
        # and their growth are negative and will reduce the balance.
        # pylint: disable=no-member
        # Pylint gets confused by attributes added by metaclass.
        transactions_history = self._transactions_history
        for when, value in transactions_history[self.this_year - 1].items():
            balance += self.value_at_time(value, when, 'end')

        return balance

    @property
    def rate_callable(self):
        """ A callable object that generates a rate for a given year.

        This object takes the signature `rate(year) -> Money` and must
        accept this `Account`'s `this_year` attribute as input.
        """
        return self._rate_callable

    @rate_callable.setter
    def rate_callable(self, val):
        """ Sets rate_callable.

        Attempts to convert non-callable objects to callable objects
        by returning `val[year]` if the object is a dict or simply
        returning `val` otherwise.
        """
        # If input isn't callable, convert it to a suitable method:
        if not callable(val):
            if isinstance(val, dict):
                # assume dict of {year: rate} pairs
                def func(year):
                    """ Wraps dict in a function. """
                    return val[year]
            else:
                # If we can cast this to Decimal, return a constant rate
                val = Decimal(val)

                def func(_):
                    """ Wraps value in a function. """
                    return val
            self._rate_callable = func
        else:
            # If the input is callable, use it without modification.
            self._rate_callable = val

    @recorded_property_cached
    def rate(self):
        """ The rate of the account for the current year (Decimal). """
        # pylint: disable=not-callable
        # rate_function's setter ensures that this is callable.
        return self.rate_callable(self.this_year)

    @recorded_property
    def transactions(self):
        """ The transactions in and out of the account this year (dict). """
        # pylint: disable=method-hidden
        # Pylint gets confused by attributes added by metaclass.
        # This method isn't hidden in __init__; it's assigned to (by a
        # setter defined via metaclass)

        return self._transactions

    @recorded_property
    def returns(self):
        """ Returns (losses) on the balance and transactions this year. """
        # Find returns on the initial balance.
        # This doesn't include any transactions or their growth.
        returns = (
            self.balance *
            (self.accumulation_function(1, self.rate, self.nper) - 1)
        )

        # Add in the returns on each transaction.
        # (Withdrawals will generate returns with the opposite sign of
        # the returns on the initial balance and prior inflows, thereby
        # cancelling out a portion of those returns.)
        for when in self.transactions:
            returns += (
                self.transactions[when] *
                (self.accumulation_function(
                    1 - when, self.rate, self.nper
                ) - 1)
            )

        return returns

    @classmethod
    def _conv_nper(cls, nper):
        """ Number of periods in a year given a compounding frequency.

        Args:
            nper (str, int): A code (str) indicating a compounding
                frequency (e.g. 'W', 'M'), an int, or None

        Returns:
            An int indicating the number of compounding periods in a
                year or None if compounding is continuous.

        Raises:
            ValueError: str nper must have a known value.
            ValueError: nper must be greater than 0.
            TypeError: nper cannot be losslessly converted to int.
        """
        # nper can be None, so return gracefully.
        if nper is None:
            return None

        # Try to parse a string based on known compounding frequencies
        if isinstance(nper, str):
            if nper not in cls._nper_mapping:
                raise ValueError('Account: str nper must have a known value')
            return cls._nper_mapping[nper]
        else:  # Attempt to cast to int
            if not nper == int(nper):
                raise TypeError(
                    'Account: nper is not losslessly convertible to int')
            if nper <= 0:
                raise ValueError('Account: nper must be greater than 0')
            return int(nper)

    @property
    def contribution_group(self):
        """ The Accounts that share contribution room with this one.

        For `Account`, this method returns a set containing only itself;
        that is, it does not share contribution room with any other
        `Account`s. However, subclasses (like `RegisteredAccount`) may
        override this behaviour.

        Returns:
            set[Account]: The `Account` objects that should be considered
            together with this `Account` when allocating contributions
            between them.

            Includes this `Account`.
        """
        return {self}

    def add_transaction(self, value, when='end'):
        """ Adds a transaction to the account.

        Args:
            value (Money): The value of the transaction. Positive values
                are inflows and negative values are outflows.
            when (float, Decimal, str): The timing of the transaction.
                Must be in the range [0,1] or be a suitable str input,
                as described in the documentation for `when_conv`.

        Raises:
            decimal.InvalidOperation: Transactions must be convertible
                to type Money and `when` must be convertible to type
                Decimal.
            ValueError: `when` must be in [0,1]
        """
        when = when_conv(when)

        # Try to cast non-Money objects to type Money
        if not isinstance(value, Money):
            value = Money(value)

        # If there's already a transaction at this time, then add them
        # together; simultaneous transactions are modelled as one sum.
        # pylint: disable=unsupported-membership-test
        # Pylint gets confused by attributes added by metaclass.
        if when in self.transactions:  # Add to existing value
            # pylint: disable=unsupported-assignment-operation
            # Pylint gets confused by attributes added by metaclass.
            self.transactions[when] += value
        else:  # Create new when/value pair.
            # pylint: disable=unsupported-assignment-operation
            # Pylint gets confused by attributes added by metaclass.
            self.transactions[when] = value  # pylint: disable=E1137

    # TODO: Add add_inflow and add_outflow methods? These could ignore
    # sign (or, for add_inflow, raise an error with negative sign) and
    # add an inflow (+) or outflow (-) with the magnitude of the input
    # arg and the appropriate sign.

    @recorded_property
    def inflows(self):
        """ The sum of all inflows to the account. """
        return Money(sum(
            val for val in self.transactions.values() if val.amount > 0)
        )

    @recorded_property
    def outflows(self):
        """ The sum of all outflows from the account. """
        return Money(sum(
            val for val in self.transactions.values() if val.amount < 0)
        )

    def __len__(self):
        """ The number of years of transaction data in the account. """
        return self.this_year - self.initial_year + 1

    @staticmethod
    def accumulation_function(t, rate, nper=1):
        """ The accumulation function, A(t), from interest theory.

        A(t) provides the growth (or discount) factor over the period
        [0, t]. If `t` is negative, this method returns the inverse
        (i.e. `A(t)^-1`).

        This method's output is not well-defined if `t` does not align
        with the start/end of a compounding period. (It will produce
        sensible output, but it might not correspond to how your bank
        calculates interest).

        Args:
            t (float, Decimal): Defines the period [0,t] over which the
                accumulation will be calculated.
            rate (float, Decimal): The rate of return (or interest).
            nper (int): The number of compounding periods per year.

        Returns:
            The accumulation A(t), as a Decimal.
        """
        # pylint: disable=invalid-name
        # `t` is the usual name for the input to A(t) in interest theory.

        # Convert t and rate to Decimal
        t = Decimal(t)
        rate = Decimal(rate)

        # Use the exponential formula for continuous compounding: e^rt
        if nper is None:
            # math.exp(rate * t) throws a warning, since there's an
            # implicit float-Decimal multiplication.
            acc = Decimal(math.e) ** (rate * t)
        # Otherwise use the discrete formula: (1+r/n)^nt
        else:
            acc = (1 + rate / nper) ** (nper * t)

        return acc

    def value_at_time(self, value, now='start', time='end'):
        """ Returns the present (or future) value.

        Args:
            value (Money): The (nominal) value to be converted.
            now (Decimal): The time associated with the nominal value.
            time (Decimal): The time to which the nominal value is to
                be converted.

        Returns:
            A Money object representing the present value
            (if now > time) or the future value (if now < time) of
            `value`.
        """
        return value * self.accumulation_function(
            when_conv(time) - when_conv(now), self.rate, self.nper
        )

    def balance_at_time(self, time):
        """ Returns the balance at a point in time.

        Args:
            when (Decimal, str): The timing of the transaction.
        """
        # We need to convert `time` to enable the comparison in the dict
        # comprehension in the for loop below.
        time = when_conv(time)

        # Find the future value (at t=time) of the initial balance.
        # This doesn't include any transactions of their growth.
        balance = self.value_at_time(self.balance, 'start', time)

        # Add in the future value of each transaction (except that that
        # happen after `time`).
        # Pylint is confused; `transactions` is a dict
        # pylint: disable=unsubscriptable-object,not-an-iterable
        for when in [w for w in self.transactions if w <= time]:
            balance += self.value_at_time(
                self.transactions[when], when, time
            )

        return balance

    def next_year(self):
        """ Adds another year to the account.

        This method will call the next_year method for the owner if they
        haven't been advanced to the next year.
        """
        # Ensure that the owner has been brought up to this year
        while self.owner.this_year < self.this_year:
            self.owner.next_year()

        # Now increment year via superclass:
        super().next_year()

        # Clear out transactions for the new year:
        self._transactions = {}

    def max_outflow(self, when='end'):
        """ An outflow which would reduce the end-of-year balance to 0.

        NOTE: This does not guarantee that the account balance will not
        be negative at a time between `when` and `end`.

        Args:
            when (When): The timing of the transaction.

        Returns:
            A value which, if withdrawn at time `when`, would make the
            account balance 0 at the end of the year, after all
            transactions are accounted for.
        """
        # If the balance is positive, the max outflow is simply the
        # current balance (but negative). If the balance is negative,
        # then there's no further outflows to be made.
        return min(-self.balance_at_time(when), Money(0))

    def max_inflow(self, when='end'):
        """ The maximum amount that can be contributed to the account. """
        # Subclasses may provide a `when` argument, so provide that here
        # for consistency (even though it's unused):
        # pylint: disable=unused-argument,no-self-use

        # For non-registered accounts, there is no maximum
        return Money('Infinity')

    def min_outflow(self, when='end'):
        """ The minimum amount to be withdrawn from the account. """
        # Subclasses may provide a `when` argument, so provide that here
        # for consistency (even though it's unused):
        # pylint: disable=unused-argument,no-self-use

        # For non-registered accounts, there is no minimum
        return Money('0')

    def min_inflow(self, when='end'):
        """ The minimum amount to be contributed to the account. """
        # Subclasses may provide a `when` argument, so provide that here
        # for consistency (even though it's unused):
        # pylint: disable=unused-argument,no-self-use

        # For non-registered accounts, there is no minimum
        return Money('0')

    @recorded_property
    def taxable_income(self):
        """ Treats all returns as taxable. """
        return max(self.returns, Money(0))

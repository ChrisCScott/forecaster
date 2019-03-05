""" A module providing the base Account class. """

import math
from collections import defaultdict
from decimal import Decimal
from forecaster.person import Person
from forecaster.ledger import (
    Money, TaxSource, recorded_property, recorded_property_cached)
from forecaster.utility import when_conv, frequency_conv

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

    `Account` objects, when treated as iterables, expose the underlying
    `transactions` dict and can be used interchangeably in most cases
    with dicts of `{when: value}` pairs.

    Examples::

        account1 = Account(100, 0.05)
        account2 = account1.next_year()
        account1.balance == 100  # True
        account2.balance == 105  # True

        account = Account(0, 0)
        account.add_transaction(value=1, 'start')
        account[0] == 1  # True

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
            self, owner=None,
            balance=0, rate=0, nper=1, inputs=None, initial_year=None):
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
        self._transactions = defaultdict(lambda: Money(0))
        self._rate_callable = None

        # Set the various property values based on inputs:
        self.owner = owner
        self.balance = Money(balance)
        self.rate_callable = rate
        self.nper = frequency_conv(nper)
        # NOTE: returns is calculated lazily

    @property
    def owner(self):
        """ The account's owner. """
        return self._owner

    @owner.setter
    def owner(self, val):
        """ Sets the account's owner. """
        # Unregister this account from any former owner:
        if self.owner is not None:
            self.owner.accounts.remove(self)

        # For new owners, do basic type-checks and then
        # bind the account to the owner:
        if val is not None:
            if not isinstance(val, Person):
                raise TypeError('Account: owner must be of type Person.')
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

        # Simultaneous transactions are modelled as one sum,
        self.transactions[when] += value

    @recorded_property
    def inflows(self):
        """ The sum of all inflows to the account. """
        return Money(sum(
            val for val in self.transactions.values() if val.amount > 0))

    @recorded_property
    def outflows(self):
        """ The sum of all outflows from the account. """
        return Money(sum(
            val for val in self.transactions.values() if val.amount < 0))

    def next_year(self):
        """ Adds another year to the account.

        This method will call the next_year method for the owner if they
        haven't been advanced to the next year.
        """
        # Ensure that the owner has been brought up to this year
        if self.owner is not None:
            while self.owner.this_year < self.this_year:
                self.owner.next_year()

        # Now increment year via superclass:
        super().next_year()

        # Clear out transactions for the new year:
        # (We assign a new defaultdict because the old dict is
        # stored by the `transactions` recorded_property; invoking
        # `clear` will affect past-year records.)
        self._transactions = defaultdict(lambda: Money(0))

    def max_outflow(self, when='end'):
        """ The maximum amount that can be withdrawn from the account.

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

    def transactions_to_balance(self, timings, balance):
        """ The amounts to add/withdraw at `timings` to get `balance`.

        The return value satisfies two criteria:

        * If each `{when: value}` pair is added as a transaction
        then `self.balance_at_time('end')` will return `balance`,
        subject to precision-based error.
        * Each `value` is proportionate to the corresponding
        input `weight` for the given timing.

        Note that this method does not guarantee that the Account will
        not go into negative balance mid-year if the output is used to
        apply transactions to the Account.

        Arguments:
            timings (dict[float, float]): A mapping of `{when: weight}`
                pairs.
            balance (Money): The balance of the Account would
                have after applying the outflows.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                value indicates the amount that can be withdrawn at that
                time such that, by the end of the year, the Account's
                balance is `balance`.
        """
        # Determine how much the end-of-year balance would change under
        # these transactions:
        ref_balance = self.balance_at_time('end')
        change = balance - ref_balance
        # We'll need to normalize weights later; this will help.
        total_weight = Decimal(sum(timings.values()))

        # It would be easy to generate a dict of {when: value} pairs
        # that achieve this change by assigning `change*w*A(1-t)`
        # for each timing `t` with weight `w`. But then the amounts
        # would be different at different timings even if weights were
        # the same. We want the value at each timing to be proportional
        # to its weight.

        # This calls for math. Consider this derivation, where A is the
        # accumulation function using the current rate/nper and
        # each {timing: value} pair in output is abbreviated t_i: v_i:

        # change = A(1-t_1)*v_1 + A(1-t_2)*v_2 + ... + A(1-t_n)*v_n
        #   (This is just the sum of future values of the transactions)
        # v_j = sum(v_1 ... v_n) * w_j for all j in [1 .. n]
        #   (This is the constraint that each v_j is proportional to its
        #   weight w_j. Note that it assumes w_j is normalized!)
        # Define s = sum(v_1 ... v_n).
        #   (We call s `total` in the code below for style reasons.)
        # change = A(1-t_1)*s*w_1 + ... + A(1-t_n)*s*w_n
        #   (Obtain this simply by substitution)
        # s = change / (A(1-t_1)*w_1 + ... + A(1-t_n)*w_n)
        #   (We've solved for s in terms of t_i and w_i, which are
        #   known. We can use this to determine v_i, the value we want.)
        total = change / sum(
            Decimal(weight / total_weight) * self.accumulation_function(
                t=1-timing,
                rate=self.rate,
                nper=self.nper)
            for timing, weight in timings.items())
        # We've determined `s`, now find `v_j`, i.e. the value of the
        # transaction for a given timing t_j. In essence, we're
        # determining a weighted portion of `total`:
        outflows = {
            timing: total * (weight / total_weight)
            for timing, weight in timings.items()}
        return outflows

    def max_outflows(self, timings):
        """ The maximum amounts that can be withdrawn at `timings`.

        The output transaction values will be proportionate to the
        values of `timings`, which are used as weights.

        Example:
            Consider an account with 100% interest without compounding:
            ``` account = Account(balance=100, rate=1, nper=1)
            account.max_outflows({0: 1, 1: 1})
            # Returns {0: Money(66.66...), 1: Money(66.66...)}
            ```

        Args:
            timings (dict[float, float]): A mapping of `{when: weight}`
                pairs.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                `value` indicates the amount that can be withdrawn at
                that time such that, by the end of the year, the
                Account's balance is $0.
        """
        return self.transactions_to_balance(timings, Money(0))

    def max_inflows(self, timings):
        """ The maximum amounts that can be contributed at `timings`.

        The output transaction values will be proportionate to the
        values of `timings`, which are used as weights.

        For a simple `Account`, this will return `Infinity` for all
        timings. Subclasses can override it as appropriate.

        Args:
            timings (dict[float, float]): A mapping of `{when: weight}`
                pairs.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                `value` indicates the maximum amount that can be
                contributed at that time.
        """
        return self.transactions_to_balance(timings, Money('Infinity'))

    @recorded_property
    def taxable_income(self):
        """ Treats all returns as taxable. """
        return max(self.returns, Money(0))

    # Allow calling code to interact directly with the account as
    # a series of transactions. Implement all `Mapping` methods
    # to redirect to `_transactions`, except for comparison
    # and serialization methods.
    def __len__(self):
        return len(self._transactions)

    def __iter__(self):
        for transaction in sorted(self._transactions.keys()):
            yield transaction

    def __contains__(self, key):
        when = when_conv(key)
        return when in self._transactions

    def __getitem__(self, key):
        return self._transactions[key]

    def __setitem__(self, key, value):
        if key in self._transactions:
            del self._transactions[key]
        self.add_transaction(value=value, when=key)

    def __delitem__(self, key):
        del self._transactions[key]

    def keys(self):
        """ The timings of the account's transactions. """
        return self._transactions.keys()

    def values(self):
        """ The values of the account's transactions. """
        return self._transactions.values()

    def items(self):
        """ The account's transactions, as {when: value} pairs. """
        return self._transactions.items()

    def get(self, key, default=None):
        """ Gets the transaction value at a particular timing. """
        self._transactions.get(key, default=default)

    def clear(self):
        """ Clears all of the account's transactions. """
        self._transactions.clear()

    # Finally, add some methods for calculating growth (i.e. balance
    # at a future time and time to get to a future balance.)

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

    @staticmethod
    def accumulation_function_inverse(accum, rate, nper=1):
        """ The inverse of the accumulation function, A^-1(a).

        A^-1(a) provides the amount of time required to achieve a
        certain growth (or discount) factor. If `accum` is less than
        1, the result is negative. `accum` must be positive.

        Args:
            accum (float, Decimal): The accumulation factor.
            rate (float, Decimal): The rate of return (or interest).
            nper (int): The number of compounding periods per year.

        Returns:
            (float, Decimal): A value `t` defining the period [0,t]
                or [t, 0] (if negative) over which the accumulation
                would be reached.
        """
        # Convert accum and rate to Decimal
        accum = Decimal(accum)
        rate = Decimal(rate)

        if accum < 0:
            raise ValueError('accum must be positive.')

        # The case where rate=0 results in divide-by-zero errors later
        # on, so deal with it specifically here.
        # If the rate is 0%, it will either take an infinite value
        # (positive or negative, depending on the rate)
        # or 0 (in the special case of accum=1)
        if rate == 0:
            if accum == 1:
                return Decimal(0)
            elif accum < 1:
                return -Decimal('Infinity')
            else:
                return Decimal('Infinity')

        # Use the exponential formula for continuous compounding: a=e^rt
        # Derive from this t=ln(a)/r
        if nper is None:
            # math.exp(rate * t) throws a warning, since there's an
            # implicit float-Decimal multiplication.
            timing = math.log(accum, math.e) / rate
        # Otherwise use the discrete formula: a=(1+r/n)^nt
        # Derive from this t=log(a,1+r/n)/n
        else:
            timing = math.log(accum, 1 + rate / nper) / nper

        return timing

    def time_to_value(self, value_now, value_then):
        """ The time required to grow from one value to another.

        Args:
            value_now (Money): The (nominal) value we start with.
            value_then (Money): The (nominal) value we end with.

        Returns:
            A Decimal object representing the time required to
            grow (or shrink) from `value_now` to `value_then`.
        """
        return self.accumulation_function_inverse(
            accum=value_then/value_now, rate=self.rate, nper=self.nper
        )

    def time_to_balance(self, value, when=Decimal(0)):
        """ Returns the time required to grow to a given balance.

        If `when` is provided, this method returns the earliest time
        at or after `when` when the balance has reached `value`. This
        method is transaction-aware; a given balance may be reached
        more than once if there are inflows/outflows.

        Args:
            value (Money): The balance to grow to.
            when (Decimal): Only balances reached on or after `when`
                are considered. Optional.
        """
        # Convert `when` to avoid type errors.
        when = when_conv(when)

        # We'll base all calculations at `when`, including the value
        # of `balance`. Do this even for `when=0`, since there may
        # be a transaction at the start of the year that isn't
        # reflected by `balance` but is incorporated in
        # `balance_at_time`.
        balance = self.balance_at_time(when)

        # Determine when we'll reach the desired amount, assuming
        # no further transactions:
        time = when + self.time_to_value(balance, value)

        # Now look ahead to the next transaction and, if it happens
        # before `time`, recurse onto that transaction's timing:
        next_transaction = min(
            (key for key in self.transactions if key > when),
            default=time)
        if next_transaction < time:
            time = self.time_to_balance(value, next_transaction)

        return time

""" A module providing the base Account class. """

from copy import copy
from collections import defaultdict
from forecaster.person import Person
from forecaster.ledger import (
    TaxSource, recorded_property, recorded_property_cached)
from forecaster.utility import (
    Timing, when_conv, frequency_conv, add_transactions)
from forecaster.accounts.util import (
    accumulation_function, value_at_time, time_to_value)

class Account(TaxSource):
    """ An account storing a balance.

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
        balance (float): The opening account balance for this year.
        balance_history (dict[int, float]): `{year: balance}` pairs
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
        transactions (dict[Decimal, float]): The transactions to/from
            the account for this year. `{when: value}` pairs, where:

            `when` describes the timing of the transaction in the year.
            In the range [0, 1].

            `value` is the sum of inflows and outflows at time `when`.
            Positive for inflows and negative for outflows.
        transactions_history (dict[int, dict[Decimal, float]]):
            `{year: transactions}` pairs covering all years in the range
            `initial_year: this_year`
        returns (float): The returns (losses) of the account for the
            year.
        returns_history (dict[int, float]): `{year: returns}` pairs
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
            balance=0, rate=0, nper=1, default_timing=None,
            inputs=None, initial_year=None, high_precision=None, **kwargs):
        """ Constructor for `Account`.

        This constructor receives only values for the first year.

        Args:
            owner (Person): The owner of the account. Optional.
            balance (float): The balance for the first year
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
            default_timing (Timing): The usual schedule for transactions
                to/from this account, used by various methods when no
                `timing` arg is expressly provided. Optional.
            initial_year (int): The first year (e.g. 2000)
            high_precision (Callable[[float], T]): Takes a single
                `float` argument and converts it to high-precision
                numeric type `T`, such as Decimal.
        """
        # Use the explicitly-provided initial year if available,
        # otherwise default to the owner's initial year:
        if initial_year is None:
            if not hasattr(owner, 'initial_year'):
                raise TypeError(
                    'Account: owner must have initial_year attribute.')
            else:
                initial_year = owner.initial_year
        # Defer Ledger's init until we can pass initial_year:
        super().__init__(
            initial_year=initial_year, inputs=inputs,
            high_precision=high_precision, **kwargs)

        # Set hidden attributes to support properties that need them to
        # be set in advance:
        self._owner = None
        self._transactions = defaultdict(lambda: 0) # Money value
        self._rate_callable = None
        self._default_timing = None
        self._nper = None

        # Set the various property values based on inputs:
        self.owner = owner
        self.balance = balance # Money value
        self.rate_callable = rate
        self.nper = frequency_conv(nper)
        if default_timing is None:
            self.default_timing = Timing(high_precision=high_precision)
        else:
            self.default_timing = default_timing
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

    @property
    def default_timing(self):
        """ The usual timing for transactions to/from this account. """
        return self._default_timing

    @default_timing.setter
    def default_timing(self, val):
        """ Sets default_timing. """
        # Cast to `Timing` type:
        if not isinstance(val, Timing):
            val = Timing(val, high_precision=self.high_precision)
        self._default_timing = val

    @default_timing.deleter
    def default_timing(self):
        """ Deletes default_timing. """
        # Return default_timing to its default value:
        self._default_timing = Timing(high_precision=self.high_precision)

    @recorded_property_cached
    def balance(self):
        """ The balance of the account for the current year (float).

        This is the balance after applying all transactions and any
        growth/losses from the rate.
        """
        # pylint: disable=method-hidden
        # Pylint gets confused by attributes added by metaclass.
        # This method isn't hidden in __init__; it's assigned to (by a
        # setter defined via metaclass)

        # First, grow last year's initial balance based on the rate:
        balance = value_at_time(
            # pylint: disable=no-member
            # Pylint gets confused by attributes added by metaclass.
            self._balance_history[self.this_year - 1],
            self.rate, 'start', 'end', nper=self.nper,
            high_precision=self.high_precision)

        # Then, grow each transactions and add it to the year-end total.
        # NOTE: This accounts for both inflows and outflows; outflows
        # and their growth are negative and will reduce the balance.
        # pylint: disable=no-member
        # Pylint gets confused by attributes added by metaclass.
        transactions_history = self._transactions_history
        for when, value in transactions_history[self.this_year - 1].items():
            balance += value_at_time(
                value, self.rate, when, 'end', nper=self.nper,
                high_precision=self.high_precision)

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
                # If this is scalar, return a constant rate
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
        one = self.precision_convert(1)
        returns = (
            self.balance * (
                accumulation_function(
                    one, self.rate, self.nper,
                    # This member exists, though Pylint can't tell.
                    # pylint: disable=no-member
                    high_precision=self.high_precision)
                    # pylint: enable=no-member
                - one))

        # Add in the returns on each transaction.
        # (Withdrawals will generate returns with the opposite sign of
        # the returns on the initial balance and prior inflows, thereby
        # cancelling out a portion of those returns.)
        for when in self.transactions:
            returns += (
                self.transactions[when] * (
                    accumulation_function(
                        one - when, self.rate, self.nper,
                        high_precision=self.high_precision) - 
                    one))

        return self.precision_convert(returns)

    @property
    def nper(self):
        """ The number of compounding periods per year. """
        return self._nper

    @nper.setter
    def nper(self, value):
        # Convert strings to either a number or float
        value = frequency_conv(value)
        # Convert non-None values to high-precision, if enabled:
        if value is not None:
            value = self.precision_convert(value)
        self._nper = value

    def add_transaction(self, value, when='end'):
        """ Adds a transaction to the account.

        Args:
            value (float): The value of the transaction. Positive values
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
        when = when_conv(when, self.high_precision)

        # NOTE: If `value` is intended to be a special Money type
        # (like PyMoney), attempt conversion here

        # Simultaneous transactions are modelled as one sum,
        self.transactions[when] += value

    def inflows(self, transactions=None):
        """ The sum of all inflows to the account. """
        if transactions is not None:
            result = sum(val for val in transactions.values() if val > 0)
        else:
            result = 0 # Money value
        result += sum(val for val in self.transactions.values() if val > 0)
        return result

    def outflows(self, transactions=None):
        """ The sum of all outflows from the account. """
        if transactions is not None:
            result = sum(val for val in transactions.values() if val < 0)
        else:
            result = 0 # Money value
        result += sum(val for val in self.transactions.values() if val < 0)
        return result

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
        self._transactions = defaultdict(lambda: 0) # Money value

    @property
    def max_outflow_limit(self):
        """ The maximum amount that can be withdrawn from the account.

        This property provides a scalar value representing the largest
        possible outflow for this account, ignoring timing or the
        current balance. For example, if there is no limit on outflows,
        this returns Money('Infinity'), regardless of the balance.

        In most cases you probably want to determine the maximum
        amount that can actually be withdrawn at the current balance.
        For that, use `max_outflows`.

        Returns:
            The maximum value that can be withdrawn from the account.
        """
        # For an ordinary Account, there is no limit on withdrawals.
        return self.precision_convert(float('-inf'))

    @property
    def max_inflow_limit(self):
        """ The maximum amount that can be contributed to the account.

        This method uses the same semantics as `max_outflow`, except
        for inflows.
        """
        # For an ordinary Account, there is no limit on contributions.
        return self.precision_convert(float('inf'))

    @property
    def min_outflow_limit(self):
        """ The minimum amount to be withdrawn from the account.

        This method uses the same semantics as `max_outflow`, except
        it provides the minimum.
        """
        # For an ordinary Account, there is no minimum withdrawal
        return self.precision_convert(0)

    @property
    def min_inflow_limit(self):
        """ The minimum amount to be contributed to the account.

        This method uses the same semantics as `max_outflow`, except
        it provides the minimum for inflows.
        """
        # For an ordinary Account, there is no minimum contribution.
        return self.precision_convert(0)

    def max_inflow(self, when="end"):
        """ The maximum amount that can be contributed at `when`. """
        # The `when` arg is provided for subclasses to use.
        # pylint: disable=unused-argument
        return self.max_inflow_limit

    def min_inflow(self, when="end"):
        """ The minimum amount that can be contributed at `when`. """
        # The `when` arg is provided for subclasses to use.
        # pylint: disable=unused-argument
        return self.min_inflow_limit

    def max_outflow(self, when="end"):
        """ The maximum amount that can be withdrawn at `when`. """
        return max(
            # Withdraw everything (or none if the balance is negative)
            min(
                -self.balance_at_time(when),
                self.precision_convert(0)), # Money value
            # But no more than the maximum outflow:
            self.max_outflow_limit)

    def min_outflow(self, when="end"):
        """ The minimum amount that can be withdrawn at `when`. """
        # The `when` arg is provided for subclasses to use.
        # pylint: disable=unused-argument
        return self.min_outflow_limit

    def transactions_to_balance(
            self, balance, timing=None,
            max_total=None, min_total=None,
            transactions=None):
        """ The amounts to add/withdraw at `timing` to get `balance`.

        The return value satisfies two criteria:

        * If each `{when: value}` pair is added as a transaction
          then `self.balance_at_time('end')` will return `balance`,
          subject to precision-based error.
        * Each `value` is proportionate to the corresponding
          input `weight` for the given timing.

        Note that this method does not guarantee that the Account will
        not go into negative balance mid-year if the output is used to
        apply transactions to the Account.

        This method is transaction-aware in the sense that the resulting
        transactions are additional to any transactions already added to
        the account.

        Arguments:
            timing (Timing): A mapping of `{when: weight}` pairs.
            balance (float): The balance of the Account would
                have after applying the outflows.
            max_total (float): If provided, the resulting transactions
                will not exceed this total value (even if this value is
                not sufficient to achieve `balance`)
            min_total (float): If provided, the resulting transactions
                will be at least this total value (even if this value is
                larger than necessary to achieve `balance`)
            transactions (dict[Decimal, float]): If provided, the result
                of this method will be determined as if the account
                also had these transactions recorded against it.

        Returns:
            dict[float, float]: A mapping of `{when: value}` pairs where
                value indicates the amount that can be withdrawn at that
                time such that, by the end of the year, the Account's
                balance is `balance`.
        """
        # Determine how much the end-of-year balance would change under
        # these transactions. This accounts for any transactions already
        # applied to the account (via balance_at_time):
        ref_balance = self.balance_at_time('end', transactions=transactions)
        change = balance - ref_balance

        # Clean inputs:
        if timing is None or not timing:
            # Use default timing if none was explicitly provided.
            # NOTE: Consider whether we should instead use whatever
            # timing is naturally suggested by the timings of the
            # current account transactions.
            # For example, if an account receives $50 at when=0.5 and a
            # $25 withdrawal at when=1, then the maximum outflow would
            # occur at when=0.5 (and would have a value of $25, assuming
            # no growth).
            # The benefit here is that we could provide a schedule of
            # transactions which *does* guarantee that the account will
            # not go into negative balance at any time!
            # A side-effect is that we might move `default_timing` logic
            # back to the classes that need it (i.e. Debt, Person).
            timing = self.default_timing
        elif not isinstance(timing, Timing):
            # Convert timing from str or dict if appropriate:
            timing = Timing(timing, high_precision=self.high_precision)
        # Weights aren't guaranteed to sum to 1, so normalize them so
        # they do. This will help later.
        # (Also convert to Decimal to avoid Decimal/float mismatch.)
        total_weight = sum(timing.values())
        # If calling code has passed in a timing object with 0 net
        # weights (i.e. values) but non-empty timings (i.e. keys),
        # assume uniform weights at those timings:
        if total_weight == 0:
            timing = Timing({
                when: self.precision_convert(1) for when in timing.keys()},
                high_precision=self.high_precision)
            total_weight = len(timing)
        # Normalize so that we can conveniently multiply weights by
        # `total` to get that amount spread across all timings:
        # (Exclude zero-valued weights for two reasons: we don't need
        # them and they lead to errors when multipling by infinity)
        normalized_timing = {
            when: weight / total_weight
            for when, weight in timing.items() if weight != 0}

        # We want the value at each timing to be proportional to its
        # weight. This calls for math.
        # Consider this derivation, where:
        # * A is the accumulation function using the current rate/nper
        # * Each {timing: value} pair in output is abbreviated t_i: v_i
        # * The sum total of all transaction values is denoted s

        # change = A(1-t_1)*v_1 + A(1-t_2)*v_2 + ... + A(1-t_n)*v_n
        #   (This is just the sum of future values of the transactions)
        # v_j = sum(v_1 ... v_n) * w_j = s * w_j for all j in [1 .. n]
        #   (This is the constraint that each v_j is proportional to its
        #   weight w_j. Note that it assumes w_j is normalized!)
        # change = A(1-t_1)*s*w_1 + ... + A(1-t_n)*s*w_n
        #   (Obtain this by simple substitution of v_j = s * w_j)
        # s = change / (A(1-t_1)*w_1 + ... + A(1-t_n)*w_n)
        #   (We can use this to determine v_j)

        # Since s (the total) is the same for all values, find it first:
        weighted_accum = self.precision_convert(0)
        for timing, weight in normalized_timing.items():
            weighted_accum += weight * accumulation_function(
                t=1-timing,
                rate=self.rate,
                nper=self.nper)
        total = change / weighted_accum

        # Limit total transaction value based on args:
        if max_total is not None:
            total = min(total, max_total)
        if min_total is not None:
            total = max(total, min_total)

        # Now find value (v_j) for each timing (t_j) by applying
        # normalized weights to the total:
        result_transactions = {
            timing: total * weight
            for timing, weight in normalized_timing.items()}
        return result_transactions

    def max_outflows(
            self, timing=None, transaction_limit=None, balance_limit=None,
            transactions=None, **kwargs):
        """ The maximum amounts that can be withdrawn at `timings`.

        The output transaction values will be proportionate to the
        values of `timings`, which are used as weights.

        Example:
            Consider an account with 100% interest without compounding:
            ``` account = Account(balance=100, rate=1, nper=1)
            account.max_outflows({0: 1, 1: 1})
            # Returns {0: 66.66..., 1: 66.66...}
            ```

        Args:
            timing (Timing): A mapping of `{when: weight}` pairs.
                Optional. Uses default_timing if not provided.
            transaction_limit (float): Total outflows will not exceed
                this amount (not including any outflows already recorded
                against this `Account`). Optional.
            balance_limit (float): At least this balance, if provided,
                will remain in the account at year-end. Optional.
            transactions (dict[Decimal, float]): If provided, the result
                of this method will be determined as if the account
                also had these transactions recorded against it.

        Returns:
            dict[float, float]: A mapping of `{when: value}` pairs where
                `value` indicates the amount that can be withdrawn at
                that time such that, by the end of the year, the
                Account's balance is $0.
        """
        # pylint: disable=unused-argument
        # `kwargs` is provided so that subclasses can expand the
        # argument list without requiring client code to type-check.

        if balance_limit is None:
            # Outflows are limited by the account balance:
            balance_limit = self.precision_convert(0) # Money value

        # Limit transactions to max total outflows, accounting for any
        # existing outflows already recorded as transactions:
        min_total = self.max_outflow_limit - self.outflows(transactions)
        # If a smaller limit is passed in, use that.
        # (Recall that outflows are negative, so we use max, not min)
        if transaction_limit is not None:
            min_total = max(min_total, transaction_limit)
        # Don't allow positive lower bounds:
        min_total = min(min_total, self.precision_convert(0)) # Money value

        # Ensure that only negative amounts are returned:
        max_total = self.precision_convert(0) # Money value
        return self.transactions_to_balance(
            balance_limit,
            timing=timing,
            max_total=max_total,
            min_total=min_total,
            transactions=transactions)

    def max_inflows(
            self, timing=None, transaction_limit=None, balance_limit=None,
            transactions=None, **kwargs):
        """ The maximum amounts that can be contributed at `timing`.

        The output transaction values will be proportionate to the
        values of `timing`, which are used as weights.

        For a simple `Account`, this will return `Infinity` for all
        timings. Subclasses can override it as appropriate.

        Args:
            timing (Timing): A mapping of `{when: weight}` pairs.
                Optional. Uses default_timing if not provided.
            transaction_limit (float): Total inflows will not exceed
                this amount (not including any inflows already recorded
                against this `Account`). Optional.
            balance_limit (float): This balance, if provided, will not
                be exceeded at year-end. Optional.
            transactions (dict[Decimal, float]): If provided, the result
                of this method will be determined as if the account
                also had these transactions recorded against it.

        Returns:
            dict[float, float]: A mapping of `{when: value}` pairs where
                `value` indicates the maximum amount that can be
                contributed at that time.
        """
        # pylint: disable=unused-argument
        # `kwargs` is provided so that subclasses can expand the
        # argument list without requiring client code to type-check.

        if balance_limit is None:
            # Inflows have no upper cap:
            balance_limit = self.precision_convert(float('inf'))

        # Limit transactions to max total inflows, accounting for any
        # existing inflows already recorded as transactions:
        max_total = self.max_inflow_limit - self.inflows(transactions)
        # If a smaller limit is passed in, use that.
        if transaction_limit is not None:
            max_total = min(max_total, transaction_limit)
        # Don't allow negative lower bounds:
        max_total = max(max_total, self.precision_convert(0)) # Money value

        # Ensure that only non-negative amounts are returned:
        min_total = self.precision_convert(0) # Money value
        return self.transactions_to_balance(
            balance_limit,
            timing=timing,
            max_total=max_total,
            min_total=min_total,
            transactions=transactions)

    def min_outflows(
            self, timing=None, transaction_limit=None, balance_limit=None,
            transactions=None, **kwargs):
        """ The minimum outflows that should be withdrawn at `timings`.

        The output transaction values will be proportionate to the
        values of `timings`, which are used as weights.

        For a simple `Account`, this will return `0` for all
        timings. Subclasses can override it as appropriate.

        Args:
            timing (Timing): A mapping of `{when: weight}` pairs.
                Optional. Uses default_timing if not provided.
            transaction_limit (float): Total outflows will not exceed
                this amount (not including any outflows already recorded
                against this `Account`). Optional.
            balance_limit (float): At least this balance, if provided,
                will remain in the account at year-end. Optional.
            transactions (dict[Decimal, float]): If provided, the result
                of this method will be determined as if the account
                also had these transactions recorded against it.

        Returns:
            dict[float, float]: A mapping of `{when: value}` pairs where
                `value` indicates the amount that should be withdrawn at
                that time.
        """
        # pylint: disable=unused-argument
        # `kwargs` is provided so that subclasses can expand the
        # argument list without requiring client code to type-check.

        if balance_limit is None:
            # Outflows are limited by the account balance:
            balance_limit = self.precision_convert(0) # Money value

        # Limit transactions to min total outflows, accounting for any
        # existing outflows already recorded as transactions:
        min_total = self.min_outflow_limit - self.outflows(transactions)
        # If a smaller limit is passed in, use that.
        # (Recall that outflows are negative, so we use max, not min)
        if transaction_limit is not None:
            min_total = max(min_total, transaction_limit)
        # Don't allow positive lower bounds:
        min_total = min(min_total, self.precision_convert(0)) # Money value

        # Ensure that only negative amounts are returned:
        max_total = self.precision_convert(0) # Money value
        return self.transactions_to_balance(
            balance_limit,
            timing=timing,
            max_total=max_total,
            min_total=min_total,
            transactions=transactions)

    def min_inflows(
            self, timing=None, transaction_limit=None, balance_limit=None,
            transactions=None, **kwargs):
        """ The minimum amounts that should be contributed at `timing`.

        The output transaction values will be proportionate to the
        values of `timing`, which are used as weights.

        For a simple `Account`, this will return `0` for all
        timings. Subclasses can override it as appropriate.

        Args:
            timing (Timing): A mapping of `{when: weight}` pairs.
                Optional. Uses default_timing if not provided.
            transaction_limit (float): Total inflows will not exceed
                this amount (not including any inflows already recorded
                against this `Account`). Optional.
            balance_limit (float): This balance, if provided, will not
                be exceeded at year-end. Optional.
            transactions (dict[Decimal, float]): If provided, the result
                of this method will be determined as if the account
                also had these transactions recorded against it.

        Returns:
            dict[float, float]: A mapping of `{when: value}` pairs where
                `value` indicates the maximum amount that can be
                contributed at that time.
        """
        # pylint: disable=unused-argument
        # `kwargs` is provided so that subclasses can expand the
        # argument list without requiring client code to type-check.

        if balance_limit is None:
            # Inflows have no upper cap:
            balance_limit = self.precision_convert(float('inf'))

        # Limit transactions to min total inflows, accounting for any
        # existing inflows already recorded as transactions:
        max_total = self.min_inflow_limit - self.inflows(transactions)
        # If a smaller limit is passed in, use that.
        if transaction_limit is not None:
            max_total = min(max_total, transaction_limit)
        # Don't allow negative lower bounds:
        max_total = max(max_total, self.precision_convert(0)) # Money value

        # Ensure that only non-negative amounts are returned:
        min_total = self.precision_convert(0) # Money value
        return self.transactions_to_balance(
            balance_limit,
            timing=timing,
            max_total=max_total,
            min_total=min_total,
            transactions=transactions)

    @recorded_property
    def taxable_income(self):
        """ Treats all returns as taxable. """
        return max(self.returns, self.precision_convert(0)) # Money value

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
        when = when_conv(key, self.high_precision)
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

    def balance_at_time(self, time, transactions=None):
        """ Returns the balance at a point in time.

        Args:
            when (Decimal, str): The time at which the account's balance
                is to be determined.
            transactions (dict[Decimal, float]): If provided, the result
                of this method will be determined as if the account
                also had these transactions recorded against it.
        """
        # We need to convert `time` to enable the comparison in the dict
        # comprehension in the for loop below.
        time = when_conv(time, self.high_precision)

        # Find the future value (at t=time) of the initial balance.
        # This doesn't include any transactions of their growth.
        balance = value_at_time(
            self.balance, self.rate, 'start', time, nper=self.nper,
            high_precision=self.high_precision)

        # Combine the recorded and input transactions, if provided:
        if transactions is not None:
            transactions = copy(transactions)
            add_transactions(transactions, self.transactions)
        # Otherwise simply use the account's recorded transactions:
        else:
            transactions = self.transactions
        # Add in the future value of each transaction (except that that
        # happen after `time`).
        for when in [w for w in transactions if w <= time]:
            balance += value_at_time(
                transactions[when], self.rate, when, time, nper=self.nper,
                high_precision=self.high_precision)

        return balance

    def time_to_balance(self, value, when=0):
        """ Returns the time required to grow to a given balance.

        If `when` is provided, this method returns the earliest time
        at or after `when` when the balance has reached `value`. This
        method is transaction-aware; a given balance may be reached
        more than once if there are inflows/outflows.

        Args:
            value (float): The balance to grow to.
            when (Decimal): Only balances reached on or after `when`
                are considered. Optional.
        """
        # Convert `when` to avoid type errors.
        when = when_conv(when, self.high_precision)

        # We'll base all calculations at `when`, including the value
        # of `balance`. Do this even for `when=0`, since there may
        # be a transaction at the start of the year that isn't
        # reflected by `balance` but is incorporated in
        # `balance_at_time`.
        balance = self.balance_at_time(when)

        # Determine when we'll reach the desired amount, assuming
        # no further transactions:
        time = when + time_to_value(
            self.rate, balance, value, nper=self.nper,
            high_precision=self.high_precision)

        # Now look ahead to the next transaction and, if it happens
        # before `time`, recurse onto that transaction's timing:
        next_transaction = min(
            (key for key in self.transactions if key > when),
            default=time)
        if next_transaction < time:
            time = self.time_to_balance(value, next_transaction)

        return time

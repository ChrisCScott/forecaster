""" A module providing a base class for SubForecast objects. """

from collections import defaultdict
from collections.abc import Hashable
from decimal import Decimal
from forecaster.ledger import Ledger, recorded_property
from forecaster.money import Money
from forecaster.accounts import Account
from forecaster.utility import Timing

class TransactionDict(defaultdict):
    """ A defaultdict that accepts unhashable keys.

    The purpose of this dictionary is to allow `SubForecast` to have
    a `dict[dict[*], dict[Decimal, Money]]` data structure to map
    accounts (or account-like dicts) to {when: value} transaction
    mappings.

    When this dict encounters an unhashable object being used as a
    key, it uses the *id* of that object as a key instead. Calling
    code does not need to use the id; it can index this dict with
    the unhashable object and will receive the unhashable object
    as a key when iterating over the dict.

    This class implicitly treats identity as equality for non-hashable
    keys. This avoids hashing collisions between unhashable keys
    (since different keys have different identities) and between
    unhashable and hashable keys, so long as no hashable key is equal
    to an unhashable key's id. This is guaranteed if the hashable keys
    aren't equal to any integers (and, if they are `Account` objects,
    they won't be, so you should be fine!). Using integer (or integer-
    convertible) objects as keys may lead to unexpected behaviour due
    to hashing collisions (but even these are very unlikely!)

    NOTE: The behaviour of `keys()` is overridden for this class to
    return a list instead of a keyview. This mimics Python 2.x
    behaviour but is non-standard for Python 3.x.
    """
    def __init__(self, *args, **kwargs):
        """ Initializes the dict. """
        super().__init__(*args, **kwargs)
        self._unhashablekeys = {}

    def __getitem__(self, key):
        """ Gets an item for a key, even if key is unhashable. """
        if not isinstance(key, Hashable):
            # This is a defaultdict, so add new keys on get:
            if id(key) not in self._unhashablekeys:
                self._unhashablekeys[id(key)] = key
            return super().__getitem__(id(key))
        else:
            return super().__getitem__(key)

    def __setitem__(self, key, value):
        """ Sets a value for key, even if key is unhashable. """
        if not isinstance(key, Hashable):
            if id(key) not in self._unhashablekeys:
                self._unhashablekeys[id(key)] = key
            super().__setitem__(id(key), value)
        else:
            super().__setitem__(key, value)

    def __iter__(self):
        """ Generates iterator over keys, including unhashable keys. """
        for key in super().__iter__():
            if key in self._unhashablekeys:
                yield self._unhashablekeys[key]
            else:
                yield key

    def keys(self):
        """ Returns a list of keys, including unhashable keys. """
        # We return a list because a keyview (the usual return type in
        # Python 3.x) exposes the underlying id-based implementation.
        # NOTE: We can't use a frozenset; it requires hashable values.

        # Translation between key and id(key) is handled by __iter__
        return sorted(self.__iter__())  # Returns a list

class SubForecast(Ledger):
    """ Generic class for implementing part of a financial forecast.

    `SubForecast` instances are managed by a `Forecast` object. Each
    `SubForecast` instance receives a dict of cashflows when called
    and mutates it by adding or substracting from the cashflows.
    The mutated dict can then be passed to another `SubForecast` for
    further processing. The dict is called `available` and represents
    the amount of money available for use by subsequent `SubForecast`
    instances.

    In general, positive values indicate additions/deposits to the
    pool of money available for use, and negative values are
    substractions/withdrawals. E.g. when income is received, an
    `IncomeForecast` subclass instance might add positive values
    to `available`. A `LivingExpensesForecast` subclass instance
    might add negative values.

    In addition to mutating `available`, each `SubForecast` instance
    can manage accounts that money moves to/from. Much of the logic
    of this class deals with adding transactions to such accounts.
    Money can be moved from `available` to an account (or vice-versa),
    and those movements can be undone as well (via
    `undo_transactions`).

    This is a `Ledger` subclass, meaning that it provides
    `recorded_property` attributes with corresponding `*_history`
    dicts storing values of the properties over time. See the
    documentation of `Ledger` (or concrete subclasses like `Account`)
    for more information.

    Args:
        initial_year (int): The first year of the forecast.
            NOTE: Issue #53 removes the requirement for initial_year.
        default_timing (Timing): The timing of transactions to use if
            none is explicitly given to `add_transactions`.

    Attributes:
        transactions (TransactionDict[
            Union[Account, dict]: defaultdict[Decimal: Money]):
            A record of transactions to/from various accounts.
            An account does not have to be a formal `Account`
            object; it can be any `Mapping`, like a `dict`.

            Each account is mapped to time-series data (in the
            {when: value} format used throughout this package) where
            positive values correspond to inflows to inflows to the
            account and negative values are outflows.

            This dict includes transactions made to/from `available`.
    """

    def __init__(self, initial_year, default_timing=None):
        """ Initializes an instance of SubForecast. """
        # Invoke Ledger's __init__ or pay the price!
        # NOTE Issue #53 removes this requirement
        super().__init__(initial_year)
        # Use default Timing (i.e. lump sum contributions at the
        # midpoint of the year) if none is explicitly provided:
        if default_timing is None:
            self.default_timing = Timing()
        else:
            self.default_timing = default_timing
        # We store transactions to/from each account so that we can
        # unwind or inspect transactions caused by this subforecast
        # later. So we store it as `{account: {when: value}}`.
        # Since `account` can be a dict (which is non-hashable),
        # we use a custom subclass of defaultdict that allows
        # non-hashable keys.
        self._transactions = TransactionDict(
            lambda: defaultdict(lambda: Money(0)))
        # If the subforecast is called more than once, we
        # may want to do some unwinding. Use this to track
        # whether this subforecast has been called before:
        self._call_invoked = False
        self.total_available = Money(0)

    @recorded_property
    def transactions(self):
        """ `TransactionDict` tracking transactions to/from accounts. """
        return self._transactions

    def next_year(self):
        """ Adds a year to the forecast.

        Note that SubForecast does not advance the years of its
        `Ledger`-type attributes. This is done by `Forecast` to avoid
        one SubForecast advancing a Ledger object that is used by
        another SubForecast.
        """
        # Call `next_year` first so that recorded_property values
        # are recorded with their current state:
        super().next_year()
        # There are no existing transactions at the start of the year:
        self.transactions.clear()
        self._call_invoked = False

    def __call__(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # If this isn't the first time calling this method this year,
        # under whatever was done previously:
        if self._call_invoked:
            self.undo_transactions()
        # Keep track of the fact that this method has been called again:
        self._call_invoked = True

        # It's often useful to know (in scalar terms) how much money
        # is available for use by the Forecast in the year. Track
        # that here.
        if isinstance(available, Account):
            # For accounts, use the amount available at the _end_ of the
            # year - after all transactions.
            # NOTE: This will give a figure that includes interest,
            # meaning that if you withdrawl amounts from `available` at
            # an earlier time it's possible that a lesser amount will be
            # available for withdrawal in total.
            # TODO: Harmonize dict- and Account-based transaction logic.
            # Consider whether we should instead sum over transactions
            # (for dicts and Accounts) and then add the account opening
            # balance (only for Accounts).
            self.total_available = available.max_outflow(1)
        else:
            self.total_available = sum(available.values())

    def undo_transactions(self):
        """ Reverses all transactions cause by this subforecast. """
        # Reverse transactions:
        for account in self.transactions:
            if account is not None:
                for when, value in self.transactions[account].items():
                    account[when] -= value
        # This undoes the effect of __call__, so treat that
        # method as if it was never called:
        self._call_invoked = False

        # If we've cached any recorded_property_cached values, invalidate
        # the cache so they can be re-calculated based on the new input:
        self.clear_cache()

    def add_transactions(
            self, transactions,
            from_account=None, to_account=None,
            strict_timing=False):
        """ Records a group of transactions between accounts.

        This is a convenience method that takes in some transactions
        (as `when: value` pairs) and adds each one as a transaction from
        `from_account` to `to_account` using the same semantics as
        `add_transaction`.

        Args:
            transactions (dict[Decimal, Money]): The timings and values
                of the transactions. Positive for inflows, negative for
                outflows.
            from_account (Account, dict[Decimal, Money]): An account
                (or dict of transactions) from which the transaction
                originates. Optional.
            from_account (Account, dict[Decimal, Money]): An account
                (or dict of transactions) to which the transaction
                is being sent. Optional.
            strict_timing (bool): If False, transactions may be added
                later than `when` if this avoids putting accounts in
                a negative balance. If True, `when` is always used.
        """
        for when, value in transactions.items():
            self.add_transaction(
                value=value, timing=when,
                from_account=from_account, to_account=to_account,
                strict_timing=strict_timing)

    def add_transaction(
            self, value, timing=None,
            from_account=None, to_account=None,
            strict_timing=False):
        """ Records a transaction at a time that balances the books.

        This method will always add the transaction at or after `when`
        (or at or after the implied timing provided by `frequency`).
        It tries to find a time where adding the transaction would
        avoid putting `from_account` into a negative balance (not
        only at the time of the transaction but at any subsequent
        time).

        In particular, it tries to find the _earliest_ workable
        time at or after `when`. Thus, `when` is used if it meets
        these constraints. `when` is also used if no such
        time can be found.

        The transaction is actually two transactions: an outflow
        from `from_account` and an inflow to `to_account`. (This is
        reversed if `value` is negative.) If an account are omitted,
        the method treats the money as coming from (and/or going to)
        an infinite pool of money outside of the model.

        The `*_account` parameters are not necessarily `Account`
        objects. `dict[Decimal, Money]` (a dict of timings mapped to
        transaction values) or anything with similar semantics will
        also work.

        Args:
            value (Money): The value of the transaction.
                Positive for inflows, negative for outflows.
            timing (Timing, dict[float, float], float, str):
                This is either a Timing object or a value that can be
                converted to a Timing object (e.g. a dict of
                {timing: weight} pairs, a `when` value as a float or
                string, etc.). Optional; defaults to `default_timing`.
            from_account (Account, dict[Decimal, Money]): An account
                (or dict of transactions) from which the transaction
                originates. Optional.
            from_account (Account, dict[Decimal, Money]): An account
                (or dict of transactions) to which the transaction
                is being sent. Optional.
            strict_timing (bool): If False, transactions may be added
                later than `when` if this avoids putting accounts in
                a negative balance. If True, `when` is always used.
        """
        # Sanitize input:
        if not isinstance(value, Money):
            value = Money(value)
        if timing is None:
            # Rather than build a new Timing object here, we'll use
            # the default timing for this SubForecast.
            timing = self.default_timing
        elif not isinstance(timing, Timing):
            # This allows users to pass `when` inputs and have them
            # parse correctly, since `Timing(when)` converts to
            # {when: 1}, i.e. a lump-sum occuring at `when`.
            timing = Timing(timing)

        # For convenience, ensure that we're withdrawing from
        # from_account and depositing to to_account:
        if value < 0:
            from_account, to_account = to_account, from_account
            value = -value

        # (Normalize weights just in case client code was naughty and
        # didn't do that for us...)
        total_weight = sum(timing.values())
        # Add a transaction at each timing, with a transaction value
        # proportionate to the (normalized) weight for its timing:
        for when, weight in timing.items():
            weighted_value = value * Decimal(weight / total_weight)
            self._add_transaction(
                value=weighted_value, when=when,
                from_account=from_account, to_account=to_account,
                strict_timing=strict_timing)

    def _add_transaction(
            self, value, when, from_account, to_account, strict_timing):
        """ Helper for `add_transaction`.

        This method provides the high-level logical flow for
        adding a single transaction. Calling code is responsible
        for sanitizing inputs, dealing with multiple transactions,
        and providing sensible default values where appropriate.
        """
        # Shift when, if appropriate, based on from_account:
        if from_account is not None and not strict_timing:
            when = self._shift_when(
                value=value, when=when, account=from_account)

        '''
        # Keep track of any tax withholdings already assigned to the
        # account:
        if hasattr(from_account, 'tax_withheld'):
            tax_withheld_before = from_account.tax_withheld
        '''

        # Record transaction to from_account:
        if from_account is not None:
            # Don't assume all objects provide defaultdict-like interface:
            if when in from_account:
                from_account[when] += -value
            else:
                from_account[when] = -value
        self.transactions[from_account][when] += -value

        '''
        # If tax withholdings have increased as a result of this
        # transaction, reduce the amount that goes to `from_account`
        # accordingly:
        if hasattr(from_account, 'tax_withheld'):
            value -= from_account.tax_withheld - tax_withheld_before
        '''

        # Record transaction to to_account:
        if to_account is not None:
            if when in to_account:
                to_account[when] += value
            else:
                to_account[when] = value
        self.transactions[to_account][when] += value

    def _shift_when(self, value, when, account):
        """ Shifts `when` to a time that avoids negative balances. """
        # First, figure out how much is available for withdrawal at
        # all material times:
        if isinstance(account, Account):
            # For accounts, we can use special features to (e.g.)
            # interpolate balances between transactions based on
            # growth rates.
            accum = self._accum_account(
                account=account, when=when, target_value=value)
        else:
            # For non-Accounts, use generic dict interface to add up
            # transactions, assuming no growth rate or other
            # Account-specific features.
            keys = account.keys() | {when}  # Always include `when`
            accum = {
                t: sum(
                    # For each point in time `t`, find the sum of all
                    # transactions up to this point:
                    account[r] for r in account if r <= t)
                   # Exclude times before `when`:
                for t in keys if t >= when}

        # Find the points in time where subtracting `value`
        # would not put any future point in time into negative
        # balance.
        eligible_times = (
            t for t in accum if all(
                accum[r] >= value for r in accum if r >= t))

        # Find the earliest valid time (or, if none exists,
        # use `when`)
        min_time = min(eligible_times, default=when)
        return min_time

    @staticmethod
    def _accum_account(account, when, target_value=None):
        """ Accumulates transaction histories to provide cash available.

        This method takes an `Account` and determines how much money is
        available to be withdrawn from the account at the time of each
        existing transaction and also at `when`.

        The method also attempts to interpolate additional times between
        the existing transactions where the amount available to be
        withdrawn is equal to `target_value`. Due to implementation
        limitations, the exact timing is not guaranteed to be found
        (but for most Account types it will be found exactly.)

        Returns:
            A dict of `{Decimal: Money}` pairs. The keys include
            all times in `transactions` at or after `when`, plus
            `when` itself (if not already included). If `target_value`
            is provided, the keys may include additional times.
        """
        keys = account.keys() | {when}  # Always include `when`
        # Use Account logic to determine how much is available at the
        # time of each existing transaction and also at `when`:
        accum = {
            t: -account.max_outflow(t)
               # Exclude times before `when`:
            for t in keys if t >= when
        }
        # Try to interpolate times where we achieve the desired
        # value, if that value is known:
        if target_value is not None:
            # We want to look at each time (except the first) and
            # the time immediately prior to it.
            times = sorted(accum.keys())  # NOTE: ascending order
            for i in range(1, len(times)):
                earlier = times[i-1]
                later = times[i]
                # We only care about pairs where the desired value
                # falls between the times in question:
                if (
                        (
                            accum[later] > target_value
                            and accum[earlier] < target_value)
                        or (
                            accum[later] < target_value
                            and accum[earlier] > target_value)
                ):
                    # HACK: The account _balance_ is used here as a
                    # proxy for money available for withdrawal.
                    # This can be inaccurate; e.g. for `Debt` accounts.
                    # `max_outflow` is the correct way to check this
                    # for a known point in time, but there's no method
                    # for finding the point in time when `max_outflow`
                    # will be a certain value.
                    # This hack is only used to identify candidate
                    # timings to shift `when` to; those candidates
                    # don't have to be correct, so this is OK.

                    # Ask the account to find an in-between time
                    # where we hit the desired value exactly.
                    time = account.time_to_balance(
                        value=target_value, when=earlier)
                    # If that time falls within the period
                    # (earlier, later), then add it!
                    if time > earlier and time < later:
                        accum[time] = -sum(account.max_outflows(time).values())
        return accum

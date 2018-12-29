""" TODO """

from collections import defaultdict
from decimal import Decimal
from forecaster.ledger import (
    Ledger, Money,
    recorded_property, recorded_property_cached
)
from forecaster.accounts import Account
from forecaster.utility import when_conv

class SubForecast(Ledger):
    """ TODO """

    def __init__(self):
        """ TODO """
        # Init members:
        self.transactions = defaultdict(lambda: Money(0))
        self.available = defaultdict(lambda: Money(0))

    def next_year(self, available=None):
        """ TODO """
        # Call `next_year` first so that recorded_property values
        # are recorded with their current state:
        super().next_year()
        # There are no existing transactions at the start of the year:
        self.transactions.clear()
        # Update available, if it's provided:
        if available is not None:
            self.available = available
        # Otherwise, advance it to the next year:
        if isinstance(self.available, Account):
            while self.available.this_year < self.this_year:
                self.available.next_year()
        # If not a dict, we can 'advance' by clearing:
        else:
            self.available.clear()

    def add_transaction(
        self, value, when=Decimal(0.5), frequency=None,
        from_account=None, to_account=None, strict_timing=False
    ):
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

        If `frequency` is provided, then `transaction` is split
        up into `frequency` equal amounts over `frequency` equally-
        spaced payment periods. The `when` parameter determines
        when in each payment period the transactions are made.

        Args:
            value (Money): The value of the transaction.
                Positive for inflows, negative for outflows.
            when (Decimal): The time at which the transaction occurs.
                Expressed as a value in [0,1]. Optional.
            frequency (int): The number of transactions made in the
                year. Must be positive. Optional.
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
        when = when_conv(when)

        # If a `frequency` has been passed, split up the transaction
        # into several equal-value and equally-spaced transactions.
        if frequency is not None:
            value = value / frequency
            for timing in range(0, frequency):
                # Note that `when` is still used to determine the
                # timing of each transaction within its sub-period.
                self._add_transaction(
                    value=value, when=(timing+when)/frequency,
                    from_account=from_account, to_account=to_account,
                    strict_timing=strict_timing)
        # Otherwise, just add a single transaction:
        else:
            self._add_transaction(
                value=value, when=when,
                from_account=from_account, to_account=to_account,
                strict_timing=strict_timing)

    def _add_transaction(
        self, value, when, from_account, to_account, strict_timing
    ):
        """ Helper for `add_transaction`.

        This method provides the high-level logical flow for 
        adding a single transaction. Calling code is responsible
        for sanitizing inputs, dealing with multiple transactions,
        and providing sensible default values where appropriate.
        """
        # For convenience, ensure that we're withdrawing from
        # from_account and depositing to to_account:
        if value < 0:
            from_account, to_account = to_account, from_account
            value = -value

        if from_account is not None and not strict_timing:
            # Shift when, if appropriate:
            when = self._shift_when(
                value=value, when=when, account=from_account)
        self._add_transaction_to_account(
            value=-value, when=when, account=from_account)

        # No need to shift `when` for to_account:
        self._add_transaction_to_account(
            value=value, when=when, account=to_account)

        # Track transactions to/from `available` separately:
        if from_account is self.available:
            self.transactions[when] -= value
        if to_account is self.available:
            self.transactions[when] += value

    def _add_transaction_to_account(self, value, when, account):
        """ Records a transaction against an account. """
        if account is None:
            # Allow None for convenience in calling code.
            return
        elif isinstance(account, Account):
            # We _could_ use the below generic, dict-based logic
            # for Account objects too, but prefer to invoke
            # `add_transaction` explicitly when possible.
            account.add_transaction(-value, when=when)
        else:
            account[when] = (
                account.get(when, Money(0)) - value)

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

        The method also attemptes to interpolate additional times between
        the existing transactions where the amount available to be
        withdrawn is equal to `target_value`. Due to implementation
        limitations, the exact timing is not guaranteed to ne found
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
                    (accum[later] > target_value
                        and accum[earlier] < target_value)
                    or (accum[later] < target_value
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
                        accum[time] = -account.max_outflow[time]
        return accum

""" TODO """

from collections import defaultdict
from copy import copy
from decimal import Decimal
from forecaster.ledger import (
    Ledger, Money,
    recorded_property, recorded_property_cached
)
from forecaster.utility import when_conv

class SubForecast(Ledger):
    """ TODO """

    def __init__(self):
        """ TODO """
        self.transactions = defaultdict(lambda: Money(0))
        self.available = defaultdict(lambda: Money(0))

    def next_year(self, available):
        """ TODO """
        # Call `next_year` first so that recorded_property values
        # are recorded with their current state:
        super().next_year()
        # Now update available/transactions for the new year:
        self.available = copy(available)
        self.transactions = defaultdict(lambda: Money(0))

    '''
    def add_transaction(
        self, value, when=Decimal(0.5), frequency=None,
        from_account=None, to_account=None,
        from_value=None, to_value=None
    ):
        # Sanitize input:
        when = when_conv(when)
        if from_account is None or from_value is None:
            from_value = value
        if to_account is None or to_value is None:
            to_value = value

        # If a `frequency` has been passed, split up the transaction
        # into several transactions with appropriate values and timing.
        if frequency is not None:
            value = value / frequency
            from_value = from_value / frequency
            to_value = to_value / frequency
            # Add `frequency` number of transactions, with equal
            # amounts and even spacing. Each transaction occurs in a
            # period of length equal to `frequency`. The point in that
            # period when it occurs is determined by `when`. For
            # example, by default each transaction occurs at the end
            # of its period (i.e. at `when=1`).
            for timing in range(0, frequency):
                self._add_transaction(
                    value,
                    when=(timing+when)/frequency,
                    from_account=from_account, to_account=to_account,
                    from_value=from_value, to_value=to_value)
        else:
            self._add_transaction(
                value=value, when=when,
                from_account=from_account, to_account=to_account,
                from_value=from_value, to_value=to_value)
    '''

    def _add_transaction(
        self, value, when=None, frequency=None,
        account=None, account_value=None
    ):
        """ Records a transaction at a time that balances the books.

        This method will always add the transaction at or after `when`
        (or at or after the implied timing provided by `frequency`).
        It tries to find a time where adding the transaction would
        avoid going cash-flow negative or putting an account into
        a negative balance.

        In particular, it tries to find the _earliest_ such time.
        Thus, the timing will be equal to `when` if that timing
        meets this constraint. `when` is also used if no such
        time can be found.

        Transaction values have the same semantics as account
        transaction values, meaning that positive values represent
        inflows to an account. This _reduces_ the cash available
        for future transactions (i.e. it will result in a _negative_
        value being added to `SubForecast.available`). Negative
        values have the reverse effect; they create outflows from
        accounts and increase the cash available.

        At least one of `when` and `frequency` must be provided.
        If `frequency` is provided, then `transaction` is split
        up into `frequency` equal amounts and each amount is
        contributed at the end of `frequency` payment periods.

        Example:
            `self.add_transaction(Money(1000), 'start')`
            `self.add_transaction(Money(1000), Decimal(0.5))`
            `self.add_transaction(Money(-2000), Decimal(0.25))`
            `# The transaction is added at when=0.5`
        
        Args:
            value (Money): The value of the transaction.
                Positive for inflows, negative for outflows.
            when (Decimal): The time at which the transaction occurs.
                Expressed as a value in [0,1]. Optional.
            frequency (int): The number of transactions made in the
                year. Must be positive. Optional.
            account (Account): An account to which the transaction
                is to be added. Optional.
            account_transaction (Money): If provided, this amount
                will be added to `account` instead of `value`.

        Example:
            `f.add_transaction(Money(10), Decimal(0.5))`
            `# f._transactions = {0.5: Money(10)}`
            `f.add_transaction(Money(-10), Decimal(0.5))`
            `# f._transactions = {0.5: Money(0)}`
        """
        # TODO: This method would look a lot more sane if it
        # let you provide two accounts: a `from` account and
        # a `to` account. If we represented `available` as
        # an account, we could easily handle it without special
        # logic. We could allow None values to reflect that
        # money is coming from or going to somewhere outside
        # the model (e.g. living expenses).

        # Sanitize input:
        when = when_conv(when)
        if account is None or account_value is None:
            account_value = value

        # If a `frequency` has been passed, split up the transaction
        # into several transactions with appropriate values and timing.
        if frequency is not None:
            self._add_transaction_frequency_recurse(
                value=value, when=when, frequency=frequency,
                account=account, account_value=account_value)
            return

        # Figure out how much money is available to work with at each
        # time at or after `when`:
        if value >= 0:
            # For inflows, look at cash on-hand (i.e. `available`)
            accum = self._accum_available(
                transactions=self.available, when=when, value=value)
        elif account is not None:
            # For outflows, look at cash in the account:
            accum = self._accum_available(
                transactions=account.transactions, when=when,
                account=account, value=account_value
            )
        else:
            # If this is an outflow with no account, assume it can be
            # made at the requested time.
            accum = {when: value}

        # Find the points in time where subtracting `value` would not
        # put any future point in time into negative balance.
        eligible_times = (
            t for t in accum if all(
                accum[r] >= -value for r in accum if r >= t
            )
        )
        # Find the earliest time that satisfies our requirements
        # (or, if none exists, use the time requested by the user)
        earliest_time = min(eligible_times, default=when)

        # We've found the time; now add the transaction!
        self.transactions[earliest_time] -= value
        self.available[earliest_time] -= value
        # Also add to the account, if passed:
        if account is not None:
            # Use the account_transaction amount, if passed,
            # otherwise fall back to `transaction`
            account.add_transaction(
                account_value,
                when=earliest_time)

    def _accum_available(self, transactions, when, account=None, value=None):
        """ Accumulates transaction histories to provide cash available.
        
        This method takes a dict of `{when: value}` transaction pairs and
        returns a dict of `{when: value}` pairs where the values, instead
        of being transaction amounts, represent the total amount of cash
        available at time `when`.
        
        If there's no growth rate associated with the pool of money,
        this is simply the sum of all prior transactions - hence the
        references to accumulation. For accounts with rates of growth,
        this is not exactly the same as the sum of prior transactions.

        Returns:
            A dict of `{Decimal: Money}` pairs. The keys will include
            all times in `transactions` at or after `when`, plus
            `when` (if not already included). If `account` and `value`
            are provided, this method will also include additional times
            where growth results in the target value being achieved
            between transaction times.
        """
        # First, figure out how much money is available at each point
        # in time, starting with `when`:
        if account is None:
            accum = {
                t: sum(
                    # For each point in time `t`, find the sum of all
                    # transactions up to this point:
                    transactions[r] for r in transactions if r <= t)
                # We don't need to include times before `when`, but
                # we do want to include `when` even if there's no
                # transaction at that time:
                for t in transactions.keys() ^ when if t >= when
            }
        else:
            # For accounts, let the account logic determine how much
            # is available in the account at each time:
            accum = {
                t: -account.max_outflow(t)
                # We don't need to include times before `when`, but
                # we do want to include `when` even if there's no
                # transaction at that time:
                for t in transactions.keys() ^ when if t >= when
            }
            # Try to interpolate times where we achieve the desired
            # value, if that value is known:
            if value is not None:
                # We want to look at each time (except the first) and
                # the time immediately prior to it.
                times = sorted(accum.keys())  # NOTE: ascending order
                for i in range(1, len(times)):
                    earlier = times[i-1]
                    later = times[i]
                    # We only care about pairs where the desired value
                    # falls between the times in question:
                    if (
                        (accum[later] > value and accum[earlier] < value)
                        or (accum[later] < value and accum[earlier] > value)
                    ):
                        # HACK: This code uses the account _balance_
                        # as a proxy for money available for withdrawal. 
                        # This isn't always accurate; e.g. `Debt`
                        # account balances don't tell you how much
                        # can be withdrawn. This is why we use
                        # `max_outflow`, but there's no interface for
                        # determining the inverse of `max_outflow`
                        # similar to `balance_at_time`. We could add
                        # a `time_to_max_outflow` method to the spec
                        # for `Account`, but this quickly adds complexity
                        # for a very niche feature.
                        # Since this method doesn't guarantee that it
                        # will find the exact moment that a certain
                        # amount is available, it's OK to use this
                        # hack to make an educated guess, since it
                        # doesn't add any _incorrect_ values; just
                        # perhaps non-useful ones!

                        # Ask the account to find an in-between time
                        # where we hit the desired value exactly.
                        time = account.time_to_balance(
                            value=value, when=earlier)
                        # If that time falls within the period
                        # (earlier, later), then add it!
                        if time > times[i-1] and time < times[i]:
                            accum[time] = -account.max_outflow[time]
        return accum

    def _add_transaction_frequency_recurse(
        self, value, frequency, when=1,
        account=None, account_value=None
    ):
        """ Records multiple transactions with a given frequency.
        
        This is a helper method for `add_transaction`. It splits up
        the transaction value into several equally-valued and
        evenly-spaced transactions based on `frequency`, then
        calls `add_transaction` on each of those new transactions.
        """
        # Split up transaction amounts based on the number of payments:
        value = value / frequency
        if account_value is not None:
            account_value = account_value / frequency

        # Add `frequency` number of transactions, with equal amounts
        # and even spacing. Each transaction occurs in a period of length
        # equal to `frequency`. The point in that period when it occurs
        # is determined by `when`. For example, by default each transaction
        # occurs at the end of its period (when=1).
        for timing in range(0, frequency):
            self._add_transaction(
                value,
                when=(timing+when)/frequency,
                account=account,
                account_value=account_value)

""" Defines helper functions for identifying an account's min/max. """

from forecaster.accounts import LimitTuple

# TODO: Move LimitTuple constants to forecaster.accounts module.
# Consider going further and refactoring `Account` so that
# `max_inflows`/etc and `max_inflow_link`/etc are held by LimitTuples
# (e.g. so client code accesses `transaction_schedule.max_inflow`
# or `link.max_inflow` instead). Is this pythonic?

# Map LimitTuple fields to the names of AccountLink members of
# LinkedLimitAccount objects:
LINK_FIELD_NAMES = LimitTuple(
    'min_inflow_link', 'max_inflow_link',
    'min_outflow_link', 'max_outflow_link')
# Map LimitTuple fields to the named of min/max inflow/outflow members
# of Account objects:
TRANSACTION_LIMIT_FIELD_NAMES = LimitTuple(
    'min_inflows', 'max_inflows', 'min_outflows', 'max_outflows')

def transaction_default_methods(field_names=TRANSACTION_LIMIT_FIELD_NAMES):
    """ Returns methods for finding min/max in/outflows as a LimitTuple. """
    methods = []
    # Rather than write out four separate methods that return
    # min_inflows, max_inflows, ..., we write a generator for such
    # methods and return a full set of them as a LimitTuple:
    for field_name in field_names:
        # We use `field_name` as a default value to avoid the issue
        # where the closure will use the most recent value for
        # `field_name` rather than the value at the time the closure
        # was defined. (This could also be solved by using a partial).
        # The default value is locked in at definition time.
        methods.append(lambda account, name=field_name: getattr(account, name))
    return LimitTuple(*methods)

TRANSACTION_DEFAULT_METHODS = transaction_default_methods()

def group_default_methods(field_names=LINK_FIELD_NAMES):
    """ Returns methods returning sets of linked accts. as a LimitTuple. """
    methods = []
    # Rather than write out four separate methods that return
    # min_inflow_link, max_inflow_link, ..., we write a generator for
    # such methods and return a full set of them as a LimitTuple:
    for field_name in field_names:
        # Define a method that returns the group of linked accounts for
        # a given link (e.g. `max_inflow_link`).
        # NOTE: Use `field_name` as a default value to avoid the issue
        # where the closure will use the most recent value for
        # `field_name` rather than the value at the time the closure
        # was defined. (This could also be solved by using a partial).
        # The default value is locked in at definition time.
        def default_method(account, name=field_name):
            # Return the group for the given link if the link exists:
            if hasattr(account, name):
                link = getattr(account, name)
                if link is not None:
                    return link.group
            # If the account doesn't have a link (either because it's
            # not a LinkedLimitAccount or similar, or because its link
            # is None), then simply return None:
            return None
        # default_method over. It will be added to the LimitTuple later.
        methods.append(default_method)
    return LimitTuple(*methods)

GROUP_DEFAULT_METHODS = group_default_methods()

def reduce_limit_default_methods():
    """ Returns methods for reducing limits based on transactions. """
    def add_inflows(limit, transactions):
        """ Reduces inflow limit based on transactions. """
        # No change if there are no net inflows:
        if transactions > 0:
            # Limits on inflows must be non-negative:
            limit = max(limit - transactions, 0)
        return limit
    def add_outflows(limit, transactions):
        """ Reduces outflow limit based on transactions. """
        # No change if there are no net outflows:
        if transactions < 0:
            # Limits on outflows must be non-positive:
            limit = min(limit - transactions, 0)
        return limit
    return LimitTuple(
        min_inflow=add_inflows, max_inflow=add_inflows,
        min_outflow=add_outflows, max_outflow=add_outflows)

def is_done_default(
        group, limit_key, timing=None, transactions=None, memo=None,
        transaction_methods=None):
    """ Returns True if the group cannot receive any more allocation. """
    # If we've already determined whether this group is done, return now
    if memo is not None and group in memo:
        return memo[group] == 0

    # Parse inputs:
    if transaction_methods is None:
        transaction_methods = TRANSACTION_DEFAULT_METHODS

    # Grab a random account from the group:
    account = next(iter(group))
    # Grab the method for identifying the account's transaction method:
    transaction_method = getattr(transaction_methods, limit_key)
    # Get the method for allocating transactions:
    method = transaction_method(account)
    # Allocate the transactions.
    # Pass in transactions already allocated to this account and
    # transactions allocated against others in its group so that the
    # method can reduce its allocation accordingly:
    if account in transactions:
        account_transactions = transactions[account]
    else:
        account_transactions = None
    transactions = method(
        timing=timing,
        transactions=account_transactions,
        group_transactions=transactions)
    # Sum up the total of the transactions:
    total = sum(transactions.values())

    # Record the result in memo, if provided:
    if memo is not None:
        memo[group] = total
    # If no transactions could be allocated, this group is _done_:
    return total == 0

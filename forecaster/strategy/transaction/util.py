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

def _convert_flows_to_transactions(
        flows, timing, limit, accounts, transaction_methods,
        total=None, precision=1, transaction_type=None):
    """ TODO """
    if transaction_methods is None:
        transaction_methods = transaction_default_methods()
    # If `total` is negative, all flows should be outflows
    # (and thus need to be flipped to negative sign).
    is_outflows = total is not None and total < 0
    transactions = {}
    for account in accounts:
        if account in flows:
            # NOTE: We scale down the flows to the account by a
            # factor of `precision` because all flows/capacities
            # are automatically inflated to avoid rounding errors.
            total_flows = precision * sum(flows[account].values())
            if is_outflows:
                total_flows = -total_flows
            # Convert to `transaction_type`, if provided:
            if transaction_type is not None:
                total_flows = transaction_type(total_flows)
            transactions[account] = _get_transactions(
                account, limit, timing,
                transaction_methods=transaction_methods, total=total_flows)
    return transactions

def _get_accounts(node, accounts=None):
    """ TODO """
    # Set defaults (for recursion)
    if accounts is None:
        accounts = set()

    # If this is a leaf, record its account:
    if node.is_leaf_node():
        accounts.add(node.source)
    # Otherwise, recurse onto children:
    else:
        for child in node.children:
            _get_accounts(child, accounts)

    return accounts

def _get_transactions(
        account, limit, timing, transaction_methods=None, total=None):
    """ TODO """
    if transaction_methods is None:
        transaction_methods = transaction_default_methods()
    if limit is None:
        return {}
    # This is ugly, but it works. Someday we should refactor this:
    selector_method = getattr(transaction_methods, limit)
    transaction_method = selector_method(account)
    return transaction_method(timing, transaction_limit=total)

def _get_group(account, limit, group_methods=None):
    """ TODO """
    if group_methods is None:
        group_methods = group_default_methods()
    group_method = getattr(group_methods, limit)
    return group_method(account)

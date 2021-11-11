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
        total=None, precision=1, high_precision=None):
    """ Converts network flows to a mapping of accounts to transactions.

    Args:
        flows (dict[Hashable, dict[Hashable, int]]): Flows across edges
            between nodes, as `from_node: (to_node: flow_amount)`
            triples.
        timing (Timing): The timing with which transactions are made to
            accounts.
        limit (str): The name for the appropriate attribute of
            `LimitTuple` to use for this traversal (e.g. "min_inflow",
            "max_outflow")
        accounts (Iterable[Hashable]): A collection of nodes in `flows`;
            only these nodes will be used as keys in the return value.
        transaction_methods (LimitTuple[Callable, Callable, Callable,
            Callable]): A `namedtuple` that provides a `Callable` value
            for the attribute with the name given by `limit`. That
            function must take a single argument (an account from
            `accounts`) and return a method which, when called, returns
            a time-series of transactions
            (as `dict[Number, Union[Number, Money]]`).
        total (Union[Number, Money]): The total amount of inflows
            (positive) or outflows (negative).
            This method only uses this value for its sign.
        precision (Number): Flows are *multiplied* by this factor prior
            to being used to generate transaction values. Optional.
            This makes it easy to scale down values that were inflated
            to avoid rounding error when the graph was defined.
        high_precision (Callable[[float], T]): If provided, each flow
            value is passed to `high_precision` as its sole arg. It is
            expected that `high_precision` will wrap it in a
            high-precision numerical type suitable for the applicable
            member of `transaction_methods`.
            Optional.

    Returns:
        dict[Hashable, dict[Number, Any]]: A mapping of accounts to
        transactions (as `dict[Number, Any]` time-series, where the
        value type is determined by the account via
        `transaction_methods` - usually `Money` for `Account` and its
        subclasses).
    """
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
            # Convert to a high-precision type, if provided:
            if high_precision is not None:
                total_flows = high_precision(total_flows)
            transactions[account] = _get_transactions(
                account, limit, timing,
                transaction_methods=transaction_methods, total=total_flows)
    return transactions

def _get_accounts(node, accounts=None):
    """ Returns the objects wrapped by all leaf nodes.

    Args:
        node (TransactionNode): The root of a (sub)tree.
        accounts (set[Any]): The set of all accounts found so far.
            Used by this method on recursion; if passed in by client
            code, beware that it will be mutated!

    Returns:
        set[Any]: A collection of objects (which can be of any type)
        wrapped by lead nodes under `node`.
    """
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
    """ Gets transactions for `account`.

    This is a generic method that allows for any type to be wrapped by
    a leaf node, not just `Account` and its subclasses. All that needs
    to be done is to pass a `transaction_methods` with suitable
    functions for the given type(s). See below for more details.

    Args:
        account (Any): The object based on which transactions will be
            generated.
        timing (Timing): The timings (and corresponding weights) with
            which transactions are made to accounts.
        limit (str): The name for the appropriate attribute of
            `LimitTuple` to use for this traversal (e.g. "min_inflow",
            "max_outflow")
        transaction_methods (LimitTuple[Callable, Callable, Callable,
            Callable]): A `namedtuple` that provides a `Callable` value
            for the attribute with the name given by `limit`.

            The given function must take a single argument: `account`.
            It returns a `Callable` (usually a method bound to
            `account`) which takes `timing` as a positional arg and
            `total` as an (optional) keyword arg and returns a
            time-series of transactions
            (as `dict[Number, Union[Number, Money]]`).
        total (Union[Number, Money]): The maximum amount of inflows
            (positive) or outflows (negative) to transact.

    Returns:
        dict[Number, Union[Number, Money]]: A time-series that maps
        timings to transaction amounts. The typing of transaction amount
        values is determined by the account, via
        `transaction_methods`. (This is usually `Money` for `Account`
        and its subclasses).
    """
    if transaction_methods is None:
        transaction_methods = transaction_default_methods()
    if limit is None:
        return {}
    # This is ugly, but it works. Someday we should refactor this:
    selector_method = getattr(transaction_methods, limit)
    transaction_method = selector_method(account)
    return transaction_method(timing, transaction_limit=total)

def _get_group(account, limit, group_methods=None):
    """ Gets a group of accounts related to `account` for a given limit.

    This is a generic method that allows for any type to be wrapped by
    a leaf node, not just `Account` and its subclasses. All that needs
    to be done is to pass a `group_methods` with suitable
    functions for the given type(s). See below for more details.

    Args:
        account (Any): The object based on which transactions will be
            generated.
        limit (str): The name for the appropriate attribute of
            `LimitTuple` to use for this traversal (e.g. "min_inflow",
            "max_outflow")
        group_methods (LimitTuple[Callable, Callable, Callable,
            Callable]): A `namedtuple` that provides a `Callable` value
            for the attribute with the name given by `limit`.

            The given function must take a single argument: `account`.
            It returns a `Container` holding all accounts which are
            related to `account` for the given `limit`. For example,
            for `limit="max_inflow", this function might return a set of
            all accounts which share contribution room with `account`.

    Returns:
        Container[Any]: A collection holding all accounts which are
        related to `account` for the given `limit`.
    """
    if group_methods is None:
        group_methods = group_default_methods()
    group_method = getattr(group_methods, limit)
    return group_method(account)

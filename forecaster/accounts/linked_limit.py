""" A module providing the LinkedLimitAccount class. """

from copy import copy
from forecaster.accounts.base import Account
from forecaster.accounts.link import AccountLink
from forecaster.utility import add_transactions

class LinkedLimitAccount(Account):
    """ An account with inflow/outflow limits linked to other accounts.

    Inflow and outflow limits may be shared between accounts. Such
    accounts should share a token for the corresponding inflow/outflow
    limit (e.g. `max_inflow_token`, `min_outflow_token`, etc.). This is
    registered with the corresponding token owner (e.g.
    `max_inflow_owner`, `min_outflow_owner`). By default, the account's
    `owner` is used for each of these.

    Accounts that this `LinkedLimitAccount` is linked to for a given
    limit can be accessed via the corresponding `*_group` property (e.g.
    `max_inflow_group` for the `max_inflow_limit` property).

    This is an abstract base class. Any subclass must implement the
    method `next_contribution_room`, which returns the contribution
    room for the following year.

    Example:
        All instances of this class with the same owner will share
        their contribution room (i.e. max_inflow limit)::

            class RegisteredAccount(LinkedLimitAccount):
                def __init__(self):
                    token = type(self).__name__
                    super().__init__(max_inflow_token=token)

    Attributes:
        max_inflow_limit (Money): Inherited from `Account`. The max.
            amount that may be contributed in the current year.
        max_inflow_link ((Person, str)): An `(owner, token)` pair.
            Accounts which share the same `(owner, token)` pair
            will share the same `max_inflow_limit`.

        min_inflow_limit (Money): Inherited from `Account`. The min.
            amount that must be contributed in the current year.
        min_inflow_link ((Person, str)): An `(owner, token)` pair.
            Accounts which share the same `(owner, token)` pair
            will share the same `min_inflow_limit`.

        max_outflow_limit (Money): Inherited from `Account`. The max.
            amount that may be withdrawn in the current year.
        max_outflow_link ((Person, str)): An `(owner, token)` pair.
            Accounts which share the same `(owner, token)` pair
            will share the same `max_outflow_limit`.

        min_outflow_limit (Money): Inherited from `Account`. The min.
            amount that must be withdrawn in the current year.
        min_outflow_link ((Person, str)): An `(owner, token)` pair.
            Accounts which share the same `(owner, token)` pair
            will share the same `min_outflow_limit`.
    """

    def __init__(
            self, *args,
            max_inflow_link=None, max_inflow_limit=None,
            min_inflow_link=None, min_inflow_limit=None,
            max_outflow_link=None, max_outflow_limit=None,
            min_outflow_link=None, min_outflow_limit=None,
            **kwargs):
        """ Initializes a LinkedLimitAccount object. """
        super().__init__(*args, **kwargs)

        # It's repetitive to clean, register, and assign each of the
        # four types of inflow links repeatedly, so the bulk of __init__
        # logic is moved to _process_link and it's just repeated here.
        self.max_inflow_link = self._process_link(
            max_inflow_link, limit=max_inflow_limit)
        self.min_inflow_link = self._process_link(
            min_inflow_link, limit=min_inflow_limit)
        self.max_outflow_link = self._process_link(
            max_outflow_link, limit=max_outflow_limit)
        self.min_outflow_link = self._process_link(
            min_outflow_link, limit=min_outflow_limit)

    @property
    def max_inflow_limit(self):
        """ The maximum amount that can be contributed to the account. """
        return self._get_limit(
            self.max_inflow_link, super().max_inflow_limit)

    @max_inflow_limit.setter
    def max_inflow_limit(self, value):
        """ Sets max_inflow_limit. """
        self._set_limit(self.max_inflow_link, value)

    @property
    def min_inflow_limit(self):
        """ The minimum amount to be contributed to the account. """
        return self._get_limit(
            self.min_inflow_link, super().min_inflow_limit)

    @min_inflow_limit.setter
    def min_inflow_limit(self, value):
        """ Sets min_inflow_limit. """
        self._set_limit(self.min_inflow_link, value)

    @property
    def max_outflow_limit(self):
        """ The maximum amount that can be withdrawn from the account. """
        return self._get_limit(
            self.max_outflow_link, super().max_outflow_limit)

    @max_outflow_limit.setter
    def max_outflow_limit(self, value):
        """ Sets max_outflow_limit. """
        self._set_limit(self.max_inflow_link, value)

    @property
    def min_outflow_limit(self):
        """ The minimum amount to be withdrawn from the account. """
        return self._get_limit(
            self.min_outflow_link, super().min_outflow_limit)

    @min_outflow_limit.setter
    def min_outflow_limit(self, value):
        """ Sets min_outflow_limit. """
        self._set_limit(self.min_inflow_link, value)

    def _get_limit(self, link, default=None):
        """ Gets the limit for a given linked group of accounts.

        Args:
            link (AccountLink): A link object pointing to a record
                shared by all accounts sharing `link`.
            default (Any): The value to return if `link` is `None`.
                Optional.

        Returns:
            Money: The limit corresponding to `link`.
        """
        if link is not None:
            return link.data
        else:
            return default

    def _set_limit(self, link, value):
        """ Sets the limit for a given linked group of accounts.

        Args:
            link (AccountLink): A link object pointing to a record
                shared by all accounts sharing `link`.
            value (Any): The value to store in the shared record.

        Raises:
            AttributeError: Cannot set limit if `link` is None.
        """
        if link is not None:
            # Update centrally-managed record:
            link.data = value
        else:
            # If there is no link, we cannot set its limit:
            raise AttributeError('Cannot set limit if link is None')

    def _process_link(
            self, link, limit=None, default_factory=lambda: None):
        """ Convenience method for __init__ when processing inputs.

        Args:
            link (Union[tuple[Person, str], AccountLink]): An
                `AccountLink` or `AccountLink`-convertible value that
                uniquely identifies the link between accounts.
            limit (Any): The value all accounts sharing `link` should
                share as a limit. If provided, overrides any value
                provided by `default_factory`. Optional.
            default_factory (Callable): If this method is creating a
                new link (i.e. one which does not yet have a limit
                value), then this 0-arg function will be called and its
                return value will be used to populate the shared limit
                value record. Optional.

        Returns:
            AccountLink: An object representing a link between accounts
            and pointing to their shared limit record.
        """
        # Nothing to do if no link is provided:
        if link is None:
            return None
        # Try to cast `link` to `AccountLink` if it isn't already:
        if not isinstance(link, AccountLink):
            # NOTE: This will generate a shared `LimitRecord` object
            # that all linked accounts can access.
            link = AccountLink(link, default_factory=default_factory)
        # Add this account to the group of linked accounts:
        link.link_account(self)
        # If `limit` is provided, overwrite any existing limit:
        if limit is not None:
            link.data = limit
        return link

    def _merge_transactions(self, transactions, group_transactions, link):
        """ Merges `group_transactions` and `transactions`.

        Only linked accounts have their transactions in
        `group_transactions` added to `transactions`. Any keys in
        `group_transactions` which are not linked (per `link`) are
        ignored.

        If `transactions` is provided, any transactions for this account
        in `group_transactions` are ignored.

        Args:
            transactions (Union[dict[Number, Money], NoneType]): A
                time-series of transactions for this account.
                May be `None`.
            group_transactions
                (Union[dict[Account, dict[Number, Money]], NoneType]):
                A mapping of `Account` keys to `transactions`-like
                values. Keys not linked (according to `link`) are
                ignored.
            link (AccountLink): An object defining a collection of
                linked accounts.

        Returns:
            dict[Number, Money]: A time-series of transactions formed
            by merging `transactions` (if provided) with the
            transactions mapped by any accounts of `group_transactions`
            (if provided) which are linked to this account.
        """
        # For convenience, use an empty iterable rather than `None`:
        if group_transactions is None:
            group_transactions = set()

        # We want to return `transactions`, but we don't want to mutate
        # any of the inputs, so copy it first:
        if transactions is not None:
            transactions = copy(transactions)
        elif self in group_transactions:
            # If `transactions` isn't given, but this account is
            # represented in `group_transactions`, use that:
            transactions = copy(group_transactions[self])
        else:
            # Otherwise, just start with a empty dict to fill later:
            transactions = {}

        # If this account isn't linked (for this type of inflow/outflow,
        # anyways), we're done:
        if link is None:
            return transactions

        # Otherwise, merge the transactions for each other linked
        # account in the group (note that this account is handled above)
        group = link.group - {self}
        for account in group:
            # Add the transactions already recorded against the account:
            add_transactions(transactions, account.transactions)
            # And add any additional transactions, if present in
            # `group_transactions`:
            if account in group_transactions:
                add_transactions(transactions, group_transactions[account])
        return transactions

    def max_inflows(
            self, *args, transactions=None, group_transactions=None, **kwargs):
        """ The maximum amounts that can be contributed to the account.

        This overloaded method simply provides a new argument
        (`group_transactions`). See `Account.max_inflows` for
        documentation of other arguments and method behaviour.

        Args:
            transactions (dict[Decimal, Money]): If provided, the result
                will be determined as if the account also had these
                transactions recorded against it. Optional.
            group_transactions (dict[Account, dict[Number, Money]]):
                A mapping of `Account` keys to `transactions`-like
                values. Any transactions mapped to accounts with a max
                inflow limit linked to this one will be added to
                `transactions` when determining the result. Optional.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                `value` indicates the maximum inflow permitted.
        """
        # pylint: disable=too-many-arguments,arguments-differ
        # This method just adds an extra optional argument.

        # Merge `transactions` and `group_transactions`:
        transactions = self._merge_transactions(
            transactions, group_transactions, self.max_inflow_link)
        return super().max_inflows(
            *args, transactions=transactions, **kwargs)

    def max_outflows(
            self, *args, transactions=None, group_transactions=None, **kwargs):
        """ The maximum amounts that can be withdrawn from the account.

        This overloaded method simply provides a new argument
        (`group_transactions`). See `Account.max_outflows` for
        documentation of other arguments and method behaviour.

        Args:
            transactions (dict[Decimal, Money]): If provided, the result
                will be determined as if the account also had these
                transactions recorded against it. Optional.
            group_transactions (dict[Account, dict[Number, Money]]):
                A mapping of `Account` keys to `transactions`-like
                values. Any transactions mapped to accounts with a max
                outflow limit linked to this one will be added to
                `transactions` when determining the result. Optional.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                `value` indicates the maximum outflow permitted.
        """
        # pylint: disable=too-many-arguments,arguments-differ
        # This method just adds an extra optional argument.

        # Merge `transactions` and `group_transactions`:
        transactions = self._merge_transactions(
            transactions, group_transactions, self.max_outflow_link)
        return super().max_outflows(
            *args, transactions=transactions, **kwargs)

    def min_inflows(
            self, *args, transactions=None, group_transactions=None, **kwargs):
        """ The minimum amounts that must be contributed to the account.

        This overloaded method simply provides a new argument
        (`group_transactions`). See `Account.min_inflows` for
        documentation of other arguments and method behaviour.

        Args:
            transactions (dict[Decimal, Money]): If provided, the result
                will be determined as if the account also had these
                transactions recorded against it. Optional.
            group_transactions (dict[Account, dict[Number, Money]]):
                A mapping of `Account` keys to `transactions`-like
                values. Any transactions mapped to accounts with a min
                inflow limit linked to this one will be added to
                `transactions` when determining the result. Optional.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                `value` indicates the minimum inflow required.
        """
        # pylint: disable=too-many-arguments,arguments-differ
        # This method just adds an extra optional argument.

        # Merge `transactions` and `group_transactions`:
        transactions = self._merge_transactions(
            transactions, group_transactions, self.min_inflow_link)
        return super().min_inflows(
            *args, transactions=transactions, **kwargs)

    def min_outflows(
            self, *args, transactions=None, group_transactions=None, **kwargs):
        """ The minimum amounts that must be withdrawn from the account.

        This overloaded method simply provides a new argument
        (`group_transactions`). See `Account.min_outflows` for
        documentation of other arguments and method behaviour.

        Args:
            transactions (dict[Decimal, Money]): If provided, the result
                will be determined as if the account also had these
                transactions recorded against it. Optional.
            group_transactions (dict[Account, dict[Number, Money]]):
                A mapping of `Account` keys to `transactions`-like
                values. Any transactions mapped to accounts with a min
                outflow limit linked to this one will be added to
                `transactions` when determining the result. Optional.

        Returns:
            dict[float, Money]: A mapping of `{when: value}` pairs where
                `value` indicates the minimum outflow required.
        """
        # pylint: disable=too-many-arguments,arguments-differ
        # This method just adds an extra optional argument.

        # Merge `transactions` and `group_transactions`:
        transactions = self._merge_transactions(
            transactions, group_transactions, self.min_outflow_link)
        return super().min_outflows(
            *args, transactions=transactions, **kwargs)

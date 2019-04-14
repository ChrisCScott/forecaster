""" A module providing the LinkedLimitAccount class. """

from dataclasses import dataclass, field
from forecaster.accounts.base import Account
from forecaster.accounts.link import AccountLink
from forecaster.ledger import Money


@dataclass
class LimitRecord:
    """ Stores a transaction limit for a group of linked accounts. """
    limit: Money = field(default_factory=Money)

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
        # All instances of this class with the same owner will share
        # their contribution room (i.e. max_inflow limit):
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

        default_factory (Callable): A callable object (e.g. a lambda
            expression) which takes no arguments and returns an object
            of any type. Inspired by `defaultdict`'s `default_factory`
            argument. Optional.

            The returned object is used to initialize the shared data
            record when the link is first registered.
            Defaults to `LimitRecord`. Whatever is returned, it should
            have a Money-valued `limit` attribute.
    """

    def __init__(
            self, *args,
            max_inflow_link=None, max_inflow_limit=None,
            min_inflow_link=None, min_inflow_limit=None,
            max_outflow_link=None, max_outflow_limit=None,
            min_outflow_link=None, min_outflow_limit=None,
            default_factory=LimitRecord,
            **kwargs):
        """ Initializes a LinkedLimitAccount object. """
        super().__init__(*args, **kwargs)

        # It's repetitive to clean, register, and assign each of the
        # four types of inflow links repeatedly, so the bulk of __init__
        # logic is moved to _process_link and it's just repeated here.
        self.max_inflow_link = self._process_link(
            max_inflow_link, limit=max_inflow_limit,
            default_factory=default_factory)
        self.min_inflow_link = self._process_link(
            min_inflow_link, limit=min_inflow_limit,
            default_factory=default_factory)
        self.max_outflow_link = self._process_link(
            max_outflow_link, limit=max_outflow_limit,
            default_factory=default_factory)
        self.min_outflow_link = self._process_link(
            min_outflow_link, limit=min_outflow_limit,
            default_factory=default_factory)

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
        """ TODO """
        if link is not None:
            return link.data.limit
        else:
            return default

    def _set_limit(self, link, value):
        """ TODO """
        if link is not None:
            # Update centrally-managed record:
            link.data.limit = value
        else:
            # Raises AttributeError:
            raise AttributeError('property does not provide setter')

    def _process_link(self, link, limit=None, default_factory=LimitRecord):
        """ Convenience method for __init__ when processing inputs. """
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
            link.data.limit = limit
        return link

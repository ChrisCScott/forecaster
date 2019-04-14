""" A module providing a tool for linking accounts via an owner. """

from collections import namedtuple, abc
from dataclasses import dataclass, field
from typing import Any

LinkTuple = namedtuple('LinkTuple', ['owner', 'token'])

# Use a dataclass instead of namedtuple to provide mutability of `data`:
@dataclass
class LinkRecord:
    """ Stores a transaction limit for a group of linked accounts. """
    # By default, `LinkRecord` inits to (group=set(), data={})
    group: set = field(default_factory=set)
    data: Any = field(default_factory=dict)

class AccountLink:
    """ Links accounts via an owner so that they share a data record.

    Accounts are linked based on a `link` parameter (which should be
    interpretable as a `LinkTuple`, which has `owner` and `token`
    attributes.) Accounts do not necessarily need to have access to the
    same `AccountLink` object to be linked - `AccountLink` merely
    provides an interface by which Accounts can get access to the
    centrally-managed data record.

    NOTE: This class is intended to provide immutable attributes, such
    as `owner` and `token`. Immutability is not programmatically
    enforced. Try not to get yourself in trouble.

    Args:
        link (LinkTuple): A `(owner, token)` tuple (or anything
            convertible to LinkTuple) that uniquely identifies a group
            of linked accounts.

            Most commonly of type `tuple[Person, str]`. The first
            element (owner) must have a `data` attribute. The second
            element (token) must be hashable.
        default_factory (Callable): A callable object (e.g. a lambda
            expression) which takes no arguments and returns an object
            of any type. Inspired by `defaultdict`'s `default_factory`
            argument. Optional.

            The returned object is used to initialize the shared data
            record when the link is first registered.
            Defaults to `dict`.

    Attributes:
        owner (Person, Any): An object that holds the data shared by
            the linked accounts.
        token (str, Hashable): A value registered with `owner` which is
            shared by all accounts in this link group with this owner.
        default_factory (Callable): A callable object (e.g. a lambda
            expression) which takes no arguments and returns an object
            of any type. Inspired by `defaultdict`'s `default_factory`
            argument. Optional.

            The returned object is used to initialize `data` when the
            link is first registered. Defaults to `dict`.
        data (Any): The centrally-managed data record shared by all
            linked accounts. Can be of any type, which is determined by
            `default_factory`. Defaults to an empty `dict`.
        group (set): The group of all accounts linked by this
            owner/token pair.
        _record (LinkRecord): A (data, group) tuple, exposed here for
            convenience in internal use.
    """
    def __init__(self, link, default_factory=None):
        """ Initializes `AccountLink`. """
        # Process inputs:
        if not isinstance(link, (AccountLink, LinkTuple)):
            # Try to cast unrecognized sequence types to `LinkTuple`
            if isinstance(link, abc.Sequence):
                link = LinkTuple(*link)
            else:
                raise TypeError('link must be convertible to a tuple')
        if default_factory is None and isinstance(link, AccountLink):
            # If we've passed in an `AccountLink`, copy its
            # default_factor (unless one's been explicitly passed in):
            default_factory = default_factory

        # Proceed with the usual init actions:
        # Store inputs:
        self.owner = link.owner
        self.token = link.token
        self.default_factory = default_factory

        # If this link is new, mutate `owner` as necessary:
        if not self.is_registered():
            self.register()

    @property
    def data(self):
        """ A shared record for a given link. """
        if self._record is not None:
            return self._record.data
        else:
            return None

    @property
    def group(self):
        """ The group of accounts linked by this AccountLink. """
        if self._record is not None:
            return self._record.group
        else:
            return None

    @property
    def _record(self):
        """ The LinkRecord shared by a group of linked accounts. """
        if self.is_registered():
            return self.owner.data[self.token]
        else:
            return None

    @_record.setter
    def _record(self, val):
        """ Sets _record. """
        # Raises KeyError if the link is not registered.
        self.owner.data[self.token] = val

    @_record.deleter
    def _record(self):
        """ Deletes _record. """
        # Raises KeyError if the link is not registered
        del self.owner.data[self.token]

    def is_registered(self):
        """ Returns whether the link has been registered with owner. """
        return self.token in self.owner.data

    def register(self):
        """ Sets up the shared data record for this `AccountLink`. """
        # If the link already exists, there's nothing to do:
        if self.is_registered():
            return
        # Otherwise, create the link. Use the init logic of
        # `LinkRecord`, except that if we have a `default_factory` use
        # that to init the `data` attribute.
        if self.default_factory is None:
            self._record = LinkRecord()
        else:
            self._record = LinkRecord(data=self.default_factory())

    def unregister(self):
        """ Deletes the shared data record for this `AccountLink`. """
        # If the link doesn't exist, there's nothing to do:
        if self.is_registered():
            return
        # Otherwise, remove the link by deleting its record from the
        # owner's data repository:
        del self._record

    def is_linked(self, account):
        """ Returns whether an account has been linked. """
        # pylint: disable=unsupported-membership-test
        # pylint gets confused by dataclass semantics; group is a set.
        return account in self._record.group

    def link_account(self, account):
        """ Links account to others linked by this `AccountLink`. """
        if not self.is_registered():
            raise KeyError('cannot add account to unregistered link')
        # Start tracking this account if we aren't already
        # pylint: disable=no-member
        # pylint gets confused by dataclass semantics; group is a set.
        self.group.add(account)

    def unlink_account(self, account):
        """ Unlinks account from others linked by this `AccountLink`. """
        # pylint: disable=no-member
        # pylint gets confused by dataclass semantics; group is a set.
        self.group.remove(account)

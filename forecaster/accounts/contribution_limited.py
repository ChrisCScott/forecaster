""" A module providing the ContributionLimitAccount class. """

from forecaster.accounts.base import Account
from forecaster.person import Person
from forecaster.ledger import Money

class ContributionLimitAccount(Account):
    """ An account with contribution limits.

    The contribution room limit may be shared between accounts. Such
    accounts should share a `contribution_token` value, which is
    registered with the `contributor` (the owner, by default).

    If contribution room is defined per-account, assign a unique
    contribution_token to the account (e.g. `id(self)`). By default,
    all objects of the same subclass share a contribution_token. This
    should be set by the subclass before invoking super().__init__.

    This is an abstract base class. Any subclass must implement the
    method `next_contribution_room`, which returns the contribution
    room for the following year.

    Attributes:
        contribution_room (Union[Money, None]): The amount of
            contribution room available in the current year.

            `None` if no contribution room has yet been recorded for
            this year.
        contributor (Union[Person, None]): The contributor to the
            account. By default, this is the owner.
    """

    def __init__(
            self, *args, contribution_room=None, contributor=None, **kwargs):
        """ Initializes a ContributionLimitAccount object.

        Args:
            contribution_room (Money): The amount of contribution room
                available in the first year. Optional.
            contributor (Person): The contributor to the account. Optional.
                If not provided, the contributor is assumed to be the same
                as the annuitant (i.e. the owner.)
        """
        super().__init__(*args, **kwargs)

        # If no contributor was provided, assume it's the owner.
        self._contributor = None
        if contributor is None:
            self.contributor = self.owner
        else:
            self.contributor = contributor

        # If `contribution_token` hasn't already been set, set
        # `contribution_token` to a value that's the same for
        # all instances of a subclass but differs between subclasses.
        # By default, we'll use the type name, but it could be anything.

        # We test for whether the member has been set before
        # accessing it, so this pylint error is not appropriate here.
        # pylint: disable=access-member-before-definition
        if not (
                hasattr(self, 'contribution_token')
                and self.contribution_token is not None):
            self.contribution_token = type(self).__name__
        # pylint: enable=access-member-before-definition

        # Prepare this account for having its contribution room tracked
        self.contributor.register_shared_contribution(self)
        # Contribution room is stored with the contributor and shared
        # between accounts. Accordingly, only set contribution room if
        # it's explicitly provided, to avoid overwriting previously-
        # determined contribution room data with a default value.
        if contribution_room is not None:
            self.contribution_room = contribution_room

    @property
    def contributor(self):
        """ The contributor to the account. """
        return self._contributor

    @contributor.setter
    def contributor(self, val):
        """ Sets the contributor to the account.

        Raises:
            TypeError: `person` must be of type `Person`.
        """
        if not isinstance(val, Person):
            raise TypeError(
                'RegisteredAccount: person must be of type Person.'
            )
        else:
            self._contributor = val

    @property
    def contribution_group(self):
        """ The accounts that share contribution room with this one. """
        return self.contributor.contribution_groups(self)

    @property
    def contribution_room(self):
        """ Contribution room available for the current year. """
        contribution_room_history = self.contributor.contribution_room(self)
        if self.this_year in contribution_room_history:
            return contribution_room_history[self.this_year]
        else:
            return None

    @contribution_room.setter
    def contribution_room(self, val):
        """ Updates contribution room for the current year. """
        self.contributor.contribution_room(self)[self.this_year] = Money(val)

    @property
    def contribution_room_history(self):
        """ A dict of `{year, contribution_room}` pairs. """
        return self.contributor.contribution_room(self)

    def next_year(self):
        """ Confirms that the year is within the range of our data. """
        # Calculate contribution room accrued based on this year's
        # transaction/etc. information
        if self.this_year + 1 not in self.contribution_room_history:
            contribution_room = self.next_contribution_room()
        # NOTE: Invoking super().next_year will increment self.this_year
        super().next_year()

        # Ensure that the contributor has advanced to this year.
        while self.contributor.this_year < self.this_year:
            self.contributor.next_year()

        # The contribution room we accrued last year becomes available
        # in the next year, so assign after calling `next_year`:
        if self.this_year not in self.contribution_room_history:
            self.contribution_room = contribution_room

    def next_contribution_room(self):
        """ Returns the contribution room for next year.

        This method must be implemented by any subclass of
        `RegisteredAccount`.

        Returns:
            Money: The contribution room for next year.

        Raises:
            NotImplementedError: Raised if this method is not overridden
            by a subclass.
        """
        raise NotImplementedError(
            'RegisteredAccount: next_contribution_room is not implemented. '
            + 'Subclasses must override this method.')

    @property
    def max_inflow_limit(self):
        """ Limits outflows based on contribution room for the year. """
        return self.contribution_room

""" A Canadian registered account.

These accounts come in various forms, but in general they have a
contributor and finite contribution room that grows from year to year.
"""

from forecaster.accounts import LinkedLimitAccount
from forecaster.ledger import recorded_property
from forecaster.utility import build_inflation_adjust

class RegisteredAccount(LinkedLimitAccount):
    """ An abstract base class for RRSPs, TFSAs, etc. """

    def __init__(
            self, owner, *args, contribution_room=None, contributor=None,
            inflation_adjust=None, max_inflow_token=None, **kwargs):
        """ Inits RegisteredAccount.

        See documentation for `Account` and `LinkedAccount`
        for information on any args not listed below.

        Args:
            owner (Person): The person who owns the account. Some types
                of accounts call this the "annuitant".

            contribution_room (Money): The amount of contribution room
                available in the first year. Optional.

                If not provided, this value will default to `None`,
                which makes it easier for subclasses to determine
                whether it has been set but, if those subclasses don't
                take care to set this manually, can lead to hard-to-
                diagnose errors in client code.

            contributor (Person): The contributor to the account.
                Optional.

                If not provided, the contributor is assumed to be the
                same as the annuitant (i.e. the owner.)

            inflation_adjust: A method with the following form:
                `inflation_adjust(val, this_year, target_year)`.

                Returns a Decimal object which is the inflation-
                adjustment factor from base_year to target_year.

                Optional. If not provided, all values are assumed to be
                in real terms, so no inflation adjustment is performed.

            max_inflow_token (str): A token that is used to link this
                account to any other accounts with the same token and
                contributor. Optional.

                If not provided then by default the max inflows of this
                account are linked with all other accounts of the same
                type having the same contributor.
        """

        # If not provided, we assume that the contributor is the owner:
        contributor_default = owner
        # To link this account to other accounts, we need to ensure that
        # they all share the same `max_inflow_link` (i.e. a contributor/
        # token pair). We'll use an explicitly-passed token if provided,
        # but in most cases we'll just link accounts with the same type.
        # Append ".max_inflow" to the type name so that we can decide
        # later to add different type-based tokens for "min_inflow"/etc.
        max_inflow_token_default = type(self).__name__ + ".max_inflow"

        # Avoid duplicate args to superclass init:
        max_inflow_link, max_inflow_limit = self._process_alias_args(
            contribution_room, contributor, max_inflow_token, kwargs,
            contributor_default=contributor_default,
            max_inflow_token_default=max_inflow_token_default)

        # Now pass the args and contructed token to the superclass:
        # (We don't store contributor separately, since it's represented
        # in max_inflow_link).
        super().__init__(
            *args, owner=owner, max_inflow_link=max_inflow_link,
            max_inflow_limit=max_inflow_limit, **kwargs)

        # There's only one new attribute that's not handled by the
        # superclass. Set it here:
        self.inflation_adjust = build_inflation_adjust(inflation_adjust)

    @property
    def contributor(self):
        """ The `Person` authorized to contribute to this account. """
        return self.max_inflow_link.owner

    @contributor.setter
    def contributor(self, val):
        """ Sets the `contributor` property. """
        self.max_inflow_link.owner = val

    @recorded_property
    def contribution_room(self):
        """ Contribution room available for the current year. """
        # Wraps `max_inflow_limit`
        return self.max_inflow_limit

    @contribution_room.setter
    def contribution_room(self, val):
        """ Sets contribution_room. """
        # Wraps `max_inflow_limit`
        self.max_inflow_limit = val

    def next_year(self):
        """ Confirms that the year is within the range of our data. """
        # If this is the first of the linked accounts to get advanced,
        # determine next_contribution_room, advance all the linked
        # accounts' to the next year (and also the contributor, if
        # necessary), and then assign the new contribution_room.
        # We do it like this to ensure that each linked account has
        # a chance to record the previous year's contribution room
        # before it's updated.

        # Is this the first account in the linked group to be advanced?
        first_account = all(
            account.this_year == self.this_year
            for account in self.max_inflow_link.group)
        # Only call next_contribution_room once for the whole group
        # per year. We do this in the first account to be called.
        if first_account:
            # If the contribution room for next year is already known
            # (e.g. via an `input` dict), use that:
            # pylint: disable=no-member
            # Pylint gets confused by attributes added by metaclass
            next_year = self.this_year + 1
            if next_year in self.contribution_room_history:
                contribution_room = self.contribution_room_history[next_year]
            else:
                # Otherwise, generate it using the magic method:
                contribution_room = self.next_contribution_room()

        # Advance this account's year first, _then_ the other linked
        # accounts (so that they each know they aren't `first_account`)
        super().next_year()

        # Ensure that all linked accounts have advanced to this year
        # to ensure they remain in sync:
        for account in self.max_inflow_link.group:
            while account.this_year < self.this_year:
                account.next_year()
        # Ensure that the contributor has also advanced to this year
        # (do this after advancing the linked accounts!)
        while self.contributor.this_year < self.this_year:
            self.contributor.next_year()

        # Now assign the contribution room we determined earlier to
        # the linked data store:
        if first_account:
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

    def _process_alias_args(
            self, contribution_room, contributor, max_inflow_token, kwargs,
            contributor_default=None, max_inflow_token_default=None):
        """ Processes args. which alias superclass args.

        Aliasing args run the risk of the same argument being passed
        twice to the superclass `__init__` method. To avoid this,
        perform checks to confirm which have been passed and transform
        any superclass-named args into something recognized by
        RegisteredAccount.

        This method mutates `kwargs` to remove any aliased arguments.
        (Don't worry - values for those arguments are returned by this
        method as well.)

        Returns:
            tuple[Any, Any]: A `(max_inflow_link, max_inflow_limit)`
                tuple.

        Raises:
            ValueError: Both an aliasing RegisteredAccount arg (e.g.
            `contribution_room`) and the LinkedLimitAccount arg it
            aliases (e.g. `max_inflow_limit`) were passed explicitly.
        """
        # We need to pass`max_inflow_limit` to the superclass init.
        # This can be provided in two ways: a RegisteredAccount-specific
        # arg (i.e. `contribution_room`) or native `LinkedLimitAccount`
        # arg names. Calling code may pass at most one of these!
        if contribution_room is not None and 'max_inflow_limit' in kwargs:
            # If both are provided, raise an error:
            raise ValueError(
                'cannot pass both `contribution_room` and '
                + '`max_inflow_limit explicitly')
        elif 'max_inflow_limit' in kwargs:
            # If they passed the LinkedLimitAccount version, map it to
            # the RegisteredAccount name for convenience.
            # (Also remove this element of `kwargs` to avoid duplicate
            # arguments being passed)
            max_inflow_limit = kwargs.pop('max_inflow_limit')
        else:
            # Only contribution_room was provided, so map it to the
            # superclass argument it aliases:
            max_inflow_limit = contribution_room

        # Similarly, we need to pass `max_inflow_link`; `contributor`
        # and `max_inflow_token` (in combination) alias this, so ensure
        # that both are not provided explicitly.
        if (
                (contributor is not None or max_inflow_token is not None)
                and 'max_inflow_link' in kwargs):
            raise ValueError(
                'cannot pass `max_inflow_link` explicitly if either '
                + '`contributor` or `max_inflow_token` are provided.')
        elif 'max_inflow_link' in kwargs:
            # If the native LinkedLimitAccount arg was passed,
            # use that directly (to avoid stripping out any additional
            # information it holds with its attributes):
            # (Also remove this element of `kwargs` to avoid duplicate
            # arguments being passed)
            max_inflow_link = kwargs.pop('max_inflow_link')
        else:
            # max_inflow_link was not provided, so we need to build it.

            # If not provided, use the default value for contributor:
            if contributor is None:
                contributor = contributor_default
            # Same for max_inflow_token:
            if max_inflow_token is None:
                max_inflow_token = max_inflow_token_default
            # Build max_inflow_link via `contributor`/`max_inflow_token`
            max_inflow_link = (contributor, max_inflow_token)

        return (max_inflow_link, max_inflow_limit)

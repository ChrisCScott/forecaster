""" TODO """

import unittest
import decimal
from decimal import Decimal
from forecaster import (
    Person, ContributionLimitAccount, Money)
from tests.test_accounts.test_base import TestAccountMethods

class TestContributionLimitAccountMethods(TestAccountMethods):
    """ Tests ContributionLimitAccount. """

    def setUp(self):
        """ Sets up variables for testing ContributionLimitAccount """
        super().setUp()

        self.AccountType = ContributionLimitAccount
        self.contribution_room = 0

    def test_init_basic(self, *args, **kwargs):
        """ Test ContributionLimitAccount.__init__ """
        super().test_init_basic(
            *args, contribution_room=self.contribution_room, **kwargs)

        # Basic init using pre-built ContributionLimitAccount-specific args
        # and default Account args
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.contribution_room, self.contribution_room)

    def test_init_contributor_implicit(self, *args, **kwargs):
        """ Test implicit initialization of contributor parameter. """
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.contributor, self.owner)

    def test_init_contributor_explicit(self, *args, **kwargs):
        """ Test explicit initialization of contributor parameter. """
        contributor = Person(
            self.initial_year, "Name", "1 January 2000",
            retirement_date="1 January 2020")
        account = self.AccountType(
            self.owner, *args, contributor=contributor, **kwargs)
        self.assertEqual(account.contributor, contributor)

    def test_contribution_room(self, *args, **kwargs):
        """ Test explicit initialization of contribution_room. """
        account = self.AccountType(
            self.owner, *args, contribution_room=Money(100), **kwargs)
        self.assertEqual(account.contribution_room, Money(100))

    def test_init_invalid(self, *args, **kwargs):
        """ Test ContributionLimitAccount.__init__ with invalid inputs. """
        super().test_init_invalid(
            *args, contribution_room=self.contribution_room, **kwargs)

        # Test invalid `person` input
        with self.assertRaises(TypeError):
            self.AccountType(
                self.owner, contributor='invalid person',
                *args, **kwargs)

        # Finally, test a non-Money-convertible contribution_room:
        with self.assertRaises(decimal.InvalidOperation):
            self.AccountType(
                self.owner, *args,
                contribution_room='invalid', **kwargs)

    def test_properties(self, *args, **kwargs):
        """ Test ContributionLimitAccount properties """
        # Basic check: properties return scalars (current year's values)
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contribution_room,
                         self.contribution_room)

        # NOTE: ContributionLimitAccount.next_year() raises NotImplementedError
        # and some subclasses require args for next_year(). That is
        # already dealt with by test_next, so check that properties are
        # pointing to the current year's values after calling next_year
        # in text_next.

    def test_next_year(self, *args, **kwargs):
        """ Test ContributionLimitAccount.next_year. """
        # next_contribution_room is not implemented for
        # ContributionLimitAccount, and it's required for next_year, so confirm
        # that trying to call next_year() throws an appropriate error.
        if self.AccountType == ContributionLimitAccount:
            account = ContributionLimitAccount(self.owner)
            with self.assertRaises(NotImplementedError):
                account.next_year()
        # For other account types, try a conventional next_year test
        else:
            super().test_next_year(
                *args, **kwargs)

    def test_returns(self, *args, **kwargs):
        """ Test ContributionLimitAccount.returns. """
        # super().test_returns calls next_year(), which calls
        # next_contribution_room(), which is not implemented for
        # ContributionLimitAccount. Don't test returns for this class,
        # and instead allow subclasses to pass through.
        if self.AccountType != ContributionLimitAccount:
            super().test_returns(*args, **kwargs)

    def test_max_inflow(self, *args, **kwargs):
        """ Test ContributionLimitAccount.max_inflow. """
        # Init an account with standard parameters, confirm that
        # max_inflow corresponds to contribution_room.
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.max_inflow(), self.contribution_room)

    def test_contribution_room_basic(self, *args, **kwargs):
        """ Test sharing of contribution room between accounts. """
        account1 = self.AccountType(
            self.owner, *args,
            contribution_room=Money(100), **kwargs)
        self.assertEqual(account1.contribution_room, Money(100))

        # Don't set contribution_room explicitly for account2; it should
        # automatically match account1's contribution_room amount.
        account2 = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account2.contribution_room, Money(100))

    def test_contribution_room_update(self, *args, **kwargs):
        """ Test updating contribution room via second account's init. """
        account1 = self.AccountType(
            self.owner, *args,
            contribution_room=Money(100), **kwargs)
        self.assertEqual(account1.contribution_room, Money(100))

        # Set contribution_room explicitly for account2; it should
        # override account1's contribution_room amount.
        account2 = self.AccountType(
            self.owner, *args,
            contribution_room=Money(200), **kwargs)
        self.assertEqual(account1.contribution_room, Money(200))
        self.assertEqual(account2.contribution_room, Money(200))

    def test_contribution_group_basic(self, *args, **kwargs):
        """ Test that contribution_group is set properly for 1 account. """
        account = self.AccountType(
            self.owner, *args,
            contribution_room=Money(100), **kwargs)
        self.assertEqual(account.contribution_group, {account})

    def test_contribution_group_mult(self, *args, **kwargs):
        """ Test that contribution_group is set properly for 2 accounts. """
        account1 = self.AccountType(
            self.owner, *args,
            contribution_room=Money(100), **kwargs)
        account2 = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account1.contribution_group, {account1, account2})
        self.assertEqual(account2.contribution_group, {account1, account2})

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

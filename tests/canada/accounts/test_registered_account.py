""" Unit tests for RegisteredAccount. """

import unittest
import inspect
import decimal
from decimal import Decimal
from random import Random
from forecaster.canada import RegisteredAccount
from tests.accounts.test_linked_limit import TestLinkedLimitAccountMethods

class TestRegisteredAccountMethods(TestLinkedLimitAccountMethods):
    """ Test RegisteredAccount. """

    def setUp(self):
        """ Sets up variables for testing RegisteredAccount. """
        super().setUp()

        self.AccountType = RegisteredAccount

        # Randomly generate inflation adjustments based on inflation
        # rates of 1%-20%. Add a few extra years on to the end for
        # testing purposes.
        self.inflation_adjustments = {self.initial_year: 1}

        def inflation_adjust(target_year, base_year):
            """ Inflation from base_year to target_year """
            return (
                self.inflation_adjustments[target_year] /
                self.inflation_adjustments[base_year]
            )
        self.inflation_adjust = inflation_adjust

        # Use a convenient default for contribution room:
        self.contribution_room = 0

    def setUp_decimal(self):
        """ Sets up variables based on Decimal inputs. """
        super().setUp_decimal()

        self.AccountType = RegisteredAccount

        # Randomly generate inflation adjustments based on inflation
        # rates of 1%-20%. Add a few extra years on to the end for
        # testing purposes.
        self.inflation_adjustments = {self.initial_year: 1}

        def inflation_adjust(target_year, base_year):
            """ Inflation from base_year to target_year """
            return (
                self.inflation_adjustments[target_year] /
                self.inflation_adjustments[base_year]
            )
        self.inflation_adjust = inflation_adjust

        # Use a convenient default for contribution room:
        self.contribution_room = 0

    def set_initial_year(self, initial_year):
        """ Sets initial_year for all relevant objects. """
        self.initial_year = initial_year
        self._set_initial_year_ledger(self.owner, initial_year)
        for account in self.owner.accounts:
            self._set_initial_year_ledger(account, initial_year)

    @staticmethod
    def _set_initial_year_ledger(ledger, initial_year):
        """ Updates `initial_year` for a `Ledger` object.

        This involves updating the various `\\*_history` dicts that
        store values for each recorded property.
        """
        for _, prop in inspect.getmembers(
                type(ledger), lambda x: hasattr(x, 'history_property')):
            history_dict = getattr(ledger, prop.history_dict_name)
            if ledger.initial_year in history_dict:
                history_dict[initial_year] = history_dict[ledger.initial_year]
                history_dict.pop(ledger.initial_year)
        ledger.initial_year = initial_year
        ledger.this_year = initial_year

    def extend_inflation_adjustments(
            self, min_year, max_year, *, high_precision=None):
        """ Convenience method for extending inflation adjustments.

        Ensures self.inflation_adjustment spans min_year and max_year.
        """
        rand = Random()

        # Extend inflation_adjustments backwards, assuming 1-20% inflation
        i = min(self.inflation_adjustments)
        while i > min_year:
            self.inflation_adjustments[i - 1] = (
                self.inflation_adjustments[i] / (1 + rand.randint(1, 20) / 100))
            i -= 1

        # Extend inflation_adjustments forwards, assuming 1-20% inflation
        i = max(self.inflation_adjustments)
        while i < max_year:
            self.inflation_adjustments[i + 1] = (
                self.inflation_adjustments[i] * (1 + rand.randint(1, 20) / 100))
            i += 1

        # Support high-precision numerical types:
        if high_precision is not None:
            self.inflation_adjustments = {
                key: Decimal(val)
                for (key, val) in self.inflation_adjustments.items()}

    def test_init_basic(self, *args, **kwargs):
        """ Basic init tests for RegisteredAccount. """
        super().test_init_basic(*args, **kwargs)

        # The only thing that RegisteredAccount.__init__ does is set
        # inflation_adjust, so test that:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.inflation_adjust, self.inflation_adjust)

    def test_init_invalid_infl_adj(self, *args, **kwargs):
        """ Test calling __init__ with invalid inflation_adjustment. """
        # First, pass in a non-dict
        with self.assertRaises(TypeError):
            self.AccountType(
                self.owner, *args,
                inflation_adjust='invalid',
                contribution_room=self.contribution_room, **kwargs)

    # The following tests all call next_year(), which calls
    # next_contribution_room(), which is not implemented for
    # this class and certain subclasses. Don't run these tests for this
    # class. Instead, allow subclasses to pass through.

    def test_next(self, *args, **kwargs):
        """ Test LinkedLimitAccount.next_year. """
        # next_contribution_room is not implemented for
        # LinkedLimitAccount, and it's required for next_year, so confirm
        # that trying to call next_year() throws an appropriate error.
        if self.AccountType == RegisteredAccount:
            account = RegisteredAccount(self.owner)
            with self.assertRaises(NotImplementedError):
                account.next_year()
        # For other account types, try a conventional next_year test
        else:
            try:
                super().test_next(
                    *args, **kwargs)
            except NotImplementedError:
                return  # this error is OK

    def test_returns(self, *args, **kwargs):
        """ Test LinkedLimitAccount.returns. """
        try:
            super().test_returns(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_returns_next_year(self, *args, **kwargs):
        """ Test LinkedLimitAccount.returns after calling next_year. """
        try:
            super().test_returns_next_year(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_next_no_growth(self, *args, **kwargs):
        """ Tests next_year with no growth. """
        try:
            super().test_next_no_growth(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_next_cont_growth(self, *args, **kwargs):
        """ Tests next_year with continuous growth. """
        try:
            super().test_next_cont_growth(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_next_disc_growth(self, *args, **kwargs):
        """ Tests next_year with discrete (monthly) growth. """
        try:
            super().test_next_disc_growth(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_next_basic_trans(self, *args, **kwargs):
        """ Tests next_year with a mid-year transaction. """
        try:
            super().test_next_basic_trans(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_next_no_growth_trans(self, *args, **kwargs):
        """ Tests next_year with no growth and a transaction. """
        try:
            super().test_next_no_growth_trans(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_next_cont_growth_trans(self, *args, **kwargs):
        """ Tests next_year with continuous growth and transaction. """
        try:
            super().test_next_cont_growth_trans(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_next_disc_growth_trans(self, *args, **kwargs):
        """ Tests next_year with discrete growth and a transaction. """
        try:
            super().test_next_disc_growth_trans(*args, **kwargs)
        except NotImplementedError:
            return  # this error is OK

    def test_max_inflows_pos(self, *args, **kwargs):
        """ Test max_inflows with positive balance """
        # This method should always return the current contribution room
        account = self.AccountType(
            self.owner, *args, balance=100, contribution_room=0, **kwargs)
        result = account.max_inflows(self.timing)
        for value in result.values():
            self.assertEqual(value, 0)

    def test_max_inflows_neg(self, *args, **kwargs):
        """ Test max_inflows with negative balance """
        # This method should always return the current contribution room
        account = self.AccountType(
            self.owner, *args, balance=-100, contribution_room=0, **kwargs)
        result = account.max_inflows(self.timing)
        for value in result.values():
            self.assertEqual(value, 0)

    def test_decimal_continuous(self, *args, **kwargs):
        """ Test RegisteredAccount with Decimal inputs. """
        # Convert values to Decimal:
        self.setUp_decimal()
        # super().test_decimal calls `account.next_contribution_room`,
        # which raises a NotImplementedError.
        # Let subclasses pass through to the super-class's test,
        # otherwise fail over to a test that doesn't have this problem:
        try:
            super().test_decimal_continuous(*args, **kwargs)
        except NotImplementedError:
            # If next_contribution_room isn't implemented, use a
            # different rest (this one is based on test_max_inflows_pos)

            # This method should always return the current contribution room
            account = self.AccountType(
                self.owner, *args, balance=Decimal(100),
                contribution_room=Decimal(0), high_precision=Decimal,
                **kwargs)
            result = account.max_inflows(self.timing)
            for value in result.values():
                self.assertEqual(value, Decimal(0))

    def test_decimal_discrete(self, *args, **kwargs):
        """ Test RegisteredAccount with Decimal inputs. """
        # Convert values to Decimal:
        self.setUp_decimal()
        # super().test_decimal calls `account.next_contribution_room`,
        # which raises a NotImplementedError.
        # Let subclasses pass through to the super-class's test,
        # otherwise fail over to a test that doesn't have this problem:
        try:
            super().test_decimal_discrete(*args, **kwargs)
        except NotImplementedError:
            # If next_contribution_room isn't implemented, use a
            # different rest (this one is based on test_max_inflows_neg)

            # This method should always return the current contribution room
            account = self.AccountType(
                self.owner, *args, balance=Decimal(-100),
                contribution_room=Decimal(0), high_precision=Decimal,
                **kwargs)
            result = account.max_inflows(self.timing)
            for value in result.values():
                self.assertEqual(value, Decimal(0))

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

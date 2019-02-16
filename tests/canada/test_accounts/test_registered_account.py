""" TODO """

import unittest
import inspect
import decimal
from decimal import Decimal
from random import Random
from forecaster import Money
from forecaster.canada import RegisteredAccount
from tests.test_accounts.test_contribution_limited import (
    TestContributionLimitAccountMethods)

class TestRegisteredAccountMethods(TestContributionLimitAccountMethods):
    """ Test RegisteredAccount. """

    def setUp(self):
        """ Sets up variables for testing RegisteredAccount. """
        super().setUp()

        self.AccountType = RegisteredAccount

        # Randomly generate inflation adjustments based on inflation
        # rates of 1%-20%. Add a few extra years on to the end for
        # testing purposes.
        self.inflation_adjustments = {self.initial_year: Decimal(1)}

        def inflation_adjust(target_year, base_year):
            """ Inflation from base_year to target_year """
            return (
                self.inflation_adjustments[target_year] /
                self.inflation_adjustments[base_year]
            )
        self.inflation_adjust = inflation_adjust

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

    def extend_inflation_adjustments(self, min_year, max_year):
        """ Convenience method for extending inflation adjustments.

        Ensures self.inflation_adjustment spans min_year and max_year.
        """
        rand = Random()

        # Extend inflation_adjustments backwards, assuming 1-20% inflation
        i = min(self.inflation_adjustments)
        while i > min_year:
            self.inflation_adjustments[i - 1] = (
                self.inflation_adjustments[i] /
                Decimal(1 + rand.randint(1, 20) / 100)
            )
            i -= 1

        # Extend inflation_adjustments forwards, assuming 1-20% inflation
        i = max(self.inflation_adjustments)
        while i < max_year:
            self.inflation_adjustments[i + 1] = (
                self.inflation_adjustments[i] *
                Decimal(1 + rand.randint(1, 20) / 100)
            )
            i += 1

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

    def test_init_type_conversion(self, *args, **kwargs):
        """ Test type conversion of __init__ inputs. """
        super().test_init_type_conversion(*args, **kwargs)

        # Try type conversion for inflation_adjustments
        inflation_adjustments = {
            '2000': '1',
            2001.0: 1.25,
            Decimal(2002): 1.5,
            2003: Decimal('1.75'),
            2017.0: Decimal(2.0)
        }

        account = self.AccountType(
            self.owner, *args,
            contribution_room=500, inflation_adjust=inflation_adjustments,
            **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.contribution_room, Money('500'))
        self.assertEqual(account.inflation_adjust(2000), Decimal(1))
        self.assertEqual(account.inflation_adjust(2001), Decimal(1.25))
        self.assertEqual(account.inflation_adjust(2002), Decimal(1.5))
        self.assertEqual(account.inflation_adjust(2003), Decimal(1.75))
        self.assertEqual(account.inflation_adjust(2017), Decimal(2))

    def test_init_invalid(self, *args, **kwargs):
        """ Test calling __init__ with invalid inputs. """
        super().test_init_invalid(*args, **kwargs)
        # Try invalid inflation_adjustments.
        # First, pass in a non-dict
        with self.assertRaises(TypeError):
            self.AccountType(
                self.owner, *args,
                inflation_adjust='invalid',
                contribution_room=self.contribution_room, **kwargs)


if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

""" Tests for forecaster.canada.PrincipleResidence. """

import unittest
import decimal
from forecaster import Money
from forecaster.canada import PrincipleResidence
from tests.test_accounts.test_base import TestAccountMethods

class TestPrincipleResidenceMethods(TestAccountMethods):
    """ Test PrincipleResidence. """

    def setUp(self):
        super().setUp()
        self.AccountType = PrincipleResidence

    def test_taxable_income(self, *args, **kwargs):
        """ Test PrincipleResidence.taxable_income. """
        account = self.AccountType(
            self.owner, *args, balance=1000, rate=1, nper=1)
        self.assertEqual(account.taxable_income, Money(0))
        # Now let the residence appreciate 100% (to $2000) and then sell
        # the home (i.e. withdraw $2000):
        account.next_year()
        account.add_transaction(-2000)
        self.assertEqual(account.taxable_income, Money(0))

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

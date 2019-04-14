""" Unit tests for LinkedLimitAccount. """

import unittest
import decimal
from forecaster import (LinkedLimitAccount, Money)
from tests.test_accounts.test_base import TestAccountMethods

class TestLinkedLimitAccountMethods(TestAccountMethods):
    """ Tests LinkedLimitAccount. """

    def setUp(self):
        """ Sets up variables for testing LinkedLimitAccount """
        super().setUp()

        self.AccountType = LinkedLimitAccount
        self.link = (self.owner, "test")
        self.max_inflow_limit = Money(10)
        self.min_inflow_limit = Money(10)
        self.max_outflow_limit = Money(-10)
        self.min_outflow_limit = Money(-10)

    def test_init_max_inflow(self, *args, **kwargs):
        """ Test LinkedLimitAccount.__init__ for max_inflow. """
        # Basic init using pre-built LinkedLimitAccount-specific args
        # and default Account args
        account = self.AccountType(
            self.owner, *args,
            max_inflow_link=self.link,
            max_inflow_limit=self.max_inflow_limit,
            **kwargs)
        self.assertEqual(account.max_inflow_link.owner, self.owner)
        self.assertEqual(account.max_inflow_limit, self.max_inflow_limit)

    def test_init_min_inflow(self, *args, **kwargs):
        """ Test LinkedLimitAccount.__init__ for min_inflow. """
        # Basic init using pre-built LinkedLimitAccount-specific args
        # and default Account args
        account = self.AccountType(
            self.owner, *args,
            min_inflow_link=self.link,
            min_inflow_limit=self.min_inflow_limit,
            **kwargs)
        self.assertEqual(account.min_inflow_link.owner, self.owner)
        self.assertEqual(account.min_inflow_limit, self.min_inflow_limit)

    def test_init_max_outflow(self, *args, **kwargs):
        """ Test LinkedLimitAccount.__init__ for max_outflow. """
        # Basic init using pre-built LinkedLimitAccount-specific args
        # and default Account args
        account = self.AccountType(
            self.owner, *args,
            max_outflow_link=self.link,
            max_outflow_limit=self.max_outflow_limit,
            **kwargs)
        self.assertEqual(account.max_outflow_link.owner, self.owner)
        self.assertEqual(account.max_outflow_limit, self.max_outflow_limit)

    def test_init_min_outflow(self, *args, **kwargs):
        """ Test LinkedLimitAccount.__init__ for min_outflow. """
        # Basic init using pre-built LinkedLimitAccount-specific args
        # and default Account args
        account = self.AccountType(
            self.owner, *args,
            min_outflow_link=self.link,
            min_outflow_limit=self.min_outflow_limit,
            **kwargs)
        self.assertEqual(account.min_outflow_link.owner, self.owner)
        self.assertEqual(account.min_outflow_limit, self.min_outflow_limit)

    def test_max_inflow_limit_basic(self, *args, **kwargs):
        """ Test sharing of max_inflow_limit between accounts. """
        # Init a first account with a link and set a $100 limit:
        account1 = self.AccountType(
            self.owner, *args,
            max_inflow_link=self.link,
            max_inflow_limit=Money(100), **kwargs)
        # Init a second account without an explicit max_inflow_limit
        # but with the same link as account1.
        account2 = self.AccountType(
            self.owner, *args, max_inflow_link=self.link, **kwargs)
        # account2's should max_inflow_limit should match account1's.
        self.assertEqual(
            account2.max_inflow_limit,
            account1.max_inflow_limit)

    def test_max_inflow_limit_update(self, *args, **kwargs):
        """ Test updating max_inflow_limit via second account's init. """
        # Init a first account with a link and set a $100 limit:
        account1 = self.AccountType(
            self.owner, *args,
            max_inflow_link=self.link,
            max_inflow_limit=Money(100), **kwargs)
        # Init a second account with a different max_inflow_limit and
        # the same link as account1.
        account2 = self.AccountType(
            self.owner, *args,
            max_inflow_link=self.link,
            max_inflow_limit=Money(200), **kwargs)
        # Both accounts should use the new $200 limit:
        self.assertEqual(account1.max_inflow_limit, Money(200))
        self.assertEqual(account2.max_inflow_limit, Money(200))


if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

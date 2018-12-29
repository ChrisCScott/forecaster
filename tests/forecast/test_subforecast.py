""" Unit tests for `SubForecast`. """

import unittest
from collections import defaultdict
from decimal import Decimal
from forecaster import (
    Money, Person, Account, SubForecast)


class TestSubForecast(unittest.TestCase):
    """ Tests Suborecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.subforecast = SubForecast()
        self.person = Person(
            initial_year = 2000, name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 2045")
        # A basic account with 100% interest and no compounding:
        self.account1 = Account(
            owner=self.person, balance=100, rate=Decimal(1), nper=1)
        # Another account, same as account1:
        self.account2 = Account(
            owner=self.person, balance=100, rate=Decimal(1), nper=1)
        # Add an alias for the subforecast's available dict
        # for convenience:
        self.available = self.subforecast.available

    def test_add_transaction_basic(self):
        """ Moves $100 from available to an account. """
        # Given $100 in cash, put it all in account1:
        self.available[Decimal(0)] = Money(100)
        self.subforecast.add_transaction(
            value=Money(100), when='start',
            from_account=self.available, to_account=self.account2)
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0): Money(-100)})

    def test_add_transaction_delay(self):
        """ Moves $100 from available to an account. """
        # Try to move $100 in cash to account1 at the start of the year,
        # when cash isn't actually available until mid-year:
        self.available[Decimal(0.5)] = Money(100)
        self.subforecast.add_transaction(
            value=Money(100), when='start',
            from_account=self.available, to_account=self.account2)
        # Transaction should be delayed until mid-year:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0.5): Money(-100)})

    def test_add_transaction_delay_acct(self):
        """ Moves $100 from available to an account. """
        # Try to move $100 in cash to account1 at the start of the year,
        # when cash isn't actually available until mid-year:
        self.available[Decimal(0.5)] = Money(100)
        self.subforecast.add_transaction(
            value=Money(100), when='start',
            from_account=self.available, to_account=self.account2)
        # Transaction should be delayed until mid-year:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0.5): Money(-100)})

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromTestCase(TestSubForecast))

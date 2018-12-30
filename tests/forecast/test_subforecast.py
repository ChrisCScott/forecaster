""" Unit tests for `SubForecast`. """

import unittest
from collections import defaultdict
from decimal import Decimal
from forecaster import (
    Money, Person, Account, SubForecast)


class TestSubForecast(unittest.TestCase):
    """ Tests Subforecast. """

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
        self.available_acct = Account(initial_year = 2000, rate = 0)

    def test_add_transaction_basic(self):
        """ Moves $100 from available to an account. """
        # Receive cash at start of year:
        self.available[Decimal(0)] = Money(100)
        # Move all $100 to account1 right away:
        self.subforecast.add_transaction(
            value=100, when='start',
            from_account=self.available, to_account=self.account1)
        # Since we're transferring from available, this transaction
        # should be recorded (at the start time):
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0): Money(-100)})
        # The $100 inflow at the start time should be reduced to $0:
        self.assertEqual(
            self.available[Decimal(0)],
            Money(0))
        # A $100 transaction should be added to the account:
        self.assertEqual(
            self.account1[Decimal(0)],
            Money(100))

    def test_add_transaction_basic_acct(self):
        """ Moves $100 from available to an account. """
        # Receive cash at start of year:
        self.available_acct.add_transaction(value=100, when='start')
        # The subforecast should be using the account for tracking:
        self.subforecast.available = self.available_acct

        # Move all $100 to account1 right away:
        self.subforecast.add_transaction(
            value=100, when='start',
            from_account=self.subforecast.available,
            to_account=self.account2)
        # Transaction should be added immediately:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0): Money(-100)})
        # No more money should be available:
        self.assertEqual(
            self.subforecast.available[Decimal(0)],
            Money(0))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0)],
            Money(100))

    def test_add_transaction_acct_transfer(self):
        """ Moves $100 from one account to another. """
        # Receive cash at start of year:
        self.account1[Decimal(0)] = Money(100)
        # Move $100 from account1 to account2 right away:
        self.subforecast.add_transaction(
            value=100, when='start',
            from_account=self.account1, to_account=self.account2)
        # The $100 inflow at the start time should be reduced to $0:
        self.assertEqual(
            self.account1[Decimal(0)],
            Money(0))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0)],
            Money(100))

    def test_add_transaction_delay(self):
        """ Transaction that should be shifted to later time. """
        # Try to move $100 in cash to account1 at the start of the year,
        # when cash isn't actually available until mid-year:
        self.available[Decimal(0.5)] = Money(100)
        self.subforecast.add_transaction(
            value=100, when='start',
            from_account=self.available, to_account=self.account2)
        # Transaction should be delayed until mid-year:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0.5): Money(-100)})
        # No more money should be available:
        self.assertEqual(
            self.subforecast.available[Decimal(0.5)],
            Money(0))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0.5)],
            Money(100))

    def test_add_transaction_delay_acct(self):
        """ Transaction that should be shifted to later time. """
        # Receive cash mid-year:
        self.available_acct.add_transaction(value=100, when=0.5)
        # The subforecast should be using the account for tracking:
        self.subforecast.available = self.available_acct

        # Try to move $100 in cash to account1 at the start of the year
        # (i.e. before cash is actually on-hand):
        self.subforecast.add_transaction(
            value=100, when='start',
            from_account=self.available_acct, to_account=self.account2)
        # Transaction should be delayed until mid-year:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0.5): Money(-100)})
        # No more money should be available:
        self.assertEqual(
            self.available_acct[Decimal(0.5)],
            Money(0))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0.5)],
            Money(100))

    def test_add_transaction_small_inflow(self):
        """ Multiple small inflows and one large outflow. """
        # Receive $100 spread across 2 transactions:
        self.available[Decimal(0)] = Money(50)
        self.available[Decimal(0.5)] = Money(50)

        # Move $100 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=100, when=0.5,
            from_account=self.available, to_account=self.account2)
        # Transaction should occur on-time:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0.5): Money(-100)})
        # Check net transaction flows of available cash:
        self.assertEqual(
            (self.available[Decimal(0)], self.available[Decimal(0.5)]),
            (Money(50), Money(-50)))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0.5)],
            Money(100))

    def test_add_transaction_future_shortfall(self):
        """ Transaction that would cause future negative balance. """
        # Want to have $100 available at when=0.5 and at when=1,
        # but with >$100 in-between:
        self.available[Decimal(0)] = Money(50)
        self.available[Decimal(0.5)] = Money(50)
        self.available[Decimal(0.75)] = Money(-50)
        self.available[Decimal(1)] = Money(50)

        # Try to move $100 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=100, when=0.5,
            from_account=self.available, to_account=self.account2)
        # Transaction should be delayed to year-end:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(1): Money(-100)})
        # Check that `available` gets the transaction too, with same timing:
        self.assertEqual(
            self.available[Decimal(1)],
            Money(-50))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(1)],
            Money(100))

    def test_add_transaction_acct_growth(self):
        """ Account growth allows outflow after insufficient inflows. """
        # Receive $100 at the start. It will grow to $150 by mid-year:
        self.account1[Decimal(0)] = Money(100)
        # Move $150 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=150, when=0.5,
            from_account=self.account1, to_account=self.account2)
        # Check net transaction flows of available cash:
        self.assertEqual(
            (self.account1[Decimal(0)], self.account1[Decimal(0.5)]),
            (Money(100), Money(-150)))
        # A $150 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0.5)],
            Money(150))

    def test_add_transaction_acct_growth_btwn(self):
        """ Account growth allows outflow between inflows. """
        # Receive $100 at the start. It will grow to $150 by mid-year:
        self.account1[Decimal(0)] = Money(100)
        # Add another inflow at the end. This shouldn't change anything:
        self.account1[Decimal(1)] = Money(100)
        # Move $150 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=150, when=0.5,
            from_account=self.account1, to_account=self.account2)
        # Check net transaction flows of available cash:
        self.assertEqual(
            (self.account1[Decimal(0)], self.account1[Decimal(0.5)]),
            (Money(100), Money(-150)))
        # A $150 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0.5)],
            Money(150))

    def test_add_transaction_shortfall(self):
        """ Transaction that must cause a negative balance. """
        # Want to withdraw $100 when this amount will not be available
        # at any point in time:
        self.available[Decimal(0)] = Money(50)
        self.available[Decimal(1)] = Money(49)

        # Try to move $100 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=100, when=0.5,
            from_account=self.available, to_account=self.account2)
        # Transaction should occur immediately:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0.5): Money(-100)})
        # Check that `available` gets the transaction too, with same timing:
        self.assertEqual(
            self.available[Decimal(0.5)],
            Money(-100))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0.5)],
            Money(100))

    def test_add_transaction_shortfall_acct(self):
        """ Transaction that must cause a negative balance. """
        self.subforecast.available = self.available_acct
        # Want to withdraw $100 when this amount will not be available
        # at any point in time:
        self.available_acct[Decimal(0)] = Money(50)
        self.available_acct[Decimal(1)] = Money(49)

        # Try to move $100 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=100, when=0.5,
            from_account=self.available_acct, to_account=self.account2)
        # Transaction should occur immediately:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0.5): Money(-100)})
        # Check that `available` gets the transaction too, with same timing:
        self.assertEqual(
            self.available_acct[Decimal(0.5)],
            Money(-100))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0.5)],
            Money(100))

    def test_add_transaction_strict(self):
        """ Add transaction with strict timing. """
        # Move $100 in cash to account1 at the start of the year.
        # Cash isn't actually available until mid-year, but use strict
        # timing to force it through:
        self.available[Decimal(0.5)] = Money(100)
        self.subforecast.add_transaction(
            value=100, when='start',
            from_account=self.available, to_account=self.account2,
            strict_timing=True)
        # Transaction should done at the time requested:
        self.assertEqual(
            self.subforecast.transactions,
            {Decimal(0): Money(-100)})
        # Negative money should be available at the start:
        self.assertEqual(
            self.subforecast.available[Decimal(0)],
            Money(-100))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2[Decimal(0)],
            Money(100))

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromTestCase(TestSubForecast))

""" Unit tests for `SubForecast`. """

import unittest
from collections import defaultdict
from decimal import Decimal
from forecaster import (
    Person, Account, SubForecast, Timing)
from forecaster.forecast.subforecast import TransactionDict


class TestTransactionDict(unittest.TestCase):
    """ Tests TransactionDict """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.dict = TransactionDict()

    def test_setitem_unhashable(self):
        """ Add a dict as a key. """
        # This shouldn't raise an exception:
        obj = {}
        self.dict[obj] = 0

    def test_getitem_unhashable(self):
        """ Gets a value using a dict as a key. """
        obj = {}
        self.dict[obj] = 0
        self.assertEqual(self.dict[obj], 0)

    def test_iter_unhashable(self):
        """ Iterates over dict with unhashable keys. """
        obj = {}
        self.dict[obj] = 0
        # The sole key in the dict should be `d` - not a copy,
        # but d itself:
        for key in self.dict:
            self.assertIs(key, obj)

    def test_keys_unhashable(self):
        """ View keys for dict with unhashable keys. """
        obj = {}
        self.dict[obj] = 0
        # The sole key in the dict should be `d` - not a copy,
        # but d itself:
        for key in self.dict.keys():
            self.assertIs(key, obj)

class TestSubForecast(unittest.TestCase):
    """ Tests Subforecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        self.subforecast = SubForecast(self.initial_year)
        self.person = Person(
            initial_year=self.initial_year,
            name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 2045")
        # A basic account with 100% interest and no compounding:
        self.account1 = Account(
            owner=self.person, balance=100, rate=Decimal(1), nper=1)
        # Another account, same as account1:
        self.account2 = Account(
            owner=self.person, balance=100, rate=Decimal(1), nper=1)
        # Set up a dict and Account for use as `available`:
        self.available_dict = defaultdict(lambda: Decimal(0))
        self.available_acct = Account(initial_year=self.initial_year, rate=0)

    def test_transaction_basic(self):
        """ Tests that transactions are saved correctly. """
        # Receive cash at start of year:
        self.available_dict[Decimal(0)] = Decimal(100)
        # Move all $100 to account1 right away:
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=self.available_dict, to_account=self.account1)
        # Transactions should be recorded against both available_dict
        # and account1:
        self.assertEqual(
            self.subforecast.transactions[self.available_dict],
            {Decimal(0): Decimal(-100)})
        self.assertEqual(
            self.subforecast.transactions[self.account1],
            {Decimal(0): Decimal(100)})

    def test_transaction_delay(self):
        """ Tests that delayed transactions are saved correctly. """
        # Receive cash mid-year:
        self.available_acct.add_transaction(value=100, when=0.5)

        # Try to move $100 in cash to account1 at the start of the year
        # (i.e. before cash is actually on-hand):
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=self.available_acct, to_account=self.account2)
        result = self.subforecast.transactions
        target = {
            self.available_acct: {Decimal(0.5): Decimal(-100)},
            self.account2: {Decimal(0.5): Decimal(100)}}
        # Transaction should be delayed until mid-year:
        self.assertEqual(result, target)

    def test_transaction_none(self):
        """ Tests that transactions against None are saved correctly. """
        # Move $100 in cash (which comes from the untracked pool None)
        # to account2 at the start of the year:
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=None, to_account=self.account2)
        # Transactions should be recorded against both:
        self.assertEqual(
            self.subforecast.transactions,
            {
                None: {Decimal(0): Decimal(-100)},
                self.account2: {Decimal(0): Decimal(100)}
            })

    def test_add_trans_basic(self):
        """ Moves $100 from available to an account. """
        # Receive cash at start of year:
        self.available_dict[Decimal(0)] = Decimal(100)
        # Move all $100 to account1 right away:
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=self.available_dict, to_account=self.account1)
        # The $100 inflow at the start time should be reduced to $0:
        self.assertEqual(
            self.available_dict[Decimal(0)],
            Decimal(0))
        # A $100 transaction should be added to the account:
        self.assertEqual(
            self.account1.transactions[Decimal(0)],
            Decimal(100))

    def test_add_trans_basic_acct(self):
        """ Moves $100 from available to an account. """
        # Receive cash at start of year:
        self.available_acct.add_transaction(value=100, when='start')

        # Move all $100 to account1 right away:
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=self.available_acct,
            to_account=self.account2)
        # No more money should be available:
        self.assertEqual(
            self.available_acct.transactions[Decimal(0)],
            Decimal(0))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0)],
            Decimal(100))

    def test_add_trans_tnsfr_acct(self):
        """ Moves $100 from one account to another. """
        # Receive cash at start of year:
        self.account1.transactions[Decimal(0)] = Decimal(100)
        # Move $100 from account1 to account2 right away:
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=self.account1, to_account=self.account2)
        # The $100 inflow at the start time should be reduced to $0:
        self.assertEqual(
            self.account1.transactions[Decimal(0)],
            Decimal(0))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0)],
            Decimal(100))

    def test_add_trans_delay(self):
        """ Transaction that should be shifted to later time. """
        # Try to move $100 in cash to account1 at the start of the year,
        # when cash isn't actually available until mid-year:
        self.available_dict[Decimal(0.5)] = Decimal(100)
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=self.available_dict, to_account=self.account2)
        # Transaction should be recorded against existing transaction
        # at timing=0.5, resulting in no net transaction:
        self.assertEqual(
            self.available_dict[Decimal(0.5)],
            Decimal(0))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0.5)],
            Decimal(100))

    def test_add_trans_delay_acct(self):
        """ Transaction that should be shifted to later time. """
        # Receive cash mid-year:
        self.available_acct.add_transaction(value=100, when=0.5)

        # Try to move $100 in cash to account1 at the start of the year
        # (i.e. before cash is actually on-hand):
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=self.available_acct, to_account=self.account2)
        # Transactions should be delayed until mid-year:
        self.assertEqual(
            self.available_acct.transactions[Decimal(0.5)],
            Decimal(0))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0.5)],
            Decimal(100))

    def test_add_trans_small_in(self):
        """ Multiple small inflows and one large outflow. """
        # Receive $100 spread across 2 transactions:
        self.available_dict[Decimal(0)] = Decimal(50)
        self.available_dict[Decimal(0.5)] = Decimal(50)

        # Move $100 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=100, timing=0.5,
            from_account=self.available_dict, to_account=self.account2)
        # Transaction should occur on-time:
        self.assertEqual(
            (
                self.available_dict[Decimal(0)],
                self.available_dict[Decimal(0.5)]),
            (Decimal(50), Decimal(-50)))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0.5)],
            Decimal(100))

    def test_add_trans_future_neg(self):
        """ Transaction that would cause future negative balance. """
        # Want to have $100 available at timing=0.5 and at timing=1,
        # but with >$100 in-between:
        self.available_dict[Decimal(0)] = Decimal(50)
        self.available_dict[Decimal(0.5)] = Decimal(50)
        self.available_dict[Decimal(0.75)] = Decimal(-50)
        self.available_dict[Decimal(1)] = Decimal(50)

        # Try to move $100 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=100, timing=0.5,
            from_account=self.available_dict, to_account=self.account2)
        # Transaction should be delayed to year-end:
        self.assertEqual(
            self.available_dict[Decimal(1)],
            Decimal(-50))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(1)],
            Decimal(100))

    def test_add_trans_acct_growth(self):
        """ Account growth allows outflow after insufficient inflows. """
        # Receive $100 at the start. It will grow to $150 by mid-year:
        self.account1.transactions[Decimal(0)] = Decimal(100)
        # Move $150 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=150, timing=0.5,
            from_account=self.account1, to_account=self.account2)
        # Check net transaction flows of available cash:
        self.assertEqual(
            (self.account1.transactions[Decimal(0)], self.account1.transactions[Decimal(0.5)]),
            (Decimal(100), Decimal(-150)))
        # A $150 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0.5)],
            Decimal(150))

    def test_add_trans_acct_growth_btwn(self):
        """ Account growth allows outflow between inflows. """
        # Receive $100 at the start. It will grow to $150 by mid-year:
        self.account1.transactions[Decimal(0)] = Decimal(100)
        # Add another inflow at the end. This shouldn't change anything:
        self.account1.transactions[Decimal(1)] = Decimal(100)
        # Move $150 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=150, timing=0.5,
            from_account=self.account1, to_account=self.account2)
        # Check net transaction flows of available cash:
        self.assertEqual(
            (
                self.account1.transactions[Decimal(0)],
                self.account1.transactions[Decimal(0.5)]),
            (Decimal(100), Decimal(-150)))
        # A $150 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0.5)],
            Decimal(150))

    def test_add_trans_shortfall(self):
        """ Transaction that must cause a negative balance. """
        # Want to withdraw $100 when this amount will not be available
        # at any point in time:
        self.available_dict[Decimal(0)] = Decimal(50)
        self.available_dict[Decimal(1)] = Decimal(49)

        # Try to move $100 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=100, timing=0.5,
            from_account=self.available_dict, to_account=self.account2)
        # Transaction should occur immediately:
        self.assertEqual(
            self.available_dict[Decimal(0.5)],
            Decimal(-100))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0.5)],
            Decimal(100))

    def test_add_trans_shortfall_acct(self):
        """ Transaction that must cause a negative balance. """
        # Want to withdraw $100 when this amount will not be available
        # at any point in time:
        self.available_acct.transactions[Decimal(0)] = Decimal(50)
        self.available_acct.transactions[Decimal(1)] = Decimal(49)

        # Try to move $100 in cash to account2 at mid-year:
        self.subforecast.add_transaction(
            value=100, timing=0.5,
            from_account=self.available_acct, to_account=self.account2)
        # Transaction should occur immediately:
        self.assertEqual(
            self.available_acct.transactions[Decimal(0.5)],
            Decimal(-100))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0.5)],
            Decimal(100))

    def test_add_trans_strict(self):
        """ Add transaction with strict timing. """
        # Move $100 in cash to account1 at the start of the year.
        # Cash isn't actually available until mid-year, but use strict
        # timing to force it through:
        self.available_dict[Decimal(0.5)] = Decimal(100)
        self.subforecast.add_transaction(
            value=100, timing='start',
            from_account=self.available_dict, to_account=self.account2,
            strict_timing=True)
        # Transaction should done at the time requested:
        self.assertEqual(
            self.available_dict[Decimal(0)],
            Decimal(-100))
        # A $100 transaction should be added to account2:
        self.assertEqual(
            self.account2.transactions[Decimal(0)],
            Decimal(100))

    def test_add_trans_timing_basic(self):
        """ Add a number of transactions based on a Timing object. """
        # Add $50 at when=0.5 and $50 at when=1
        timing = Timing(when=1, frequency=2)
        self.subforecast.add_transaction(
            value=100, timing=timing,
            to_account=self.available_dict)
        # Confirm monies were added at the times noted above:
        self.assertEqual(
            self.available_dict,
            {Decimal(0.5): Decimal(50), Decimal(1): Decimal(50)})

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

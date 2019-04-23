""" Unit tests for `TransactionStrategy`. """

import unittest
from decimal import Decimal
from forecaster import (
    Person, Money, TransactionStrategy, Debt, TransactionNode, LimitTuple)
from forecaster.canada import RRSP, TFSA, TaxableAccount


class TestTransactionStrategyMethods(unittest.TestCase):
    """ A test case for non-strategy method of TransactionStrategy. """

    def setUp(self):
        """ Sets up variables for testing. """
        self.initial_year = 2000
        self.person = Person(
            self.initial_year, "Test", "1 January 1980",
            retirement_date="1 January 2030")
        # An RRSP with a $1000 balance and $100 in contribution room:
        self.rrsp = RRSP(
            initial_year=self.initial_year,
            owner=self.person,
            balance=Money(1000),
            contribution_room=Money(100))
        # A TFSA with a $100 balance and $1000 in contribution room:
        self.tfsa = TFSA(
            initial_year=self.initial_year,
            owner=self.person,
            balance=Money(100),
            contribution_room=Money(1000))
        # A taxable account with $0 balance (and no contribution limit)
        self.taxable_account = TaxableAccount(
            initial_year=self.initial_year,
            owner=self.person,
            balance=Money(0))
        # A $100 debt with no interest and a $10 min. payment:
        self.debt = Debt(
            initial_year=self.initial_year,
            owner=self.person,
            balance=Money(100),
            minimum_payment=Money(10))
        # Contribute to RRSP, then TFSA, then taxable
        self.priority_ordered = [self.rrsp, self.tfsa, self.taxable_account]
        # Contribute 50% to RRSP, 25% to TFSA, and 25% to taxable
        self.priority_weighted = {
            self.rrsp: Decimal(0.5),
            self.tfsa: Decimal(0.25),
            self.taxable_account: Decimal(0.25)}
        # Contribute to RRSP and TFSA (50-50) until both are full, with
        # the remainder to taxable accounts.
        self.priority_nested = [
            {
                self.rrsp: Decimal(0.5),
                self.tfsa: Decimal(0.5)},
            self.taxable_account]

    def test_init_basic(self):
        """ Test __init__ with explicit arguments. """
        strategy = TransactionStrategy(priority=self.priority_ordered)
        self.assertEqual(strategy.priority, self.priority_ordered)

    def test_ordered_basic(self):
        """ Contribute to the first account of an ordered list. """
        # Contribute $100 to RRSP, then TFSA, then taxable.
        strategy = TransactionStrategy(priority=self.priority_ordered)
        available = {Decimal(0.5): Money(100)}
        transactions = strategy(available)
        # $100 will go to RRSP, $0 to TFSA, $0 to taxable:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(100))
        # The taxable account doesn't need to be explicitly represented,
        # but if it is then it should be $0:
        if self.tfsa in transactions:
            self.assertAlmostEqual(
                sum(transactions[self.tfsa].values()), Money(0))
        if self.taxable_account in transactions:
            self.assertAlmostEqual(
                sum(transactions[self.taxable_account].values()),
                Money(0))

    def test_weighted_basic(self):
        """ Contribute to each account proportionate to its weight. """
        # Contribute $100 to the accounts.
        strategy = TransactionStrategy(priority=self.priority_weighted)
        available = {Decimal(0.5): Money(100)}
        transactions = strategy(available)
        # $50 will go to RRSP, $25 to TFSA, $25 to taxable:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(50))
        self.assertAlmostEqual(
            sum(transactions[self.tfsa].values()), Money(25))
        self.assertAlmostEqual(
            sum(transactions[self.taxable_account].values()),
            Money(25))

    def test_nested_basic(self):
        """ Test with weighted dict nested in ordered list. """
        # Contribute $100 to the accounts.
        strategy = TransactionStrategy(priority=self.priority_nested)
        available = {Decimal(0.5): Money(100)}
        transactions = strategy(available)
        # $50 will go to RRSP, $50 to TFSA, $0 to taxable:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(50))
        self.assertAlmostEqual(
            sum(transactions[self.tfsa].values()), Money(50))
        if self.taxable_account in transactions:
            self.assertAlmostEqual(
                sum(transactions[self.taxable_account].values()),
                Money(0))

    def test_ordered_overflow_partial(self):
        """ Contribute to first and second accounts of an ordered list. """
        # Contribute $200 to RRSP, then TFSA, then taxable.
        strategy = TransactionStrategy(priority=self.priority_ordered)
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $100 will go to RRSP, $100 to TFSA, $0 to taxable:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(100))
        self.assertAlmostEqual(
            sum(transactions[self.tfsa].values()), Money(100))
        # The taxable account doesn't need to be explicitly represented,
        # but if it is then it should be $0:
        if self.taxable_account in transactions:
            self.assertAlmostEqual(
                sum(transactions[self.taxable_account].values()),
                Money(0))

    def test_weighted_overflow_partial(self):
        """ Max out one weighted account, contribute overflow to others. """
        # Contribute $400 to the accounts.
        strategy = TransactionStrategy(priority=self.priority_weighted)
        available = {Decimal(0.5): Money(400)}
        transactions = strategy(available)
        # $100 will go to RRSP (maxed), $150 to TFSA, $150 to taxable:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(100))
        self.assertAlmostEqual(
            sum(transactions[self.tfsa].values()), Money(150))
        self.assertAlmostEqual(
            sum(transactions[self.taxable_account].values()),
            Money(150))

    def test_nested_overflow_partial(self):
        """ Max out one nested account, contribute overflow to neighbor. """
        # Contribute $400 to the accounts.
        strategy = TransactionStrategy(priority=self.priority_nested)
        available = {Decimal(0.5): Money(400)}
        transactions = strategy(available)
        # $100 will go to RRSP (maxed), $300 to TFSA, $0 to taxable:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(100))
        self.assertAlmostEqual(
            sum(transactions[self.tfsa].values()), Money(300))
        if self.taxable_account in transactions:
            self.assertAlmostEqual(
                sum(transactions[self.taxable_account].values()),
                Money(0))

    def test_contribution_group_ordered(self):
        """ Contribute to ordered accounts sharing contribution room. """
        # Set up a second RRSP with $0 balance, owned by the same person
        # as `self.rrsp` (and thus sharing contribution room):
        rrsp2 = RRSP(initial_year=self.initial_year, owner=self.person)
        priority = [self.rrsp, rrsp2, self.taxable_account]
        strategy = TransactionStrategy(priority=priority)
        # Contribute $200 to the accounts:
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $100 will go to self.rrsp, $0 to rrsp2, and $100 to taxable:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(100))
        if rrsp2 in transactions:
            # No further transactions to rrsp2 because all contribution
            # room is consumed by transactions to self.rrsp
            self.assertAlmostEqual(sum(transactions[rrsp2].values()), Money(0))
        self.assertAlmostEqual(
            sum(transactions[self.taxable_account].values()), Money(100))

    def test_contribution_group_weight(self):
        """ Contribute to weighted accounts sharing contribution room. """
        # Set up a second RRSP with $0 balance, owned by the same person
        # as `self.rrsp` (and thus sharing contribution room):
        rrsp2 = RRSP(initial_year=self.initial_year, owner=self.person)
        priority = [
            {self.rrsp: Decimal(0.5), rrsp2: Decimal(0.5)},
            self.taxable_account]
        strategy = TransactionStrategy(priority=priority)
        # Contribute $200 to the accounts:
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $50 will go to self.rrsp, $50 to rrsp2, and $100 to taxable:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(50))
        self.assertAlmostEqual(
            sum(transactions[rrsp2].values()), Money(50))
        self.assertAlmostEqual(
            sum(transactions[self.taxable_account].values()), Money(100))

    def test_limit_ordered(self):
        """ Limit contributions according to per-node limits. """
        # Limit debt contributions to $100
        # (rather than $1000 max. contribution)
        limits = LimitTuple(max_inflow=Money(100))
        limit_node = TransactionNode(self.debt, limits=limits)
        priority = [self.rrsp, limit_node, self.taxable_account]
        strategy = TransactionStrategy(priority=priority)
        # Contribute $300 to the accounts:
        available = {Decimal(0.5): Money(300)}
        transactions = strategy(available)
        # $100 will go to each account:
        self.assertAlmostEqual(
            sum(transactions[self.rrsp].values()), Money(100))
        self.assertAlmostEqual(
            sum(transactions[self.debt].values()), Money(100))
        self.assertAlmostEqual(
            sum(transactions[self.taxable_account].values()), Money(100))

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

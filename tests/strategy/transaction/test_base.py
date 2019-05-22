""" Unit tests for `TransactionStrategy`. """

import unittest
from decimal import Decimal
from forecaster import (
    Person, Money, TransactionTraversal, Debt, TransactionNode, LimitTuple)
from forecaster.canada import RRSP, TFSA, TaxableAccount
from tests.util import TestCaseTransactions


class TestTransactionTraversalMethods(TestCaseTransactions):
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
        # Another RRSP, linked to the first one:
        # (For testing LinkedLimitAccount nodes)
        self.rrsp2 = RRSP(
            initial_year=self.initial_year,
            owner=self.person)
        # A TFSA with a $100 balance and $1000 in contribution room:
        self.tfsa = TFSA(
            initial_year=self.initial_year,
            owner=self.person,
            balance=Money(100),
            contribution_room=Money(1000))
        # Another TFSA, linked to the first one:
        self.tfsa2 = TFSA(
            initial_year=self.initial_year,
            owner=self.person)
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
        strategy = TransactionTraversal(priority=self.priority_ordered)
        self.assertEqual(strategy.priority, self.priority_ordered)

    def test_call_basic(self):
        """ Test __call__ with a one-node priority tree. """
        strategy = TransactionTraversal(priority=self.taxable_account)
        available = {Decimal(0.5): Money(100)}
        transactions = strategy(available)
        # All $100 will go to the single account:
        self.assertTransactions(transactions[self.taxable_account], Money(100))

    def test_ordered_basic(self):
        """ Contribute to the first account of an ordered list. """
        # Contribute $100 to RRSP, then TFSA, then taxable.
        strategy = TransactionTraversal(priority=self.priority_ordered)
        available = {Decimal(0.5): Money(100)}
        transactions = strategy(available)
        # $100 will go to RRSP, $0 to TFSA, $0 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        if self.tfsa in transactions:
            self.assertTransactions(transactions[self.tfsa], Money(0))
        if self.taxable_account in transactions:
            self.assertTransactions(
                transactions[self.taxable_account], Money(0))

    def test_weighted_basic(self):
        """ Contribute to each account proportionate to its weight. """
        # Contribute $100 to the accounts.
        strategy = TransactionTraversal(priority=self.priority_weighted)
        available = {Decimal(0.5): Money(100)}
        transactions = strategy(available)
        # $50 will go to RRSP, $25 to TFSA, $25 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(50))
        self.assertTransactions(transactions[self.tfsa], Money(25))
        self.assertTransactions(transactions[self.taxable_account], Money(25))

    def test_nested_basic(self):
        """ Test with weighted dict nested in ordered list. """
        # Contribute $100 to the accounts.
        strategy = TransactionTraversal(priority=self.priority_nested)
        available = {Decimal(0.5): Money(100)}
        transactions = strategy(available)
        # $50 will go to RRSP, $50 to TFSA, $0 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(50))
        self.assertTransactions(transactions[self.tfsa], Money(50))
        if self.taxable_account in transactions:
            self.assertTransactions(
                transactions[self.taxable_account], Money(0))

    def test_ordered_overflow_partial(self):
        """ Contribute to first and second accounts of an ordered list. """
        # Contribute $200 to RRSP, then TFSA, then taxable.
        strategy = TransactionTraversal(priority=self.priority_ordered)
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $100 will go to RRSP, $100 to TFSA, $0 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        self.assertTransactions(transactions[self.tfsa], Money(100))
        if self.taxable_account in transactions:
            self.assertTransactions(
                transactions[self.taxable_account], Money(0))

    def test_weighted_overflow_partial(self):
        """ Max out one weighted account, contribute overflow to others. """
        # Contribute $400 to the accounts.
        strategy = TransactionTraversal(priority=self.priority_weighted)
        available = {Decimal(0.5): Money(400)}
        transactions = strategy(available)
        # $100 will go to RRSP (maxed), $150 to TFSA, $150 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        self.assertTransactions(transactions[self.tfsa], Money(150))
        self.assertTransactions(transactions[self.taxable_account], Money(150))

    def test_nested_overflow_partial(self):
        """ Max out one nested account, contribute overflow to neighbor. """
        # Contribute $400 to the accounts.
        strategy = TransactionTraversal(priority=self.priority_nested)
        available = {Decimal(0.5): Money(400)}
        transactions = strategy(available)
        # $100 will go to RRSP (maxed), $300 to TFSA, $0 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        self.assertTransactions(transactions[self.tfsa], Money(300))
        if self.taxable_account in transactions:
            self.assertTransactions(
                transactions[self.taxable_account], Money(0))

    def test_link_group_ordered(self):
        """ Contribute to ordered accounts sharing max inflow limit. """
        priority = [self.rrsp, self.rrsp2, self.taxable_account]
        strategy = TransactionTraversal(priority=priority)
        # Contribute $200 to the accounts:
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $100 will go to self.rrsp, $0 to rrsp2, and $100 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        if self.rrsp2 in transactions:
            self.assertTransactions(transactions[self.rrsp2], Money(0))
        self.assertTransactions(transactions[self.taxable_account], Money(100))

    def test_link_weight(self):
        """ Contribute to weighted accounts sharing max inflow limit. """
        priority = [
            {self.rrsp: Decimal(0.5), self.rrsp2: Decimal(0.5)},
            self.taxable_account]
        strategy = TransactionTraversal(priority=priority)
        # Contribute $200 to the accounts:
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $50 will go to self.rrsp, $50 to rrsp2, and $100 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(50))
        self.assertTransactions(transactions[self.rrsp2], Money(50))
        self.assertTransactions(transactions[self.taxable_account], Money(100))

    def test_limit_ordered(self):
        """ Limit contributions with per-node limit in ordered tree. """
        # Limit debt contributions to $100
        # (rather than $1000 max. contribution)
        limits = LimitTuple(max_inflow=Money(100))
        limit_node = TransactionNode(self.debt, limits=limits)
        priority = [self.rrsp, limit_node, self.taxable_account]
        strategy = TransactionTraversal(priority=priority)
        # Contribute $300 to the accounts:
        available = {Decimal(0.5): Money(300)}
        transactions = strategy(available)
        # $100 will go to each account:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        self.assertTransactions(transactions[self.debt], Money(100))
        self.assertTransactions(transactions[self.taxable_account], Money(100))

    def test_limit_weighted(self):
        """ Limit contributions with per-node limit in weighted tree. """
        # Limit debt contributions to $100
        # (rather than $1000 max. contribution)
        limits = LimitTuple(max_inflow=Money(100))
        limit_node = TransactionNode(self.debt, limits=limits)
        priority = {
            self.rrsp: Decimal(1),
            limit_node: Decimal(1),
            self.taxable_account: Decimal(1)}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $400 to the accounts:
        available = {Decimal(0.5): Money(400)}
        transactions = strategy(available)
        # $100 will go to debt and RRSP and $200 taxable:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        self.assertTransactions(transactions[self.debt], Money(100))
        self.assertTransactions(transactions[self.taxable_account], Money(200))

    def test_limit_weight_link_1_small(self):
        """ Linked account with limit in weighted tree; small inflow. """
        # This test looks at this structure:
        #       {}
        #      /| \
        #     / |  \
        #    R1 R2  A
        # R1/R2 are a group with a shared limit of $100.
        # _R1_ has a per-node limit of $10. All nodes have equal weight.
        # This should result in any contributions over the limit being
        # redistributed to R2 and A (up to the linked group limit, in
        # the case of R2).
        limits = LimitTuple(max_inflow=Money(10))
        limit_node = TransactionNode(self.rrsp, limits=limits)
        priority = {
            limit_node: Decimal(1),
            self.rrsp2: Decimal(1),
            self.taxable_account: Decimal(1)}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $110 to the accounts:
        available = {Decimal(0.5): Money(110)}
        transactions = strategy(available)
        # $10 will go to rrsp and $100 will be split equally between
        # the two other accounts, for a total of $50 each:
        self.assertTransactions(transactions[self.rrsp], Money(10))
        self.assertTransactions(transactions[self.rrsp2], Money(50))
        self.assertTransactions(transactions[self.taxable_account], Money(50))

    def test_limit_weight_link_1_large(self):
        """ Linked account with limit in weighted tree; large inflow. """
        # This test looks at the same structure as
        # `test_limit_weighted_link_small`, except that enough money
        # is contributed to hit the group limit for R2 (as well as the
        # per-node limit for R1)
        limits = LimitTuple(max_inflow=Money(10))
        limit_node = TransactionNode(self.rrsp, limits=limits)
        priority = {
            limit_node: Decimal(1),
            self.rrsp2: Decimal(1),
            self.taxable_account: Decimal(1)}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $210 to the accounts:
        available = {Decimal(0.5): Money(210)}
        transactions = strategy(available)
        # $10 will go to rrsp and $200 will be split between the two
        # other accounts - i.e. $90 to rrsp2 and $110 to taxable
        # (because rrsp/rrsp2 share a $100 limit):
        self.assertTransactions(transactions[self.rrsp], Money(10))
        self.assertTransactions(transactions[self.rrsp2], Money(90))
        self.assertTransactions(transactions[self.taxable_account], Money(110))

    def test_limit_weight_link_2_small(self):
        """ Limit in weighted tree with linked accounts; small inflow. """
        # This test looks at this structure:
        #       {}
        #      /| \
        #     / |  \
        #    R1 R2  A
        # R1/R2 are a group. _A_ has a per-node limit.
        # This should result in any contributions over the limit being
        # redistributed to R1 and R2 (up to the linked group limit).
        limits = LimitTuple(max_inflow=Money(10))
        limit_node = TransactionNode(self.taxable_account, limits=limits)
        priority = {
            self.rrsp: Decimal(1),
            self.rrsp2: Decimal(1),
            limit_node: Decimal(1)}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $60 to the accounts:
        available = {Decimal(0.5): Money(60)}
        transactions = strategy(available)
        # $10 will go to taxable and $50 will be split between the two
        # linked accounts - i.e. $25 to each of rrsp and rrsp2:
        self.assertTransactions(transactions[self.rrsp], Money(25))
        self.assertTransactions(transactions[self.rrsp2], Money(25))
        self.assertTransactions(transactions[self.taxable_account], Money(10))

    def test_limit_weight_link_2_large(self):
        """ Limit in weighted tree with linked accounts; large inflow. """
        # This test looks at the same structure as
        # `test_limit_weight_link_2_small`, except that enough money
        # is contributed to hit the group limit for R1/R2
        limits = LimitTuple(max_inflow=Money(10))
        limit_node = TransactionNode(self.taxable_account, limits=limits)
        priority = {
            self.rrsp: Decimal(1),
            self.rrsp2: Decimal(1),
            limit_node: Decimal(1)}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $300 to the accounts:
        available = {Decimal(0.5): Money(300)}
        transactions = strategy(available)
        # $10 will go to taxable and $50 go to each of rrsp and rrsp2:
        # (This is less than the full $300 because the various accounts
        # hit their limits at $110 of inflows)
        self.assertTransactions(transactions[self.rrsp], Money(50))
        self.assertTransactions(transactions[self.rrsp2], Money(50))
        self.assertTransactions(transactions[self.taxable_account], Money(10))

    def test_link_basic(self):
        """ A weighted root with two linked children. """
        # This test looks at this structure:
        #       {}
        #      /  \
        #     /    \
        #    R1     R2
        # R1/R2 are a group. Trying to contribute more than the group
        # allows should result in only the total contribution room
        # being contributed across both accounts.
        priority = {self.rrsp: Decimal(0.5), self.rrsp2: Decimal(0.5)}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $200 (i.e. more than the joint contribution room
        # of the two RRSPs, which is $100):
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $50 should go to each account:
        self.assertTransactions(transactions[self.rrsp], Money(50))
        self.assertTransactions(transactions[self.rrsp2], Money(50))

    def test_link_overflow(self):
        """ A weighted root with two linked children and one other. """
        # This test looks at this structure:
        #       {}
        #      / |\
        #     /  | \
        #    R1 R2  T
        # If R1/R2 are a group (and R1 and R2 have equal weights) then
        # contributing more than the group can receive will send the
        # overflow to T.
        priority = {self.rrsp: 1, self.rrsp2: 1, self.taxable_account: 1}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $200:
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $50 should go to each RRSP, with remaining $100 to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(50))
        self.assertTransactions(transactions[self.rrsp2], Money(50))
        self.assertTransactions(transactions[self.taxable_account], Money(100))

    def test_link_order_equal(self):
        """ Two linked groups, each under both children of the root. """
        # This test looks at this structure:
        #       {}
        # (50%)/  \(50%)
        #     /    \
        #   []      []
        #  /  \    /  \
        # R1  T2  T1  R2
        # If R1/R2 and T1/T2 are groups with equal contribution room,
        # R2 and T2 shouldn't ever get a contribution.
        priority = {
            (self.rrsp, self.tfsa2): 1,
            (self.tfsa, self.rrsp2): 1}
        # Ensure RRSP and TFSA have equal contribution room:
        self.tfsa.contribution_room = self.rrsp.contribution_room
        strategy = TransactionTraversal(priority=priority)
        # Contribute $200 (enough to fill both groups):
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $100 should go to each of rrsp and tfsa (which are 1st on each
        # side of the root node), with no more going to rrsp2 or tfsa2:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        self.assertTransactions(transactions[self.tfsa], Money(100))
        self.assertTransactions(transactions[self.rrsp2], Money(0))
        self.assertTransactions(transactions[self.tfsa2], Money(0))

    def test_link_order_unequal(self):
        """ Two linked groups, each under both children of the root. """
        # This test looks at this structure:
        #       {}
        # (50%)/  \(50%)
        #     /    \
        #   []      []
        #  /  \    /  \
        # R1  T2  T1  R2
        # If R1/R2 and T1/T2 are groups with unequal contribution room
        # (WLOG, say R1 > T1), then R2 will get additional contributions
        priority = {
            (self.rrsp, self.tfsa2): 1,
            (self.tfsa, self.rrsp2): 1}
        # Ensure RRSP has more contribution room than TFSA:
        self.tfsa.contribution_room = Money(50)
        strategy = TransactionTraversal(priority=priority)
        # Contribute $150 (enough to fill both groups):
        available = {Decimal(0.5): Money(150)}
        transactions = strategy(available)
        # $75 should go to rrsp, $50 to tfsa, and $25 to rrsp2:
        self.assertTransactions(transactions[self.rrsp], Money(75))
        self.assertTransactions(transactions[self.tfsa], Money(50))
        self.assertTransactions(transactions[self.rrsp2], Money(25))
        if self.tfsa2 in transactions:
            self.assertTransactions(transactions[self.tfsa2], Money(0))

    def test_link_weighted_nested(self):
        """ A weighted root with weighted children with common groups. """
        # This test looks at this structure:
        #       {}
        # (50%)/  \(50%)
        #     /    \
        #   {}      {}
        #  /  \    /  \
        # R1  T2  T1  R2
        # If R1/R2 and T1/T2 are groups and all links are equal-weighted
        # then all accounts will get equal contributions (up to each
        # group's contribution limit)
        left_child = TransactionNode({self.rrsp: 1, self.tfsa2: 1})
        right_child = TransactionNode({self.tfsa: 1, self.rrsp2: 1})
        # Need to wrap nested dicts, since they aren't hashable.
        priority = {left_child: 1, right_child: 1}
        # Ensure RRSP has more contribution room than TFSA:
        self.tfsa.contribution_room = self.rrsp.contribution_room
        strategy = TransactionTraversal(priority=priority)
        # Contribute $200 (enough to fill both groups):
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $50 should go to each account:
        self.assertTransactions(transactions[self.rrsp], Money(50))
        self.assertTransactions(transactions[self.tfsa], Money(50))
        self.assertTransactions(transactions[self.rrsp2], Money(50))
        self.assertTransactions(transactions[self.tfsa2], Money(50))

    def test_link_nested_basic(self):
        """ A weighted root with weighted children with common groups. """
        # This test looks at this structure:
        #       {}
        # (50%)/  \(50%)
        #     /    \
        #   R1      []
        #          /  \
        #         R2   T
        # If R1/R2 is a group then contributing slightly more than their
        # shared contribution room could have two possible reasonable
        # results:
        # 1) R1 and R2 are contributed to equally, with the excess to T.
        # 2) R1 receives more than R2 so that both children of the root
        #    are balanced, with the excess to T.
        # The current implementation opts for #1, so test for that:
        priority = {
            self.rrsp: Decimal(1),
            (self.rrsp2, self.taxable_account): Decimal(1)}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $200 (enough to fill RRSPs with $100 left over):
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $50 should go to each RRSP, with balance to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(50))
        self.assertTransactions(transactions[self.rrsp2], Money(50))
        self.assertTransactions(transactions[self.taxable_account], Money(100))

    def test_link_nested_hidden(self):
        """ A weighted root with weighted children with common groups. """
        # This test looks at this structure:
        #       {}
        # (50%)/  \(50%)
        #     /    \
        #   R1      []
        #          /  \
        #         T    R2
        # If R1/R2 is a group then contributing slightly more than their
        # shared contribution room should result in R1 receiving all
        # of the group's contribution room, with the rest to T:
        priority = {
            self.rrsp: Decimal(1),
            (self.taxable_account, self.rrsp2): Decimal(1)}
        strategy = TransactionTraversal(priority=priority)
        # Contribute $200 (enough to fill RRSPs with $100 left over):
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # $100 should go to rrsp, with balance to taxable:
        self.assertTransactions(transactions[self.rrsp], Money(100))
        if self.rrsp2 in transactions:
            self.assertTransactions(transactions[self.rrsp2], Money(0))
        self.assertTransactions(transactions[self.taxable_account], Money(100))

    def test_assign_mins(self):
        """ Assign minimum inflows without throwing off total inflows. """
        # Simple scenario: One account that takes $10-$100 in inflows:
        priority = [self.debt]
        strategy = TransactionTraversal(priority=priority)
        # Contribute more than the account can accept:
        available = {Decimal(0.5): Money(200)}
        transactions = strategy(available)
        # Exactly $100 should go to the account:
        self.assertTransactions(
            transactions[self.debt], Money(100))

    def test_assign_mins_out(self):
        """ Assign minimum outflows without throwing off total outflows. """
        # RRSPs have min outflows (if converted to an RRIF), so use
        # one of those:
        self.person.birth_date = self.initial_year - 72
        self.rrsp.convert_to_rrif(year=self.initial_year - 1)
        priority = [self.rrsp]
        strategy = TransactionTraversal(priority=priority)
        # Withdraw more than min_outflow_limit and less than balance:
        total = (self.rrsp.min_outflow_limit - self.rrsp.balance) / 2
        available = {Decimal(0.5): total}
        transactions = strategy(available)
        # Exactly the `total` amount should be withdrawn:
        self.assertTransactions(transactions[self.rrsp], total)

    def test_assign_mins_out_overflow(self):
        """ Assign minimum outflows without throwing off total outflows. """
        # RRSPs have min outflows (if converted to an RRIF), so use
        # one of those:
        self.person.birth_date = self.initial_year - 72
        self.rrsp.convert_to_rrif(year=self.initial_year - 1)
        priority = [self.rrsp]
        strategy = TransactionTraversal(priority=priority)
        # Try to withdraw more than the account allows:
        total = -2 * self.rrsp.balance
        available = {Decimal(0.5): total}
        transactions = strategy(available)
        # Withdrawals should not exceed the RRSP's max outflows:
        self.assertTransactions(
            transactions[self.rrsp], self.rrsp.max_outflows(timing=available))

    def test_assign_mins_unbalanced(self):
        """ Assign min inflows to some accounts and not to others.

        This example was part of an old test for WithdrawalForecast and
        gave rise to unexpected results. Rather than test it indirectly
        there, test for it explicitly here.

        The basic problem we're checking for is where we have multiple
        accounts with different min_inflow (or min_outflow) limits.
        TransactionTraversal will assign those transactions first, which
        don't necessarily align with the weights of a weighted node.
        When going on to the second traversal (for max_inflow or
        max_outflow), that imbalance in the prior transactions needs to
        be accounted for.
        """
        # Set up an RRSP that's been converted to an RRIF (so that it
        # has minimum withdrawals).
        self.person.birth_date = self.initial_year - 72
        self.rrsp.convert_to_rrif(year=self.initial_year - 1)
        # Use balances that were used by TestWithdrawalForecast:
        self.rrsp.balance = Money(6000)
        self.taxable_account.balance = Money(60000)
        # We want to withdraw $20,000 from these accounts, with
        # $3000 from the RRSP and $17000 from the taxable account.
        priority = {
            self.rrsp: Decimal(3000), self.taxable_account: Decimal(17000)}
        # Use the same `available` dict as in TestWithdrawalForecast,
        # with $2000 in inflows and $22,000 in outflows, for a net need
        # of $20,000 in withdrawals to make up the shortfall:
        available = {
            Decimal(0.25): Money(1000),
            Decimal(0.5): Money(-11000),
            Decimal(0.75): Money(1000),
            Decimal(1): Money(-11000)}
        strategy = TransactionTraversal(priority=priority)
        # Generate the transactions:
        transactions = strategy(available)
        # Confirm that the $20,000 is distributed as in `priority`:
        self.assertAccountTransactionsTotal(transactions, Money(-20000))
        self.assertTransactions(transactions[self.rrsp], Money(-3000))
        self.assertTransactions(
            transactions[self.taxable_account], Money(-17000))

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

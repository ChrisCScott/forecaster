""" Unit tests for `TransactionStrategy`. """

import unittest
from decimal import Decimal
from forecaster import Person, Money, TransactionStrategy
from forecaster.canada import RRSP, TFSA, TaxableAccount
from tests.util import make_available, TestCaseTransactions


class TestTransactionStrategyOrdered(TestCaseTransactions):
    """ A test case for TransactionStrategy.strategy_ordered """

    def setUp(self):
        """ Sets up variables for testing. """
        # Different groups of tests use different groups of variables.
        # We could split this class up into multiple classes (perhaps
        # one for ordered strategies and one for weighted strategies?),
        # but for now this project's practice is one test case for each
        # custom class.
        # pylint: disable=too-many-instance-attributes

        initial_year = 2000
        person = Person(
            initial_year, 'Testy McTesterson', 1980, retirement_date=2045)

        # Set up some accounts for the tests.
        self.rrsp = RRSP(
            person,
            balance=Money(200), rate=0, contribution_room=Money(200))
        self.tfsa = TFSA(
            person,
            balance=Money(100), rate=0, contribution_room=Money(100))
        self.taxable_account = TaxableAccount(
            person, balance=Money(1000), rate=0)
        self.accounts = {self.rrsp, self.tfsa, self.taxable_account}

        # Define a simple timing for transactions:
        self.timing = {Decimal(0.5): 1}

        # Build strategy for testing (in non-init tests):
        self.strategy = TransactionStrategy(
            TransactionStrategy.strategy_ordered, {
                'RRSP': 1,
                'TFSA': 2,
                'TaxableAccount': 3
            })

    # Test with inflows:

    def test_in_basic(self):
        """ Test strategy_ordered with a small amount of inflows. """
        # The amount being contributed is less than the available
        # contribution room in the top-weighted account type.
        available = make_available(Money(100), self.timing)
        results = self.strategy(available, self.accounts)
        self.assertTransactions(results[self.rrsp], Money(100))
        # Accounts with no transactions aren't guaranteed to be
        # included in the results dict:
        if self.tfsa in results:
            self.assertTransactions(results[self.tfsa], Money(0))
        if self.taxable_account in results:
            self.assertTransactions(results[self.taxable_account], Money(0))

    def test_in_fill_one(self):
        """ Test strategy_ordered with inflows to fill 1 account. """
        # Contribute more than the rrsp will accomodate.
        # The extra $50 should go to the tfsa, which is next in line.
        available = make_available(Money(250), self.timing)
        results = self.strategy(available, self.accounts)
        self.assertTransactions(results[self.rrsp], Money(200))
        self.assertTransactions(results[self.tfsa], Money(50))
        if self.taxable_account in results:
            self.assertTransactions(results[self.taxable_account], Money(0))

    def test_in_fill_two(self):
        """ Test strategy_ordered with inflows to fill 2 accounts. """
        # The rrsp and tfsa will get filled and the remainder will go to
        # the taxable account.
        available = make_available(Money(1000), self.timing)
        results = self.strategy(available, self.accounts)
        self.assertTransactions(results[self.rrsp], Money(200))
        self.assertTransactions(results[self.tfsa], Money(100))
        self.assertTransactions(results[self.taxable_account], Money(700))

    # Test with outflows:

    def test_out_basic(self):
        """ Test strategy_ordered with a small amount of outflows. """
        # The amount being withdrawn is less than the max outflow in the
        # top-weighted account type.
        available = make_available(Money(-100), self.timing)
        results = self.strategy(available, self.accounts)
        self.assertTransactions(results[self.rrsp], Money(-100))
        if self.tfsa in results:
            self.assertTransactions(results[self.tfsa], Money(0))
        if self.taxable_account in results:
            self.assertTransactions(results[self.taxable_account], Money(0))

    def test_out_empty_one(self):
        """ Test strategy_ordered with outflows to empty 1 account. """
        # Now withdraw more than the rrsp will accomodate. The extra $50
        # should come from the tfsa, which is next in line.
        available = make_available(Money(-250), self.timing)
        results = self.strategy(available, self.accounts)
        self.assertTransactions(results[self.rrsp], Money(-200))
        self.assertTransactions(results[self.tfsa], Money(-50))
        if self.taxable_account in results:
            self.assertTransactions(results[self.taxable_account], Money(0))

    def test_out_empty_two(self):
        """ Test strategy_ordered with outflows to empty 2 accounts. """
        # The rrsp and tfsa will get emptied and the remainder will go
        # to the taxable account.
        available = make_available(Money(-1000), self.timing)
        results = self.strategy(available, self.accounts)
        self.assertTransactions(results[self.rrsp], self.rrsp.max_outflows())
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        self.assertTransactions(results[self.taxable_account], Money(-700))

    def test_out_empty_all(self):
        """ Test strategy_ordered with outflows to empty all account. """
        # Try withdrawing more than all of the accounts have:
        val = sum(
            sum(account.max_outflows().values())
            for account in self.accounts
        ) * 2
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        self.assertTransactions(results[self.rrsp], self.rrsp.max_outflows())
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        self.assertTransactions(
            results[self.taxable_account],
            self.taxable_account.max_outflows())

    def test_change_order(self):
        """ Test strategy_ordered works with changed order vars. """
        self.strategy.weights['RRSP'] = 2
        self.strategy.weights['TFSA'] = 1
        available = make_available(Money(100), self.timing)
        results = self.strategy(available, self.accounts)
        # Contribute the full $100 to TFSA:
        self.assertTransactions(results[self.tfsa], self.tfsa.max_inflows())
        # Remaining accounts shouldn't be contributed to:
        if self.rrsp in results:
            self.assertTransactions(results[self.rrsp], Money(0))
        if self.taxable_account in results:
            self.assertTransactions(results[self.taxable_account], Money(0))


class TestTransactionStrategyOrderedMult(TestCaseTransactions):
    """ Tests TransactionStrategy.strategy_ordered with account groups.
    In particular, this test case includes multiple accounts of the same
    type (e.g. two RRSPs) to ensure that accounts that share a weighting
    are handled properly.
    """

    def setUp(self):
        """ Sets up variables for testing. """
        initial_year = 2000
        person = Person(
            initial_year, 'Testy McTesterson', 1980, retirement_date=2045)

        # Set up some accounts for the tests.
        self.rrsp = RRSP(
            person,
            balance=Money(200), rate=0, contribution_room=Money(200))
        self.rrsp2 = RRSP(person, balance=Money(100), rate=0)
        self.tfsa = TFSA(
            person,
            balance=Money(100), rate=0, contribution_room=Money(100))
        self.taxable_account = TaxableAccount(
            person, balance=Money(1000), rate=0)
        self.accounts = {
            self.rrsp, self.rrsp2, self.tfsa, self.taxable_account
        }

        # Define a simple timing for transactions:
        self.timing = {Decimal(0.5): 1}

        self.max_outflow = sum(
            sum(account.max_outflows(timing=self.timing).values())
            for account in self.accounts)
        self.max_inflows = sum(
            sum(account.max_inflows(timing=self.timing).values())
            for account in self.accounts)

        # Build strategies for testing (in non-init tests):
        self.strategy = TransactionStrategy(
            TransactionStrategy.strategy_ordered, {
                'RRSP': 1,
                'TFSA': 2,
                'TaxableAccount': 3
            })

    def test_out_basic(self):
        """ Test strategy_ordered with multiple RRSPs, small outflows. """
        available = make_available(Money(-150), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm that the total of all outflows sums up to `-$150`,
        # which should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, Money(-150))
        self.assertAlmostEqual(
            sum(results[self.rrsp].values())
            + sum(results[self.rrsp2].values()),
            Money(-150))

    def test_out_empty_three(self):
        """ Test strategy_ordered with multiple RRSPs, empty 3 accounts. """
        available = make_available(Money(-400), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm that the total of all outflows sums up to -$400, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, Money(-400))
        self.assertTransactions(results[self.rrsp], Money(-200))
        self.assertTransactions(results[self.rrsp2], Money(-100))
        self.assertTransactions(results[self.tfsa], Money(-100))

    def test_out_empty_all(self):
        """ Test strategy_ordered with multiple RRSPs, empty all accounts. """
        # Try to withdraw more than all accounts combined contain:
        val = self.max_outflow * 2
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Ensure that the correct amount is withdrawn in total; should
        # be the amount available in the accounts (i.e. their balances):
        self.assertAccountTransactionsTotal(
            results,
            -sum(account.balance for account in self.accounts))
        # Confirm balances for each account:
        self.assertTransactions(results[self.rrsp], self.rrsp.max_outflows())
        self.assertTransactions(results[self.rrsp2], self.rrsp2.max_outflows())
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        self.assertTransactions(
            results[self.taxable_account], self.taxable_account.max_outflows())

    def test_in_basic(self):
        """ Test strategy_ordered with multiple RRSPs, small inflows. """
        # Amount contributed is more than the RRSPs can receive:
        val = self.rrsp.contribution_room + Money(50)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)

        # Confirm that the total amount contributed to the RRSPs is
        # equal to their (shared) contribution room.
        # If it exceeds that limit, then it's likely that their
        # contribution room sharing isn't being respected.
        self.assertAlmostEqual(
            sum(results[self.rrsp].values())
            + sum(results[self.rrsp2].values()),
            self.rrsp.contribution_room)
        # The remainder should be contributed to the TFSA:
        self.assertTransactions(results[self.tfsa], Money(50))


class TestTransactionStrategyWeighted(TestCaseTransactions):
    """ A test case for TransactionStrategy.strategy_weighted. """

    def setUp(self):
        """ Sets up variables for testing. """

        # Vars for building accounts:
        initial_year = 2000
        person = Person(
            initial_year, 'Testy McTesterson', 1980, retirement_date=2045)

        # Set up some accounts for the tests.
        self.rrsp = RRSP(
            person,
            balance=Money(200), rate=0, contribution_room=Money(200))
        self.tfsa = TFSA(
            person,
            balance=Money(100), rate=0, contribution_room=Money(100))
        self.taxable_account = TaxableAccount(
            person, balance=Money(1000), rate=0)
        self.accounts = {self.rrsp, self.tfsa, self.taxable_account}

        # Define a simple timing for transactions:
        self.timing = {Decimal(0.5): 1}

        self.max_outflow = sum(
            sum(account.max_outflows(timing=self.timing).values())
            for account in self.accounts)
        self.max_inflows = sum(
            sum(account.max_inflows(timing=self.timing).values())
            for account in self.accounts)

        # Build strategy for testing (in non-init tests):
        self.weights = {
            'RRSP': Decimal('0.4'),
            'TFSA': Decimal('0.3'),
            'TaxableAccount': Decimal('0.3')
        }
        self.strategy = TransactionStrategy(
            TransactionStrategy.strategy_weighted, self.weights)

    # Test with outflows:

    def test_out_basic(self):
        """ Test strategy_weighted with small amount of outflows. """
        # Amount withdrawn is smaller than the balance of each account.
        val = max(
            sum(account.max_outflows().values())
            for account in self.accounts)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)
        # Confirm each account gets the expected total transactions:
        self.assertTransactions(results[self.rrsp], val * self.weights['RRSP'])
        self.assertTransactions(results[self.tfsa], val * self.weights['TFSA'])
        self.assertTransactions(
            results[self.taxable_account],
            val * self.weights['TaxableAccount'])

    def test_out_one_empty(self):
        """ Test strategy_weighted with outflows to empty 1 account. """
        # Now withdraw enough to exceed the TFSA's balance, plus a bit.
        threshold = (
            sum(self.tfsa.max_outflows().values())
            / self.weights['TFSA'])
        val = Money(threshold - Money(50))
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Sum up results for each account for convenience:
        results_totals = {
            account: sum(transactions.values())
            for account, transactions in results.items()}
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)
        # Confirm each account gets the expected total transactions:
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        self.assertAlmostEqual(
            results_totals[self.rrsp] / self.weights['RRSP'],
            results_totals[self.taxable_account]
            / self.weights['TaxableAccount'])

    def test_out_two_empty(self):
        """ Test strategy_weighted with outflows to empty 2 accounts. """
        # Withdraw just a little less than the total available balance.
        # This will clear out the RRSP and TFSA.
        val = sum(
            sum(account.max_outflows().values())
            for account in self.accounts
        ) + Money(50)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)
        # Confirm each account gets the expected total transactions:
        self.assertTransactions(results[self.rrsp], self.rrsp.max_outflows())
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        self.assertTransactions(
            results[self.taxable_account],
            sum(self.taxable_account.max_outflows().values())
            + Money(50))

    def test_out_all_empty(self):
        """ Test strategy_weighted with outflows to empty all accounts. """
        # Withdraw more than the accounts have:
        val = sum(
            sum(account.max_outflows().values())
            for account in self.accounts
        ) - Money(50)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm each account gets the expected total transactions:
        self.assertTransactions(results[self.rrsp], self.rrsp.max_outflows())
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        self.assertTransactions(
            results[self.taxable_account],
            self.taxable_account.max_outflows())

    def test_in_basic(self):
        """ Test strategy_weighted with a small amount of inflows. """
        # The amount being contributed is less than the available
        # contribution room for each account
        val = min(
            sum(account.max_inflows().values())
            for account in self.accounts)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)
        # Confirm accounts have separate total transaction values:
        self.assertTransactions(results[self.rrsp], val * self.weights['RRSP'])
        self.assertTransactions(results[self.tfsa], val * self.weights['TFSA'])
        self.assertTransactions(
            results[self.taxable_account],
            val * self.weights['TaxableAccount'])

    def test_in_fill_one(self):
        """ Test strategy_weighted with inflows to fill 1 account. """
        # Now contribute enough to exceed the TFSA's contribution room.
        # The excess (i.e. the amount that would be contributed to the
        # TFSA but can't because of its lower contribution room) should
        # be redistributed to the other accounts proportionately to
        # their relative weights:
        threshold = (
            sum(self.tfsa.max_inflows().values()) / self.weights['TFSA'])
        val = Money(threshold + Money(50))
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)

        self.assertTransactions(results[self.tfsa], self.tfsa.max_inflows())
        self.assertTransactions(
            results[self.rrsp],
            sum(results[self.taxable_account].values())
            * self.weights['RRSP'] / self.weights['TaxableAccount'])

    def test_in_fill_two(self):
        """ Test strategy_weighted with inflows to fill 2 accounts. """
        # Contribute a lot of money - the rrsp and tfsa will get
        # filled and the remainder will go to the taxable account.
        threshold = max(
            sum(self.rrsp.max_inflows().values()) / self.weights['RRSP'],
            sum(self.tfsa.max_inflows().values()) / self.weights['TFSA'])
        val = threshold + Money(50)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)
        # Confirm accounts have expected transactions:
        self.assertTransactions(results[self.rrsp], self.rrsp.max_inflows())
        self.assertTransactions(results[self.tfsa], self.tfsa.max_inflows())
        self.assertTransactions(
            results[self.taxable_account],
            val - (
                sum(self.rrsp.max_inflows().values())
                + sum(self.tfsa.max_inflows().values())))


class TestTransactionStrategyWeightedLink(TestCaseTransactions):
    """ Tests TransactionStrategy.strategy_weighted with linked accounts
    
    This test case includes multiple linked accounts (e.g. two RRSPs)
    to ensure that accounts that share a weighting are handled properly.
    """

    def setUp(self):
        """ Sets up variables for testing. """
        # Vars for building accounts:
        initial_year = 2000
        person = Person(
            initial_year, 'Testy McTesterson', 1980, retirement_date=2045)

        # Set up some accounts for the tests.
        self.rrsp = RRSP(
            person,
            balance=Money(200), rate=0, contribution_room=Money(200))
        self.rrsp2 = RRSP(person, balance=Money(100), rate=0)
        self.tfsa = TFSA(
            person,
            balance=Money(100), rate=0, contribution_room=Money(100))
        self.taxable_account = TaxableAccount(
            person, balance=Money(1000), rate=0)
        self.accounts = {
            self.rrsp, self.rrsp2, self.tfsa, self.taxable_account
        }

        # Define a simple timing for transactions:
        self.timing = {Decimal(0.5): 1}

        # Build strategy for testing (in non-init tests):
        self.weights = {
            'RRSP': Decimal('0.4'),
            'TFSA': Decimal('0.3'),
            'TaxableAccount': Decimal('0.3')
        }
        self.strategy = TransactionStrategy(
            TransactionStrategy.strategy_weighted, self.weights)

    def test_out_basic(self):
        """ Test strategy_weighted with multiple RRSPs, small outflows. """
        # Amount withdrawn is less than the balance of each account.
        val = Money(
            max(sum(account.max_outflows().values())
                for account in self.accounts))
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Sum up results for each account for convenience:
        results_totals = {
            account: sum(transactions.values())
            for account, transactions in results.items()}
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)
        # Confirm RRSPs' shared weight is respected:
        self.assertAlmostEqual(
            results_totals[self.rrsp] + results_totals[self.rrsp2],
            val * self.weights['RRSP'])
        # Confirm that money is withdrawn from each RRSP, but don't
        # put constraints on how much:
        self.assertLess(results_totals[self.rrsp], Money(0))
        self.assertLess(results_totals[self.rrsp2], Money(0))
        # Confirm that remaining accounts have expected amounts:
        self.assertTransactions(results[self.tfsa], val * self.weights['TFSA'])
        self.assertTransactions(
            results[self.taxable_account],
            val * self.weights['TaxableAccount'])

    def test_out_empty_one(self):
        """ Test strategy_weighted with multiple RRSPs, empty 1 account. """
        # Withdraw enough to exceed the balance of one account (the
        # TFSA, in this case, as it has the smallest balance):
        threshold = (
            sum(self.tfsa.max_outflows().values())
            / self.weights['TFSA'])
        val = Money(threshold - Money(50))
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Sum up results for each account for convenience:
        results_totals = {
            account: sum(transactions.values())
            for account, transactions in results.items()}
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)
        # Confirm each account has the expected set of transactions:
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        # The excess (i.e. the amount that would ordinarily be
        # contributed to the TFSA but can't due to contribution room
        # limits) should also be split between RRSPs and the TFSA
        # proportionately to their relative weights.
        self.assertAlmostEqual(
            results_totals[self.rrsp] + results_totals[self.rrsp2],
            results_totals[self.taxable_account]
            * self.weights['RRSP'] / self.weights['TaxableAccount'])

    def test_out_empty_three(self):
        """ Test strategy_weighted with mult. RRSPs, empty 3 accounts. """
        # Try withdrawing just a little less than the total available
        # balance. This will clear out the RRSPs and TFSA and leave the
        # remainder in the taxable account, since the taxable account
        # has a much larger balance and roughly similar weight:
        val = sum(
            sum(account.max_outflows().values())
            for account in self.accounts
        ) + Money(50)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Sum up results for each account for convenience:
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)
        # Also confirm that the smaller accounts get emptied:
        self.assertTransactions(results[self.rrsp], self.rrsp.max_outflows())
        self.assertTransactions(results[self.rrsp2], self.rrsp2.max_outflows())
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        # And confirm that the largest account is not-quite-filled:
        self.assertTransactions(
            results[self.taxable_account],
            sum(self.taxable_account.max_outflows().values()) + Money(50))

    def test_out_empty_all(self):
        """ Test strategy_weighted with mult. RRSPs, empty all accounts. """
        # Try withdrawing more than the accounts have
        val = sum(
            sum(account.max_outflows().values())
            for account in self.accounts
        ) - Money(50)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Confirm each account has the expected set of transactions:
        self.assertTransactions(results[self.rrsp], self.rrsp.max_outflows())
        self.assertTransactions(results[self.tfsa], self.tfsa.max_outflows())
        self.assertTransactions(
            results[self.taxable_account],
            self.taxable_account.max_outflows())

    def test_in_basic(self):
        """ Test strategy_weighted with multiple RRSPs, small inflows. """
        # Amount contributed is more than the RRSPs can receive:
        val = self.rrsp.contribution_room / self.weights['RRSP'] + Money(50)
        available = make_available(Money(val), self.timing)
        results = self.strategy(available, self.accounts)
        # Sum up results for each account for convenience:
        results_totals = {
            account: sum(transactions.values())
            for account, transactions in results.items()}
        # Confirm that the total of all outflows sums up to `val`, which
        # should be fully allocated to accounts:
        self.assertAccountTransactionsTotal(results, val)

        # Confirm that the total amount contributed to the RRSPs is
        # equal to their (shared) contribution room.
        # If it exceeds that limit, then it's likely that their
        # contribution room sharing isn't being respected.
        self.assertAlmostEqual(
            results_totals[self.rrsp] + results_totals[self.rrsp2],
            self.rrsp.contribution_room)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

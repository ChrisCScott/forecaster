""" Unit tests for `TransactionStrategy`. """

import unittest
from decimal import Decimal
from forecaster import Person, Money, TransactionStrategy
from forecaster.canada import RRSP, TFSA, TaxableAccount


class TestTransactionStrategyMethods(unittest.TestCase):
    """ A test case for non-strategy method of TransactionStrategy. """

    def setUp(self):
        """ Sets up variables for testing. """
        self.weights = {
            'RRSP': Decimal(0.5),
            'TFSA': Decimal(0.25),
            'TaxableAccount': Decimal(0.25)
        }
        self.method = TransactionStrategy.strategy_weighted

    def test_init_explicit(self):
        """ Test __init__ with explicit arguments. """
        method = 'Weighted'
        weights = {
            'RRSP': Decimal(0.5),
            'TFSA': Decimal(0.25),
            'TaxableAccount': Decimal(0.25)
        }
        timing = 'end'
        strategy = TransactionStrategy(method, weights, timing)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.weights, weights)
        self.assertEqual(strategy.timing, timing)

    def test_init_implicit(self):
        """ Test __init__ with implicit (omitted optional) arguments. """
        strategy = TransactionStrategy("Weighted", self.weights)

        self.assertEqual(strategy.strategy, "Weighted")
        self.assertEqual(strategy.weights, self.weights)
        self.assertEqual(strategy.timing, 'end')

    def test_init_invalid(self):
        """ Test __init__ with invalid arguments. """
        # Test invalid strategies
        with self.assertRaises(ValueError):
            TransactionStrategy(
                strategy='Not a strategy', weights={})
        with self.assertRaises(TypeError):
            TransactionStrategy(strategy=1, weights={})
        # Test invalid weight
        with self.assertRaises(TypeError):  # not a dict
            TransactionStrategy(strategy=self.method, weights='a')
        with self.assertRaises(TypeError):  # dict with non-str keys
            TransactionStrategy(
                strategy=self.method, weights={1: 5})
        with self.assertRaises(TypeError):  # dict with non-numeric values
            TransactionStrategy(
                strategy=self.method, weights={'RRSP', 'Not a number'})
        # Test invalid timing
        with self.assertRaises(TypeError):
            TransactionStrategy(strategy=self.method, weights={}, timing={})


class TestTransactionStrategyOrdered(unittest.TestCase):
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
        results = self.strategy(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxable_account], Money(0))

    def test_in_fill_one(self):
        """ Test strategy_ordered with inflows to fill 1 account. """
        # Contribute more than the rrsp will accomodate.
        # The extra $50 should go to the tfsa, which is next in line.
        results = self.strategy(Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(50))
        self.assertEqual(results[self.taxable_account], Money(0))

    def test_in_fill_two(self):
        """ Test strategy_ordered with inflows to fill 2 accounts. """
        # The rrsp and tfsa will get filled and the remainder will go to
        # the taxable account.
        results = self.strategy(Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxable_account], Money(700))

    # Test with outflows:

    def test_out_basic(self):
        """ Test strategy_ordered with a small amount of outflows. """
        # The amount being withdrawn is less than the max outflow in the
        # top-weighted account type.
        results = self.strategy(-Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxable_account], Money(0))

    def test_out_empty_one(self):
        """ Test strategy_ordered with outflows to empty 1 account. """
        # Now withdraw more than the rrsp will accomodate. The extra $50
        # should come from the tfsa, which is next in line.
        results = self.strategy(-Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-50))
        self.assertEqual(results[self.taxable_account], Money(0))

    def test_out_empty_two(self):
        """ Test strategy_ordered with outflows to empty 2 accounts. """
        # The rrsp and tfsa will get emptied and the remainder will go
        # to the taxable account.
        results = self.strategy(-Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxable_account], Money(-700))

    def test_out_empty_all(self):
        """ Test strategy_ordered with outflows to empty all account. """
        # Try withdrawing more than all of the accounts have:
        val = sum(
            account.max_outflow(self.strategy.timing)
            for account in self.accounts
        ) * 2
        results = self.strategy(val, self.accounts)
        self.assertEqual(
            results[self.rrsp],
            self.rrsp.max_outflow(self.strategy.timing))
        self.assertEqual(
            results[self.tfsa],
            self.tfsa.max_outflow(self.strategy.timing))
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow(self.strategy.timing))

    def test_change_order(self):
        """ Test strategy_ordered works with changed order vars. """
        self.strategy.weights['RRSP'] = 2
        self.strategy.weights['TFSA'] = 1
        results = self.strategy(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(0))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxable_account], Money(0))


class TestTransactionStrategyOrderedMult(unittest.TestCase):
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

        # Build strategies for testing (in non-init tests):
        self.strategy = TransactionStrategy(
            TransactionStrategy.strategy_ordered, {
                'RRSP': 1,
                'TFSA': 2,
                'TaxableAccount': 3
            })

    def test_out_basic(self):
        """ Test strategy_ordered with multiple RRSPs, small outflows. """
        results = self.strategy(Money(-150), self.accounts)
        self.assertEqual(sum(results.values()), Money(-150))
        self.assertEqual(results[self.rrsp] + results[self.rrsp2], Money(-150))

    def test_out_empty_three(self):
        """ Test strategy_ordered with multiple RRSPs, empty 3 accounts. """
        results = self.strategy(Money(-400), self.accounts)
        self.assertEqual(sum(results.values()), Money(-400))
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.rrsp2], Money(-100))
        self.assertEqual(results[self.tfsa], Money(-100))

    def test_out_empty_all(self):
        """ Test strategy_ordered with multiple RRSPs, empty all accounts. """
        # Try to withdraw more than all accounts combined contain:
        val = sum(
            account.max_outflow(self.strategy.timing)
            for account in self.accounts
        ) * 2
        results = self.strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), -sum(
            account.balance for account in self.accounts))
        self.assertEqual(results[self.rrsp], -self.rrsp.balance)
        self.assertEqual(results[self.rrsp2], -self.rrsp2.balance)
        self.assertEqual(results[self.tfsa], -self.tfsa.balance)
        self.assertEqual(
            results[self.taxable_account], -self.taxable_account.balance)

    def test_in_basic(self):
        """ Test strategy_ordered with multiple RRSPs, small inflows. """
        # Amount contributed is more than the RRSPs can receive:
        val = self.rrsp.contribution_room + Money(50)
        results = self.strategy(val, self.accounts)

        self.assertEqual(sum(results.values()), val)
        # Confirm that the total amount contributed to the RRSPs is
        # equal to their (shared) contribution room.
        # If it exceeds that limit, then it's likely that their
        # contribution room sharing isn't being respected.
        self.assertEqual(
            results[self.rrsp] + results[self.rrsp2],
            self.rrsp.contribution_room)


class TestTransactionStrategyWeighted(unittest.TestCase):
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

        # Build strategy for testing (in non-init tests):
        self.weights = {
            'RRSP': Decimal('0.4'),
            'TFSA': Decimal('0.3'),
            'TaxableAccount': Decimal('0.3')
        }
        self.strategy_weighted = TransactionStrategy(
            TransactionStrategy.strategy_weighted, self.weights)

    # Test with outflows:

    def test_out_basic(self):
        """ Test strategy_weighted with small amount of outflows. """
        # Amount withdrawn is smaller than the balance of each account.
        val = Money(max(
            account.max_outflow(self.strategy_weighted.timing)
            for account in self.accounts)
        )
        results = self.strategy_weighted(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * self.weights['RRSP'])
        self.assertEqual(results[self.tfsa], val * self.weights['TFSA'])
        self.assertEqual(results[self.taxable_account],
                         val * self.weights['TaxableAccount'])

    def test_out_one_empty(self):
        """ Test strategy_weighted with outflows to empty 1 account. """
        # Now withdraw enough to exceed the TFSA's balance, plus a bit.
        threshold = (
            self.tfsa.max_outflow(self.strategy_weighted.timing)
            / self.weights['TFSA'])
        val = Money(threshold - Money(50))
        results = self.strategy_weighted(val, self.accounts)
        self.assertEqual(
            results[self.tfsa],
            self.tfsa.max_outflow(self.strategy_weighted.timing))
        self.assertAlmostEqual(sum(results.values()), val, places=5)
        self.assertAlmostEqual(
            results[self.rrsp],
            results[self.taxable_account]
            * self.weights['RRSP'] / self.weights['TaxableAccount'])

    def test_out_two_empty(self):
        """ Test strategy_weighted with outflows to empty 2 accounts. """
        # Withdraw just a little less than the total available balance.
        # This will clear out the RRSP and TFSA.
        val = sum(
            account.max_outflow(self.strategy_weighted.timing)
            for account in self.accounts
        ) + Money(50)
        results = self.strategy_weighted(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(
            results[self.rrsp],
            self.rrsp.max_outflow(self.strategy_weighted.timing))
        self.assertEqual(
            results[self.tfsa],
            self.tfsa.max_outflow(self.strategy_weighted.timing))
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow(self.strategy_weighted.timing)
            + Money(50))

    def test_out_all_empty(self):
        """ Test strategy_weighted with outflows to empty all accounts. """
        # Withdraw more than the accounts have:
        val = sum(
            account.max_outflow(self.strategy_weighted.timing)
            for account in self.accounts
        ) - Money(50)
        results = self.strategy_weighted(val, self.accounts)
        self.assertEqual(
            results[self.rrsp],
            self.rrsp.max_outflow(self.strategy_weighted.timing))
        self.assertEqual(
            results[self.tfsa],
            self.tfsa.max_outflow(self.strategy_weighted.timing))
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow(self.strategy_weighted.timing))

    def test_in_basic(self):
        """ Test strategy_weighted with a small amount of inflows. """
        # The amount being contributed is less than the available
        # contribution room for each account
        val = Money(min(account.max_inflow() for account in self.accounts))
        results = self.strategy_weighted(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * self.weights['RRSP'])
        self.assertEqual(results[self.tfsa], val * self.weights['TFSA'])
        self.assertEqual(results[self.taxable_account],
                         val * self.weights['TaxableAccount'])

    def test_in_fill_one(self):
        """ Test strategy_weighted with inflows to fill 1 account. """
        # Now contribute enough to exceed the TFSA's contribution room.
        # The excess (i.e. the amount that would be contributed to the
        # TFSA but can't because of its lower contribution room) should
        # be redistributed to the other accounts proportionately to
        # their relative weights:
        threshold = self.tfsa.max_inflow() / self.weights['TFSA']
        val = Money(threshold + Money(50))
        results = self.strategy_weighted(val, self.accounts)
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertAlmostEqual(sum(results.values()), val, places=5)
        self.assertAlmostEqual(
            results[self.rrsp],
            results[self.taxable_account]
            * self.weights['RRSP'] / self.weights['TaxableAccount']
        )

    def test_in_fill_two(self):
        """ Test strategy_weighted with inflows to fill 2 accounts. """
        # Contribute a lot of money - the rrsp and tfsa will get
        # filled and the remainder will go to the taxable account.
        threshold = max(self.rrsp.max_inflow() / self.weights['RRSP'],
                        self.tfsa.max_inflow() / self.weights['TFSA'])
        val = threshold + Money(50)
        results = self.strategy_weighted(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_inflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertEqual(results[self.taxable_account], val -
                         (self.rrsp.max_inflow() + self.tfsa.max_inflow()))


class TestTransactionStrategyWeightedMult(unittest.TestCase):
    """ Tests TransactionStrategy.strategy_weighted with account groups.

    In particular, this test case includes multiple accounts of the same
    type (e.g. two RRSPs) to ensure that accounts that share a weighting
    are handled properly.
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
        val = Money(max(
            account.max_outflow(self.strategy.timing)
            for account in self.accounts)
        )
        results = self.strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(
            results[self.rrsp] + results[self.rrsp2],
            val * self.weights['RRSP'])
        # Confirm that money is withdrawn from each RRSP, but don't
        # put constraints on how much:
        self.assertLess(results[self.rrsp], Money(0))
        self.assertLess(results[self.rrsp2], Money(0))
        self.assertEqual(results[self.tfsa], val * self.weights['TFSA'])
        self.assertEqual(
            results[self.taxable_account],
            val * self.weights['TaxableAccount'])

    def test_out_empty_one(self):
        """ Test strategy_weighted with multiple RRSPs, empty 1 account. """
        # Withdraw enough to exceed the balance of one account (the
        # TFSA, in this case, as it has the smallest balance):
        threshold = (
            self.tfsa.max_outflow(self.strategy.timing)
            / self.weights['TFSA'])
        val = Money(threshold - Money(50))
        results = self.strategy(val, self.accounts)
        self.assertAlmostEqual(sum(results.values()), val, places=5)
        self.assertEqual(
            results[self.tfsa],
            self.tfsa.max_outflow(self.strategy.timing))
        # The excess (i.e. the amount that would ordinarily be
        # contributed to the TFSA but can't due to contribution room
        # limits) should also be split between RRSPs and the TFSA
        # proportionately to their relative weights.
        self.assertAlmostEqual(
            results[self.rrsp] + results[self.rrsp2],
            results[self.taxable_account]
            * self.weights['RRSP'] / self.weights['TaxableAccount'])

    def test_out_empty_three(self):
        """ Test strategy_weighted with mult. RRSPs, empty 3 accounts. """
        # Try withdrawing just a little less than the total available
        # balance. This will clear out the RRSPs and TFSA and leave the
        # remainder in the taxable account, since the taxable account
        # has a much larger balance and roughly similar weight:
        val = sum(
            account.max_outflow(self.strategy.timing)
            for account in self.accounts
        ) + Money(50)
        results = self.strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(
            results[self.rrsp],
            self.rrsp.max_outflow(self.strategy.timing))
        self.assertEqual(
            results[self.rrsp2],
            self.rrsp2.max_outflow(self.strategy.timing))
        self.assertEqual(
            results[self.tfsa],
            self.tfsa.max_outflow(self.strategy.timing))
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow(self.strategy.timing)
            + Money(50))

    def test_out_empty_all(self):
        """ Test strategy_weighted with mult. RRSPs, empty all accounts. """
        # Try withdrawing more than the accounts have
        val = sum(
            account.max_outflow(self.strategy.timing)
            for account in self.accounts
        ) - Money(50)
        results = self.strategy(val, self.accounts)
        self.assertEqual(
            results[self.rrsp],
            self.rrsp.max_outflow(self.strategy.timing))
        self.assertEqual(
            results[self.tfsa],
            self.tfsa.max_outflow(self.strategy.timing))
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow(self.strategy.timing))

    def test_in_basic(self):
        """ Test strategy_weighted with multiple RRSPs, small inflows. """
        # Amount contributed is more than the RRSPs can receive:
        val = self.rrsp.contribution_room / self.weights['RRSP'] + Money(50)
        results = self.strategy(val, self.accounts)

        self.assertEqual(sum(results.values()), val)
        # Confirm that the total amount contributed to the RRSPs is
        # equal to their (shared) contribution room.
        # If it exceeds that limit, then it's likely that their
        # contribution room sharing isn't being respected.
        self.assertEqual(
            results[self.rrsp] + results[self.rrsp2],
            self.rrsp.contribution_room)


if __name__ == '__main__':
    unittest.main()

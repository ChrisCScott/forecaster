""" Unit tests for `TransactionStrategy` and `DebtPaymentStrategy`. """

import unittest
from decimal import Decimal
from forecaster import (
    Person, Debt, Money, TransactionStrategy, DebtPaymentStrategy)
from forecaster.canada import RRSP, TFSA, TaxableAccount, constants


class TestTransactionStrategyMethods(unittest.TestCase):
    """ A test case for the TransactionStrategy class """

    @classmethod
    def setUpClass(cls):
        cls.initial_year = 2000
        cls.person = Person(
            cls.initial_year, 'Testy McTesterson', 1980, retirement_date=2045)
        cls.inflation_adjustments = {
            cls.initial_year: Decimal(1),
            cls.initial_year + 1: Decimal(1.25),
            min(constants.RRSP_ACCRUAL_MAX): Decimal(1)}

        # Set up some accounts for the tests.
        cls.rrsp = RRSP(
            cls.person,
            inflation_adjust=cls.inflation_adjustments,
            balance=Money(200), rate=0, contribution_room=Money(200))
        cls.tfsa = TFSA(
            cls.person,
            inflation_adjust=cls.inflation_adjustments,
            balance=Money(100), rate=0, contribution_room=Money(100))
        cls.taxable_account = TaxableAccount(
            cls.person, balance=Money(1000), rate=0)
        cls.accounts = [cls.rrsp, cls.tfsa, cls.taxable_account]

    def test_init(self):
        """ Test TransactionStrategy.__init__ """
        # Test explicit init:
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

        # Test implicit init for optional args:
        strategy = TransactionStrategy(method, weights)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.weights, weights)
        self.assertEqual(strategy.timing, 'end')

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = TransactionStrategy(
                strategy='Not a strategy', weights={})
        with self.assertRaises(TypeError):
            strategy = TransactionStrategy(strategy=1, weights={})
        # Test invalid weight
        with self.assertRaises(TypeError):  # not a dict
            strategy = TransactionStrategy(strategy=method, weights='a')
        with self.assertRaises(TypeError):  # dict with non-str keys
            strategy = TransactionStrategy(strategy=method, weights={1: 5})
        with self.assertRaises(TypeError):  # dict with non-numeric values
            strategy = TransactionStrategy(
                strategy=method, weights={'RRSP', 'Not a number'})
        # Test invalid timing
        with self.assertRaises(TypeError):
            strategy = TransactionStrategy(
                strategy=method, weights={}, timing={})

    def test_strategy_ordered(self):
        """ Test TransactionStrategy.strategy_ordered. """
        # Run each test on inflows and outflows
        method = TransactionStrategy.strategy_ordered
        strategy = TransactionStrategy(
            method, {
                'RRSP': 1,
                'TFSA': 2,
                'TaxableAccount': 3
            })

        # Try a simple scenario: The amount being contributed is less
        # than the available contribution room in the top-weighted
        # account type.
        results = strategy(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxable_account], Money(0))
        # Try again with outflows.
        results = strategy(-Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-100))
        self.assertEqual(results[self.tfsa], Money(0))
        self.assertEqual(results[self.taxable_account], Money(0))

        # Now contribute (withdraw) more than the rrsp will accomodate.
        # The extra $50 should go to the tfsa, which is next in line.
        results = strategy(Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(50))
        self.assertEqual(results[self.taxable_account], Money(0))
        results = strategy(-Money(250), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-50))
        self.assertEqual(results[self.taxable_account], Money(0))

        # Now contribute (withdraw) a lot of money - the rrsp and tfsa
        # will get filled (emptied) and the remainder will go to the
        # taxable account.
        results = strategy(Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(200))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxable_account], Money(700))
        results = strategy(-Money(1000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxable_account], Money(-700))

        # For outflows only, try withdrawing more than the accounts have
        results = strategy(-Money(10000), self.accounts)
        self.assertEqual(results[self.rrsp], Money(-200))
        self.assertEqual(results[self.tfsa], Money(-100))
        self.assertEqual(results[self.taxable_account], Money(-1000))

        # Now change the order and confirm that it still works
        strategy.weights['RRSP'] = 2
        strategy.weights['TFSA'] = 1
        results = strategy(Money(100), self.accounts)
        self.assertEqual(results[self.rrsp], Money(0))
        self.assertEqual(results[self.tfsa], Money(100))
        self.assertEqual(results[self.taxable_account], Money(0))

    def test_strategy_weighted_out(self):
        """ Test TransactionStrategy.strategy_weighted on outflows. """
        method = TransactionStrategy.strategy_weighted
        rrsp_weight = Decimal('0.4')
        tfsa_weight = Decimal('0.3')
        taxable_account_weight = Decimal('0.3')
        strategy = TransactionStrategy(
            method, {
                'RRSP': rrsp_weight,
                'TFSA': tfsa_weight,
                'TaxableAccount': taxable_account_weight
            })

        # Basic test. Amount withdrawn is less than the balance of each
        # account.
        val = -Money(max([a.max_outflow() for a in self.accounts]))
        results = strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * rrsp_weight)
        self.assertEqual(results[self.tfsa], val * tfsa_weight)
        self.assertEqual(results[self.taxable_account],
                         val * taxable_account_weight)

        # Now withdraw enough to exceed the TFSA's balance.
        threshold = self.tfsa.max_outflow() / tfsa_weight
        overage = -Money(50)
        val = Money(threshold + overage)
        results = strategy(val, self.accounts)
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertAlmostEqual(sum(results.values()), val, places=3)
        self.assertLess(results[self.rrsp], results[self.taxable_account])
        rrsp_vals = [
            val * rrsp_weight + overage * rrsp_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_outflow()) * rrsp_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.rrsp], min(rrsp_vals))
        self.assertLessEqual(results[self.rrsp], max(rrsp_vals))
        taxable_vals = [
            val * taxable_account_weight +
            overage * taxable_account_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_outflow()) *
            taxable_account_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.taxable_account],
                                min(taxable_vals))
        self.assertLessEqual(results[self.taxable_account],
                             max(taxable_vals))

        # For withdrawals, try withdrawing just a little less than the
        # total available balance. This will clear out the RRSP and TFSA
        val = self.rrsp.max_outflow() + self.tfsa.max_outflow() + \
            self.taxable_account.max_outflow() - overage
        results = strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_outflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow() - overage)

        # For outflows only, try withdrawing more than the accounts have
        val = self.rrsp.max_outflow() + self.tfsa.max_outflow() + \
            self.taxable_account.max_outflow() + overage
        results = strategy(val, self.accounts)
        self.assertEqual(results[self.rrsp], self.rrsp.max_outflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_outflow())
        self.assertEqual(
            results[self.taxable_account],
            self.taxable_account.max_outflow())

    def test_strategy_weighted_in(self):
        """ Test TransactionStrategy.strategy_weighted on inflows. """
        # Run each test on inflows and outflows
        method = TransactionStrategy.strategy_weighted
        rrsp_weight = Decimal('0.4')
        tfsa_weight = Decimal('0.3')
        taxable_account_weight = Decimal('0.3')
        strategy = TransactionStrategy(
            method, {
                'RRSP': rrsp_weight,
                'TFSA': tfsa_weight,
                'TaxableAccount': taxable_account_weight
            })

        # Try a simple scenario: The amount being contributed is less
        # than the available contribution room for each account
        val = Money(min([a.max_inflow() for a in self.accounts]))
        results = strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], val * rrsp_weight)
        self.assertEqual(results[self.tfsa], val * tfsa_weight)
        self.assertEqual(results[self.taxable_account],
                         val * taxable_account_weight)

        # Now contribute enough to exceed the TFSA's contribution room.
        # This can be implemented in various reasonable ways, but we
        # should ensure that:
        # 1 - TFSA contribution is maxed
        # 2 - The total amount contributed is equal to `val`
        # 3 - More is contributed to RRSPs than taxable accounts.
        # 4 - The proportion of RRSP to taxable contributions should be
        #     in a reasonable range, depending on whether (a) only the
        #     overage is reweighted to exclude the TFSA or (b) the
        #     entire contribution to those accounts is reweighted to
        #     exclude the TFSA. (This is left to the implementation.)
        threshold = self.tfsa.max_inflow() / tfsa_weight
        overage = Money(50)
        val = Money(threshold + overage)
        results = strategy(val, self.accounts)
        # Do tests 1-3:
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertAlmostEqual(sum(results.values()), val, places=3)
        self.assertGreater(results[self.rrsp], results[self.taxable_account])
        # Now we move on to test 4, which is a bit trickier.
        # We want to be in the range defined by:
        # 1 - Only the overage is reweighted, and
        # 2 - The entire contribution to the RRSP is reweighted
        rrsp_vals = [
            val * rrsp_weight + overage * rrsp_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_inflow()) * rrsp_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.rrsp], min(rrsp_vals))
        self.assertLessEqual(results[self.rrsp], max(rrsp_vals))
        taxable_vals = [
            val * taxable_account_weight +
            overage * taxable_account_weight / (1 - tfsa_weight),
            (val - self.tfsa.max_inflow()) *
            taxable_account_weight / (1 - tfsa_weight)
        ]
        self.assertGreaterEqual(results[self.taxable_account],
                                min(taxable_vals))
        self.assertLessEqual(results[self.taxable_account],
                             max(taxable_vals))

        # Now contribute a lot of money - the rrsp and tfsa will get
        # filled and the remainder will go to the taxable account.
        threshold = max(self.rrsp.max_inflow() / rrsp_weight,
                        self.tfsa.max_inflow() / tfsa_weight)
        overage = abs(overage)
        val = threshold + overage
        results = strategy(val, self.accounts)
        self.assertEqual(sum(results.values()), val)
        self.assertEqual(results[self.rrsp], self.rrsp.max_inflow())
        self.assertEqual(results[self.tfsa], self.tfsa.max_inflow())
        self.assertEqual(results[self.taxable_account], val -
                         (self.rrsp.max_inflow() + self.tfsa.max_inflow()))


class TestDebtPaymentStrategyMethods(unittest.TestCase):
    """ A test case for the DebtPaymentStrategy class """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.initial_year = 2000
        cls.person = Person(cls.initial_year, 'Testy McTesterson', 1980,
                            retirement_date=2045)

        # These accounts have different rates:
        cls.debt_big_high_interest = Debt(
            cls.person,
            balance=Money(1000), rate=1, minimum_payment=Money(100),
            reduction_rate=1, accelerate_payment=True
        )
        cls.debt_small_low_interest = Debt(
            cls.person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=1, accelerate_payment=True
        )
        cls.debt_medium = Debt(
            cls.person,
            balance=Money(500), rate=0.5, minimum_payment=Money(50),
            reduction_rate=1, accelerate_payment=True
        )

        cls.debts = {
            cls.debt_big_high_interest,
            cls.debt_medium,
            cls.debt_small_low_interest
        }

        cls.debt_not_accelerated = Debt(
            cls.person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=1, accelerate_payment=False
        )
        cls.debt_no_reduction = Debt(
            cls.person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=1, accelerate_payment=False
        )
        cls.debt_half_reduction = Debt(
            cls.person,
            balance=Money(100), rate=0, minimum_payment=Money(10),
            reduction_rate=0.5, accelerate_payment=False
        )

    @staticmethod
    def min_payment(debts, timing):
        """ Finds the minimum payment *from savings* for `accounts`. """
        # Find the minimum payment *from savings* for each account:
        return sum(
            debt.min_inflow(timing) * debt.reduction_rate
            for debt in debts
        )

    @staticmethod
    def max_payment(debts, timing):
        """ Finds the maximum payment *from savings* for `accounts`. """
        # Find the minimum payment *from savings* for each account:
        return sum(
            debt.max_inflow(timing) * debt.reduction_rate
            for debt in debts
        )

    def test_init(self):
        """ Test DebtPaymentStrategy.__init__ """
        # pylint: disable=no-member
        method = DebtPaymentStrategy.strategy_avalanche.strategy_key
        strategy = DebtPaymentStrategy(method)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.timing, 'end')

        # Test explicit init:
        method = 'Snowball'
        timing = 'end'
        strategy = DebtPaymentStrategy(method, timing)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.timing, timing)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = DebtPaymentStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            strategy = DebtPaymentStrategy(strategy=1)
        # Test invalid timing
        with self.assertRaises(TypeError):
            strategy = DebtPaymentStrategy(strategy=method, timing={})

    def test_strategy_snowball(self):
        """ Test DebtPaymentStrategy.strategy_snowball. """
        # Run each test on inflows and outflows
        method = DebtPaymentStrategy.strategy_snowball
        strategy = DebtPaymentStrategy(method)

        # Try a simple scenario: The amount being contributed is equal
        # to the minimum payments for the accounts.
        min_payment = self.min_payment(self.debts, strategy.timing)
        excess = Money(0)
        payment = min_payment + excess
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

        # Try paying less than the minimum. Minimum should still be paid
        payment = Money(0)
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

        # Try paying a bit more than the minimum
        # The smallest debt should be paid first.
        excess = Money(10)
        payment = min_payment + excess
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment + excess
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment
        )

        # Now pay more than the first-paid debt will accomodate.
        # The excess should go to the next-paid debt (medium).
        payment = (
            self.min_payment(
                self.debts - {self.debt_small_low_interest}, strategy.timing) +
            self.max_payment({self.debt_small_low_interest}, strategy.timing) +
            excess
        )
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + excess
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment
        )

        # Now pay more than the first and second-paid debts will
        # accomodate. The excess should go to the next-paid debt.
        payment = (
            self.min_payment({self.debt_big_high_interest}, strategy.timing) +
            self.max_payment(
                self.debts - {self.debt_big_high_interest}, strategy.timing) +
            excess
        )
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment + excess
        )

        # Now contribute more than the total max.
        payment = self.max_payment(self.debts, strategy.timing) + excess
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.max_inflow(strategy.timing))

    def test_strategy_avalanche(self):
        """ Test DebtPaymentStrategy.strategy_avalanche. """
        # Run each test on inflows and outflows
        method = DebtPaymentStrategy.strategy_avalanche
        strategy = DebtPaymentStrategy(method)

        # Try a simple scenario: The amount being contributed is equal
        # to the minimum payments for the accounts.
        min_payment = self.min_payment(self.debts, strategy.timing)
        excess = Money(0)
        payment = min_payment + excess
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

        # Try paying less than the minimum. Minimum should still be paid
        payment = Money(0)
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.minimum_payment)

        # Try paying a bit more than the minimum.
        # The highest-interest debt should be paid first.
        excess = Money(10)
        payment = min_payment + excess
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.minimum_payment + excess
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment
        )

        # Now pay more than the first-paid debt will accomodate.
        # The extra $50 should go to the next-paid debt (medium).
        payment = (
            self.min_payment(
                self.debts - {self.debt_big_high_interest}, strategy.timing) +
            self.max_payment({self.debt_big_high_interest}, strategy.timing) +
            excess
        )
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.minimum_payment + excess
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment
        )

        # Now pay more than the first and second-paid debts will
        # accomodate. The excess should go to the next-paid debt.
        payment = (
            self.min_payment({self.debt_small_low_interest}, strategy.timing) +
            self.max_payment(
                self.debts - {self.debt_small_low_interest}, strategy.timing) +
            excess
        )
        results = strategy(payment, self.debts)
        self.assertEqual(
            results[self.debt_big_high_interest],
            self.debt_big_high_interest.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_medium],
            self.debt_medium.max_inflow(strategy.timing)
        )
        self.assertEqual(
            results[self.debt_small_low_interest],
            self.debt_small_low_interest.minimum_payment + excess
        )

        # Now contribute more than the total max.
        payment = self.max_payment(self.debts, strategy.timing) + excess
        results = strategy(payment, self.debts)
        for debt in self.debts:
            self.assertEqual(results[debt], debt.max_inflow(strategy.timing))

if __name__ == '__main__':
    unittest.main()

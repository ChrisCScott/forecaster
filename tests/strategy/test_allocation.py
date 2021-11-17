""" Unit tests for `ContributionStrategy` and `WithdrawalStrategy`. """

import unittest
from decimal import Decimal
from forecaster import AllocationStrategy


class TestAllocationStrategyMethods(unittest.TestCase):
    """ A test case for the AllocationStrategy class """

    def setUp(self):
        # Provide default method/strategy for testing:
        self.method = AllocationStrategy.strategy_n_minus_age
        self.strategy = AllocationStrategy(self.method, 100)

    def test_init_default(self):
        """ Test AllocationStrategy.__init__ with default params."""
        # Arguments for AllocationStrategy are:
        # strategy (str, func)
        # min_equity (float)
        # max_equity (float)
        # target (float)
        # standard_retirement_age (int)
        # risk_transition_period (int)
        # adjust_for_retirement_plan (bool)

        # Test default init:
        method = AllocationStrategy.strategy_n_minus_age
        strategy = AllocationStrategy(method, 100)
        # pylint: disable=no-member
        self.assertEqual(strategy.strategy, method.strategy_key)
        self.assertAlmostEqual(strategy.min_equity, 0)
        self.assertAlmostEqual(strategy.max_equity, 1)
        # The default target varies depending on the strategy
        self.assertAlmostEqual(strategy.target, 100)
        self.assertAlmostEqual(strategy.standard_retirement_age, 65)
        self.assertAlmostEqual(strategy.risk_transition_period, 20)
        self.assertAlmostEqual(strategy.adjust_for_retirement_plan, True)

    def test_init_decimal(self):
        """ Test AllocationStrategy.__init__ with Decimal inputs."""
        # Arguments for AllocationStrategy are:
        # strategy (str, func)
        # min_equity (Decimal)
        # max_equity (Decimal)
        # target (Decimal)
        # standard_retirement_age (int)
        # risk_transition_period (int)
        # adjust_for_retirement_plan (bool)
        # Test explicit init:
        method = AllocationStrategy.strategy_n_minus_age
        min_equity = 0
        max_equity = 1
        target = '0.5'
        standard_retirement_age = 65.0
        risk_transition_period = '10'
        adjust_for_retirement_plan = 'Evaluates to True'
        strategy = AllocationStrategy(
            method, target, min_equity=min_equity, max_equity=max_equity,
            standard_retirement_age=standard_retirement_age,
            risk_transition_period=risk_transition_period,
            adjust_for_retirement_plan=adjust_for_retirement_plan,
            high_precision=Decimal)
        # Pylint misses this member, which is added by metaclass
        # pylint: disable=no-member
        self.assertEqual(strategy.strategy, method.strategy_key)
        # pylint: enable=no-member
        self.assertEqual(strategy.min_equity, Decimal(min_equity))
        self.assertEqual(strategy.max_equity, Decimal(max_equity))
        self.assertEqual(strategy.target, Decimal(target))
        self.assertEqual(strategy.standard_retirement_age,
                         int(standard_retirement_age))
        self.assertEqual(strategy.risk_transition_period,
                         int(risk_transition_period))
        self.assertEqual(strategy.adjust_for_retirement_plan,
                         bool(adjust_for_retirement_plan))

        # Type-check:
        self.assertIsInstance(strategy.strategy, str)
        self.assertIsInstance(strategy.min_equity, Decimal)
        self.assertIsInstance(strategy.max_equity, Decimal)
        self.assertIsInstance(strategy.target, Decimal)
        self.assertIsInstance(strategy.standard_retirement_age, int)
        self.assertIsInstance(strategy.risk_transition_period, int)
        self.assertIsInstance(strategy.adjust_for_retirement_plan, bool)

    def test_invalid_strategies(self):
        """ Tests that invalid strategies raise exceptions. """
        with self.assertRaises(ValueError):
            _ = AllocationStrategy(strategy='Not a strategy', target=1)

    def test_mismatched_thresholds(self):
        """ Tests mismatched min and max equity thresholds. """
        with self.assertRaises(ValueError):
            _ = AllocationStrategy(
                self.method, 1, min_equity=1, max_equity=0)

    def test_identical_thresholds(self):
        """ Test the min/max thresholds can be the same. """
        strategy = AllocationStrategy(
            self.method, 1, min_equity=0.5, max_equity=0.5)
        self.assertEqual(strategy.min_equity, strategy.max_equity)

    def test_strategy_n_minus_age(self):
        """ Test AllocationStrategy.strategy_n_minus_age. """
        method = AllocationStrategy.strategy_n_minus_age

        # Create a basic strategy that puts 100-age % into equity
        target = 100
        strategy = AllocationStrategy(
            method, target,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=False)

        # Test allocations for each age from birth to retirement:
        for age in range(0, target):
            self.assertAlmostEqual(
                strategy(age).stocks, (target - age) / 100)
            self.assertAlmostEqual(
                strategy(age).bonds, 1 - (target - age) / 100)
        # Test allocations for each age from retirement onward:
        for age in range(target, target + 100):
            self.assertAlmostEqual(strategy(age).stocks, strategy.min_equity)
            self.assertAlmostEqual(strategy(age).bonds, 1 - strategy.min_equity)

    def test_strategy_n_minus_age_dec(self):
        """ Test strategy_n_minus_age with Decimal inputs. """
        method = AllocationStrategy.strategy_n_minus_age

        # Create a basic strategy that puts 100-age % into equity
        target = 100
        strategy = AllocationStrategy(
            method, target,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=False,
            high_precision=Decimal)

        # Test allocations for each age from birth to retirement:
        for age in range(0, target):
            self.assertAlmostEqual(
                strategy(age).stocks, Decimal((target - age) / 100))
            self.assertAlmostEqual(
                strategy(age).bonds, Decimal(1 - (target - age) / 100))
        # Test allocations for each age from retirement onward:
        for age in range(target, target + 100):
            self.assertAlmostEqual(strategy(age).stocks, strategy.min_equity)
            self.assertAlmostEqual(strategy(age).bonds, 1 - strategy.min_equity)

    def test_strategy_n_minus_age_early(self):
        """ Test strategy_n_minus_age with early retirement. """
        method = AllocationStrategy.strategy_n_minus_age
        # Try with adjustments for retirement plans enabled.
        # Use n = 120, but a retirement age that's 20 years early.
        # After adjusting for retirement plans, the results should be
        # the same as in the above test
        target = 120
        standard_retirement_age = 65
        diff = -20
        retirement_age = standard_retirement_age + diff
        strategy = AllocationStrategy(
            method, target,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=True)

        for age in range(0, target + diff):
            self.assertAlmostEqual(
                strategy(age, retirement_age=retirement_age).stocks,
                (target + diff - age) / 100)
            self.assertAlmostEqual(
                strategy(age, retirement_age=retirement_age).bonds,
                1 - (target + diff - age) / 100)
        for age in range(target + diff, target + diff + 100):
            self.assertAlmostEqual(
                strategy(age, retirement_age=retirement_age).stocks,
                strategy.min_equity)
            self.assertAlmostEqual(
                strategy(age, retirement_age=retirement_age).bonds,
                1 - strategy.min_equity)

    def test_strategy_n_minus_age_unadj(self):
        """ Test strategy_n_minus_age with early retirement, unadjusted. """
        # Finally, try n=120 without adjusting the retirement age to
        # confirm that max_equity is respected.
        method = AllocationStrategy.strategy_n_minus_age
        target = 120
        standard_retirement_age = 65
        retirement_age = standard_retirement_age - 20
        strategy = AllocationStrategy(
            method, target,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=False)

        for age in range(0, 20):
            self.assertAlmostEqual(strategy(age).stocks, strategy.max_equity)
            self.assertAlmostEqual(strategy(age).bonds, 1 - strategy.max_equity)
        for age in range(20, target):
            self.assertAlmostEqual(
                strategy(age, retirement_age=retirement_age).stocks,
                (target - age) / 100)
            self.assertAlmostEqual(
                strategy(age, retirement_age=retirement_age).bonds,
                1 - (target - age) / 100)
        for age in range(target, target + 100):
            self.assertAlmostEqual(
                strategy(age, retirement_age=retirement_age).stocks,
                strategy.min_equity)
            self.assertAlmostEqual(
                strategy(age, retirement_age=retirement_age).bonds,
                1 - strategy.min_equity)

    def test_strategy_trans_to_const(self):
        """ Test AllocationStrategy.strategy_transition_to_constant. """
        method = AllocationStrategy.strategy_transition_to_const

        # Create a basic strategy that transitions from 100% stocks to
        # 50% stocks between the ages of 55 and 65.
        strategy = AllocationStrategy(
            method, 0.5,
            min_equity=0, max_equity=1, standard_retirement_age=65,
            risk_transition_period=10, adjust_for_retirement_plan=False)

        for age in range(18, 54):
            self.assertAlmostEqual(strategy(age).stocks, 1)
            self.assertAlmostEqual(strategy(age).bonds, 0)
        for age in range(55, 65):
            self.assertAlmostEqual(
                strategy(age).stocks,
                1 * (65 - age) / 10 + 0.5 * (age - 55) / 10)
            self.assertAlmostEqual(
                strategy(age).bonds,
                1 - (1 * (65 - age) / 10 + 0.5 * (age - 55) / 10))
        for age in range(66, 100):
            self.assertAlmostEqual(strategy(age).stocks, 0.5)
            self.assertAlmostEqual(strategy(age).bonds, 0.5)


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

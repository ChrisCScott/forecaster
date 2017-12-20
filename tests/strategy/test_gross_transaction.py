""" Unit tests for `ContributionStrategy` and `WithdrawalStrategy`. """

import unittest
import decimal
from decimal import Decimal
from random import Random
from forecaster import Money, ContributionStrategy, WithdrawalStrategy


class TestContributionStrategyMethods(unittest.TestCase):
    """ A test case for the ContributionStrategy class """

    @classmethod
    def setUpClass(cls):

        inflation_adjustments = {
            2000: Decimal(0.5),
            2001: Decimal(1),
            2002: Decimal(2)
        }

        @staticmethod
        def variable_inflation(year, base_year=None):
            """ Returns different inflation rates for different years. """
            if base_year is None:
                base_year = 2001
            # Store a convenient inflation_adjust function that returns
            # 50% for 2000, 100% for 2001, and 200% for 2002:
            return (
                inflation_adjustments[year] /
                inflation_adjustments[base_year]
            )

        # pylint: disable=unused-argument
        @staticmethod
        def constant_2x_inflation(year, base_year=None):
            """ Returns the same inflation rate for each year. """
            # A convenient inflation_adjust function that returns 200%
            # for any input (and doesn't require any particular `year`)
            return Decimal('2')

        cls.variable_inflation = variable_inflation
        cls.constant_2x_inflation = constant_2x_inflation

    def test_init(self):
        """ Test ContributionStrategy.__init__ """
        # Test default init:
        method = "Constant contribution"
        strategy = ContributionStrategy(method)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.base_amount, Money(0))
        self.assertEqual(strategy.rate, Decimal(0))
        self.assertEqual(strategy.refund_reinvestment_rate, Decimal(1))

        # Test explicit init:
        method = 'Constant contribution'
        base_amount = Money('1000')
        rate = Decimal('0.5')
        refund_reinvestment_rate = Decimal('0.5')
        inflation_adjust = self.constant_2x_inflation
        strategy = ContributionStrategy(
            strategy=method, base_amount=base_amount, rate=rate,
            refund_reinvestment_rate=refund_reinvestment_rate,
            inflation_adjust=inflation_adjust)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.base_amount, base_amount)
        self.assertEqual(strategy.rate, rate)
        self.assertEqual(
            strategy.refund_reinvestment_rate, refund_reinvestment_rate)
        self.assertEqual(strategy.inflation_adjust, inflation_adjust)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = ContributionStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            strategy = ContributionStrategy(strategy=1)
        # Test invalid base_amount
        with self.assertRaises(decimal.InvalidOperation):
            strategy = ContributionStrategy(strategy=method, base_amount='a')
        # Test invalid rate
        with self.assertRaises(decimal.InvalidOperation):
            strategy = ContributionStrategy(strategy=method, rate='a')
        # Test invalid refund_reinvestment_rate
        with self.assertRaises(decimal.InvalidOperation):
            strategy = ContributionStrategy(
                strategy=method, refund_reinvestment_rate='a')

    def test_strategy_const_contrib(self):
        """ Test ContributionStrategy.strategy_const_contribution. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy.strategy_const_contribution

        # Default strategy. Set to $1 constant contributions.
        strategy = ContributionStrategy(method, base_amount=Money(1))
        # Test all default parameters (no inflation adjustments here)
        self.assertEqual(strategy(), strategy.base_amount)
        # Test refunds ($1) and other income ($2), for a total of $3
        # plus the default contribution rate.
        self.assertEqual(
            strategy(refund=Money(1), other_contribution=Money(2)),
            Money(strategy.base_amount) +
            Money(1) * strategy.refund_reinvestment_rate +
            Money(2))
        # Test that changing net_income and gross_income has no effect
        self.assertEqual(
            strategy(
                refund=0, other_contribution=0, net_income=Money(100000),
                gross_income=Money(200000)
            ),
            Money(strategy.base_amount)
        )
        # Test different inflation_adjustments
        strategy = ContributionStrategy(
            strategy=method, inflation_adjust=self.variable_inflation)
        self.assertEqual(
            strategy(year=2000),
            Money(strategy.base_amount) * self.variable_inflation(2000)
        )
        self.assertEqual(
            strategy(year=2001),
            Money(strategy.base_amount) * self.variable_inflation(2001)
        )
        self.assertEqual(
            strategy(year=2002),
            Money(strategy.base_amount) * self.variable_inflation(2002)
        )

        # Customize some inputs
        base_amount = Money(500)
        rate = Decimal('0.5')
        refund_reinvestment_rate = 1
        strategy = ContributionStrategy(
            strategy=method, base_amount=base_amount, rate=rate,
            refund_reinvestment_rate=refund_reinvestment_rate)
        # Test all default parameters.
        self.assertEqual(strategy(), base_amount)
        # Test that changing net_income, gross_income have no effect on
        # a constant contribution:
        self.assertEqual(
            strategy(
                net_income=Money(100000), gross_income=Money(200000)
            ),
            base_amount)

    def test_strategy_const_living_exp(self):
        """ Test ContributionStrategy.strategy_const_living_expenses. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy.strategy_const_living_expenses

        # Default strategy
        strategy = ContributionStrategy(
            method, base_amount=Money(1000), inflation_adjust=lambda year:
            {2000: Decimal(0.5), 2001: Decimal(1), 2002: Decimal(2)}[year])
        excess = Money(1500)  # excess money (this is the contribution)
        net_income = strategy.base_amount + excess  # net income
        # This method requires net_income
        self.assertEqual(strategy(year=2001, net_income=net_income), excess)
        # Test that changing gross_income has no effect
        self.assertEqual(
            strategy(
                year=2001, net_income=net_income, gross_income=Money(20000)
            ),
            excess
        )

        # Test different inflation_adjustments for different years.
        # First, test nominal $2000 in a year where the inflation
        # adjustment is 50%. Our real-value $1000 living expenses is
        # reduced by 50% to $500 in nominal terms, leaving $2000 to
        # contribute.
        self.assertEqual(
            strategy(year=2000, net_income=Money(2500)), Money('2000'))
        # For 2002, the inflation adjustment is 200%, meaning that our
        # living expenses are $2000 nominally. For income of $2500
        # the contribution is now just $500
        self.assertEqual(
            strategy(year=2002, net_income=Money(2500)), Money('500'))
        # Test a lower net_income than the living standard:
        strategy = ContributionStrategy(method, Money(1000))
        self.assertEqual(strategy(year=2000, net_income=Money(500)), 0)

    def test_strategy_net_percent(self):
        """ Test ContributionStrategy.strategy_net_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy.strategy_net_percent

        # Default strategy
        strategy = ContributionStrategy(method)
        net_income = Money(1000)
        # This method requires net_income
        self.assertEqual(
            strategy(net_income=net_income), net_income * strategy.rate)
        # Test that changing gross_income has no effect
        self.assertEqual(
            strategy(net_income=net_income, gross_income=Money(20000)),
            net_income * strategy.rate
        )
        strategy = ContributionStrategy(
            strategy=method, inflation_adjust=self.variable_inflation)
        # Test different inflation_adjustments
        # (Since the net_income argument is nominal, inflation should
        # have no effect)
        self.assertEqual(
            strategy(net_income=net_income, year=2000),
            net_income * strategy.rate
        )
        self.assertEqual(
            strategy(net_income=net_income, year=2002),
            net_income * strategy.rate
        )

    def test_strategy_gross_percent(self):
        """ Test ContributionStrategy.strategy_gross_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = ContributionStrategy.strategy_gross_percent

        # Default strategy
        strategy = ContributionStrategy(method)
        gross_income = Money(1000)  # gross income
        # This method requires gross_income
        self.assertEqual(
            strategy(gross_income=gross_income),
            gross_income * strategy.rate
        )
        # Test that changing gross_income has no effect
        self.assertEqual(
            strategy(gross_income=gross_income, net_income=Money(20000)),
            gross_income * strategy.rate
        )
        # Test different inflation_adjustments
        # (Since the gross_income argument is nominal, inflation_adjustment
        # should have no effect)
        strategy = ContributionStrategy(
            strategy=method, inflation_adjust=self.variable_inflation)
        self.assertEqual(
            strategy(gross_income=gross_income, year=2000),
            gross_income * strategy.rate
        )
        self.assertEqual(
            strategy(gross_income=gross_income, year=2002),
            gross_income * strategy.rate
        )

    def test_strategy_earnings_percent(self):
        """ Test ContributionStrategy.strategy_earnings_percent. """
        method = ContributionStrategy.strategy_earnings_percent

        # Default strategy
        strategy = ContributionStrategy(
            method, inflation_adjust=self.variable_inflation)
        net_income = strategy.base_amount * 2
        # This method requires net_income
        # Also need to provide `year` because inflation_adjust needs it
        # (2001 is the year for which inflation adjustment is 1)
        self.assertEqual(
            strategy(net_income=net_income, year=2001),
            (net_income - strategy.base_amount) * strategy.rate
        )
        # Test that changing gross_income has no effect
        self.assertEqual(
            strategy(
                net_income=net_income, gross_income=Money(20000), year=2001),
            (net_income - strategy.base_amount) * strategy.rate
        )
        # Test different inflation_adjustments
        # (This should inflation_adjust base_amount)
        self.assertEqual(
            strategy(net_income=net_income, year=2000),
            (net_income - strategy.base_amount * Decimal(0.5)) * strategy.rate)
        self.assertEqual(
            strategy(net_income=net_income, year=2002),
            (net_income - strategy.base_amount * Decimal(2)) * strategy.rate)


class TestWithdrawalStrategyMethods(unittest.TestCase):
    """ A test case for the WithdrawalStrategy class """

    def setUp(self):
        """ Sets up TestWithdrawalStrategyMethods. """
        # Several methods use varying inflation adjustment figures.
        self.year_half = 1999  # -50% inflation (values halved) in this year
        self.year_1 = 2000  # baseline year; no inflation
        self.year_2 = 2001  # 100% inflation (values doubled) in this year
        self.year_10 = 2002  # Values multiplied by 10 in this year
        self.inflation_adjustment = {
            self.year_half: Decimal(0.5),
            self.year_1: Decimal(1),
            self.year_2: Decimal(2),
            self.year_10: Decimal(10)
        }

        def inflation_adjust(year, base_year=self.year_1):
            """ Returns inflation-adjustment factor between two years. """
            return (
                self.inflation_adjustment[year] /
                self.inflation_adjustment[base_year]
            )

        self.inflation_adjust = inflation_adjust

    def test_init(self):
        """ Test WithdrawalStrategy.__init__ """
        # Test default init:
        method = "Constant withdrawal"
        strategy = WithdrawalStrategy(method)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.rate, Decimal(0))
        self.assertEqual(strategy.base_amount, Money(0))
        self.assertEqual(strategy.timing, 'end')
        self.assertEqual(strategy.income_adjusted, False)

        # Test explicit init:
        method = 'Constant withdrawal'
        rate = Decimal('1000')
        base_amount = Decimal('500')
        timing = 'end'
        income_adjusted = True
        inflation_adjust = self.inflation_adjust
        strategy = WithdrawalStrategy(
            strategy=method, base_amount=base_amount, rate=rate,
            timing=timing, income_adjusted=income_adjusted,
            inflation_adjust=inflation_adjust
        )

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.rate, rate)
        self.assertEqual(strategy.base_amount, base_amount)
        self.assertEqual(strategy.timing, timing)
        self.assertEqual(strategy.income_adjusted, income_adjusted)
        self.assertEqual(strategy.inflation_adjust, inflation_adjust)

        # Test invalid strategies
        with self.assertRaises(ValueError):
            strategy = WithdrawalStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            strategy = WithdrawalStrategy(strategy=1)
        # Test invalid rate
        with self.assertRaises(decimal.InvalidOperation):
            strategy = WithdrawalStrategy(strategy=method, rate='a')
        # Test invalid base_amount
        with self.assertRaises(decimal.InvalidOperation):
            strategy = WithdrawalStrategy(strategy=method, base_amount='a')
        # Test invalid timing
        with self.assertRaises(ValueError):
            strategy = WithdrawalStrategy(strategy=method, timing='a')
        # No need to test bool-valued attributes - everything is
        # bool-convertible!

    def test_strategy_const_withdrawal(self):
        """ Test WithdrawalStrategy.strategy_const_withdrawal. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy.strategy_const_withdrawal

        # Default strategy
        strategy = WithdrawalStrategy(method, base_amount=Money(100))
        # Test all default parameters. (We don't need to provide any
        # inflation data since this instance is not inflation-adjusted.)
        self.assertEqual(strategy(), Money(100))

        # Test different inflation_adjustments
        strategy = WithdrawalStrategy(
            method, base_amount=Money(100),
            inflation_adjust=self.inflation_adjust)
        for year in self.inflation_adjustment:
            self.assertEqual(
                strategy(year=year),
                Money(strategy.base_amount) * self.inflation_adjustment[year]
            )

    def test_strategy_principal_percent(self):
        """ Test WithdrawalStrategy.strategy_principal_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy.strategy_principal_percent

        rand = Random()
        principal = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            principal[year] = Money(rand.randint(0, 100000000) / 100)

        strategy = WithdrawalStrategy(strategy=method, rate=0.5)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(
                strategy(
                    principal_history=principal,
                    retirement_year=retirement_year),
                Money(strategy.rate * principal[retirement_year]))

        # Test different inflation_adjustments
        strategy = WithdrawalStrategy(
            strategy=method, rate=0.5, inflation_adjust=self.inflation_adjust)
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            # For readability, we store the result of the strategy here
            # and perform separate tests below depending on whether or
            # not the plannee has retired yet:
            test_withdrawal = strategy(
                principal_history=principal,
                retirement_year=retirement_year,
                year=year
            )
            true_withdrawal = (
                Money(strategy.rate * principal[retirement_year]) *
                inflation_adjustment
            )
            if year <= retirement_year:  # Not retired. No withdrawals
                self.assertEqual(test_withdrawal, Money(0))
            else:  # Retired. Withdraw according to strategy.
                self.assertEqual(test_withdrawal, true_withdrawal)

    def test_strategy_net_percent(self):
        """ Test WithdrawalStrategy.strategy_net_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy.strategy_net_percent

        rand = Random()
        net_income = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            net_income[year] = Money(rand.randint(0, 100000000) / 100)

        strategy = WithdrawalStrategy(strategy=method, rate=0.5, base_amount=0)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(
                strategy(
                    net_income_history=net_income,
                    retirement_year=retirement_year),
                Money(strategy.rate * net_income[retirement_year]))

        # Test different inflation_adjustments
        strategy = WithdrawalStrategy(
            strategy=method, rate=0.5, base_amount=0,
            inflation_adjust=self.inflation_adjust)
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            # For readability, we store the result of the strategy here
            # and perform separate tests below depending on whether or
            # not the plannee has retired yet:
            test_withdrawal = strategy(
                net_income_history=net_income,
                retirement_year=retirement_year,
                year=year
            )
            true_withdrawal = Money(
                strategy.rate * net_income[retirement_year]
            ) * inflation_adjustment
            if year <= retirement_year:  # Not retired. No withdrawals
                self.assertEqual(test_withdrawal, Money(0))
            else:  # Retired. Withdraw according to strategy.
                self.assertEqual(test_withdrawal, true_withdrawal)

    def test_strategy_gross_percent(self):
        """ Test WithdrawalStrategy.strategy_gross_percent. """
        # Rather than hardcode the key, let's look it up here.
        method = WithdrawalStrategy.strategy_gross_percent

        rand = Random()
        gross_income = {}
        retirement_year = min(self.inflation_adjustment.keys())
        for year in self.inflation_adjustment:
            # Randomly generate values in [$0, $1000000.00]
            gross_income[year] = Money(rand.randint(0, 100000000) / 100)

        strategy = WithdrawalStrategy(method, rate=0.5, base_amount=0)
        # Test results for the simple, no-inflation/no-benefits case:
        for year in self.inflation_adjustment:
            self.assertEqual(
                strategy(
                    gross_income_history=gross_income,
                    retirement_year=retirement_year
                ),
                Money(strategy.rate * gross_income[retirement_year])
            )

        # Test different inflation_adjustments
        strategy = WithdrawalStrategy(
            strategy=method, rate=0.5, base_amount=0,
            inflation_adjust=self.inflation_adjust)
        for year in self.inflation_adjustment:
            # Determine the inflation between retirement_year and
            # the current year (since all figs. are in nominal terms)
            inflation_adjustment = self.inflation_adjustment[year] / \
                self.inflation_adjustment[retirement_year]
            # For readability, we store the result of the strategy here
            # and perform separate tests below depending on whether or
            # not the plannee has retired yet:
            test_withdrawal = strategy(
                gross_income_history=gross_income,
                retirement_year=retirement_year,
                year=year
            )
            true_withdrawal = Money(
                strategy.rate * gross_income[retirement_year]
            ) * inflation_adjustment
            if year <= retirement_year:  # Not retired. No withdrawals
                self.assertEqual(test_withdrawal, Money(0))
            else:  # Retired. Withdraw according to strategy.
                self.assertEqual(test_withdrawal, true_withdrawal)

    def test_call(self):
        """ Test __call__ logic (but not strategy-specific logic). """
        # Select a simple, constant withdrawal strategy.
        method = WithdrawalStrategy.strategy_const_withdrawal

        # Test other income. No inflation adjustment.
        strategy = WithdrawalStrategy(
            strategy=method, base_amount=Money(100), rate=0,
            timing='end', income_adjusted=True)
        # $0 benefits -> no change:
        self.assertEqual(strategy(other_income=Money(0)),
                         Money(strategy.base_amount))
        # $1 benefits -> $1 reduction
        self.assertEqual(strategy(other_income=Money(1)),
                         Money(strategy.base_amount) - Money(1))
        # Benefits = withdrawal rate -> $0 withdrawal
        self.assertEqual(strategy(other_income=Money(strategy.base_amount)),
                         Money(0))
        # Benefits > withdrawal rate -> $0 withdrawal
        self.assertEqual(
            strategy(other_income=Money(strategy.base_amount) + Money(1)),
            Money(0))

        # Re-run above tests, but this time with income_adjusted=False
        strategy = WithdrawalStrategy(
            strategy=method, base_amount=Money(100), rate=0, timing='end',
            income_adjusted=False)
        # In every case, there should be no change:
        self.assertEqual(strategy(Money(0)), Money(strategy.base_amount))
        self.assertEqual(strategy(Money(1)), Money(strategy.base_amount))
        self.assertEqual(
            strategy(Money(strategy.base_amount)),
            Money(strategy.base_amount))
        self.assertEqual(strategy(Money(strategy.base_amount) + Money(1)),
                         Money(strategy.base_amount))


if __name__ == '__main__':
    unittest.main()

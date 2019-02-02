""" Unit tests for `LivingExpensesStrategy` and `WithdrawalStrategy`. """

import unittest
import decimal
from decimal import Decimal
from random import Random
from forecaster import (
    Person, Money, Tax,
    LivingExpensesStrategy, WithdrawalStrategy)


class TestLivingExpensesStrategyMethods(unittest.TestCase):
    """ A test case for the LivingExpensesStrategy class """

    @classmethod
    def setUpClass(cls):
        """ Set up stock variables that won't be modified by tests. """
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

    def setUp(self):
        """ Set up stock variables which might be modified. """
        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Money(0): Decimal(0.5)}})
        # Set up people with $4000 gross income, $2000 net income:
        self.person1 = Person(
            initial_year = self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2001",  # next year
            gross_income=Money(1000),
            tax_treatment=tax,
            payment_frequency='BW')
        self.person2 = Person(
            initial_year = self.initial_year,
            name="Test 2",
            birth_date="1 January 1975",
            retirement_date="31 December 2001",  # next year
            gross_income=Money(3000),
            tax_treatment=tax,
            payment_frequency='BW')
        self.people = {self.person1, self.person2}

    def test_init(self):
        """ Test LivingExpensesStrategy.__init__ """
        # Test default init:
        method = "Constant contribution"
        strategy = LivingExpensesStrategy(method)

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
        strategy = LivingExpensesStrategy(
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
            strategy = LivingExpensesStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            strategy = LivingExpensesStrategy(strategy=1)
        # Test invalid base_amount
        with self.assertRaises(decimal.InvalidOperation):
            strategy = LivingExpensesStrategy(strategy=method, base_amount='a')
        # Test invalid rate
        with self.assertRaises(decimal.InvalidOperation):
            strategy = LivingExpensesStrategy(strategy=method, rate='a')
        # Test invalid refund_reinvestment_rate
        with self.assertRaises(decimal.InvalidOperation):
            strategy = LivingExpensesStrategy(
                strategy=method, refund_reinvestment_rate='a')

    def test_strategy_const_contrib(self):
        """ Test LivingExpensesStrategy.strategy_const_contribution. """
        # Rather than hardcode the key, let's look it up here.
        method = LivingExpensesStrategy.strategy_const_contribution

        # Default strategy. Set to $1 constant contributions.
        strategy = LivingExpensesStrategy(method, base_amount=Money(1))
        # Test all default parameters (no inflation adjustments here)
        self.assertEqual(
            strategy(people=self.people),
            sum(person.net_income for person in self.people) - strategy.base_amount)

    def test_const_contrib_inflation_adjust(self):
        """ Test inflation-adjusted constant contributions. """
        # Contribute $500/yr, leaving $1500/yr for living.
        method = LivingExpensesStrategy.strategy_const_contribution
        strategy = LivingExpensesStrategy(
            method, base_amount=Money(500), inflation_adjust=lambda year:
            {2000: Decimal(0.5), 2001: Decimal(1), 2002: Decimal(2)}[year])

        # Test different inflation_adjustments for different years.
        # 2000: the adjustment is 50% so $500 contribution is reduced
        # to $250, leaving $1750 for living expenses.
        self.assertEqual(
            strategy(people=self.people, year=2000), Money('1750'))
        # 2001: the adjustment is 100% so $500 contribution is
        # unchanged, leaving $1500 for living expenses.
        self.assertEqual(
            strategy(people=self.people, year=2001), Money('1500'))
        # 2002: the adjustment is 200% so $500 contribution is
        # increased to $1000, leaving $1000 for living expenses.
        self.assertEqual(
            strategy(people=self.people, year=2002), Money('1000'))

    def test_insufficient_income(self):
        """ Test a lower net income than the contribution rate. """
        # Try to contribute more than net income:
        method = LivingExpensesStrategy.strategy_const_contribution
        strategy = LivingExpensesStrategy(method, Money(2001))
        # Living expenses are $0 in this case, not -$1:
        self.assertEqual(strategy(people=self.people), 0)

    def test_strategy_const_living_exp(self):
        """ Test LivingExpensesStrategy.strategy_const_living_expenses. """
        # Rather than hardcode the key, let's look it up here.
        method = LivingExpensesStrategy.strategy_const_living_expenses

        # Contribute $1000 annually, regardless of income:
        strategy = LivingExpensesStrategy(
            method, base_amount=Money(1000))
        # This method requires net_income
        self.assertEqual(strategy(people=self.people), Money(1000))

    def test_const_living_exp_inflation_adjust(self):
        """ Test inflation-adjusted constant living expenses. """
        # Contribute $1000 every year, adjusted to inflation:
        method = LivingExpensesStrategy.strategy_const_living_expenses
        strategy = LivingExpensesStrategy(
            strategy=method, inflation_adjust=self.variable_inflation,
            base_amount=Money(1000))
        self.assertEqual(
            strategy(year=2000),
            strategy.base_amount * self.variable_inflation(2000)
        )
        self.assertEqual(
            strategy(year=2001),
            strategy.base_amount * self.variable_inflation(2001)
        )
        self.assertEqual(
            strategy(year=2002),
            strategy.base_amount * self.variable_inflation(2002)
        )

    def test_strategy_net_percent(self):
        """ Test LivingExpensesStrategy.strategy_net_percent. """
        # Live on 50% of net income:
        method = LivingExpensesStrategy.strategy_net_percent
        strategy = LivingExpensesStrategy(method, rate=0.5)
        net_income = sum(person.net_income for person in self.people)
        self.assertEqual(
            strategy(people=self.people),
            net_income * strategy.rate)

    def test_net_percent_inflation_adjust(self):
        """ Test inflation-adjusted net-percent living expenses. """
        # Live on 50% of net income, and also provide inflation-adjust:
        method = LivingExpensesStrategy.strategy_net_percent
        strategy = LivingExpensesStrategy(
            strategy=method, rate=0.5,
            inflation_adjust=self.variable_inflation)
        # Since net_income is nominal, inflation should have no effect:
        net_income = sum(person.net_income for person in self.people)
        self.assertEqual(
            strategy(people=self.people, year=2000),
            net_income * strategy.rate
        )
        self.assertEqual(
            strategy(people=self.people, year=2002),
            net_income * strategy.rate
        )

    def test_strategy_gross_percent(self):
        """ Test LivingExpensesStrategy.strategy_gross_percent. """
        # Live on 50% of gross income:
        method = LivingExpensesStrategy.strategy_gross_percent
        strategy = LivingExpensesStrategy(method, rate=0.5)
        gross_income = sum(person.gross_income for person in self.people)
        self.assertEqual(
            strategy(people=self.people),
            gross_income * strategy.rate)

    def test_gross_percent_inflation_adjust(self):
        """ Test inflation-adjusted gross-percent living expenses. """
        # Live on 50% of gross income, and also provide inflation-adjust:
        method = LivingExpensesStrategy.strategy_gross_percent
        strategy = LivingExpensesStrategy(
            strategy=method, rate=0.5,
            inflation_adjust=self.variable_inflation)
        # Since gross_income is nominal, inflation should have no effect:
        gross_income = sum(person.gross_income for person in self.people)
        self.assertEqual(
            strategy(people=self.people, year=2000),
            gross_income * strategy.rate
        )
        self.assertEqual(
            strategy(people=self.people, year=2002),
            gross_income * strategy.rate
        )

    def test_strategy_earnings_percent(self):
        """ Test LivingExpensesStrategy.strategy_earnings_percent. """
        # Live off the first $1000 plus 50% of amounts above that:
        method = LivingExpensesStrategy.strategy_earnings_percent
        strategy = LivingExpensesStrategy(
            method, base_amount=Money(1000), rate=0.5)
        # The test people earn $2000 net. They spend $1000 plus
        # another $500 for a total of $1500.
        self.assertEqual(
            strategy(people=self.people),
            Money(1500)
        )

    def test_earnings_percent_inflation_adjust(self):
        """ Test inflation-adjusted earnings-percent living expenses. """
        # Live off the first $1000 plus 50% of amounts above that:
        method = LivingExpensesStrategy.strategy_earnings_percent
        strategy = LivingExpensesStrategy(
            strategy=method, base_amount=Money(1000), rate=0.5,
            inflation_adjust=self.variable_inflation)
        # 2000: Adjustment is 50%, so live on $500 plus 50% of
        # remaining $1500 (i.e. $750) for a total of $1250:
        self.assertEqual(
            strategy(people=self.people, year=2000),
            Money(1250)
        )
        # 2001: Adjustment is 100%; should yield the usual $1500:
        self.assertEqual(
            strategy(people=self.people, year=2001),
            Money(1500)
        )
        # 2002: Adjustment is 200%, so live on $2000. That's all
        # of the net income, so the 50% rate doesn't apply:
        self.assertEqual(
            strategy(people=self.people, year=2002),
            Money(2000)
        )


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

    def test_init_default(self):
        """ Test WithdrawalStrategy.__init__ with default args """
        method = "Constant withdrawal"
        strategy = WithdrawalStrategy(method)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.rate, Decimal(0))
        self.assertEqual(strategy.base_amount, Money(0))
        self.assertEqual(strategy.timing, 'end')
        self.assertEqual(strategy.income_adjusted, False)

    def test_init_explicit(self):
        """ Test WithdrawalStrategy.__init__ with explicit args """
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

    def test_init_invalid(self):
        """ Test WithdrawalStrategy.__init__ with invalid args """
        method = 'Constant withdrawal'
        # Test invalid strategies
        with self.assertRaises(ValueError):
            _ = WithdrawalStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            _ = WithdrawalStrategy(strategy=1)
        # Test invalid rate
        with self.assertRaises(decimal.InvalidOperation):
            _ = WithdrawalStrategy(strategy=method, rate='a')
        # Test invalid base_amount
        with self.assertRaises(decimal.InvalidOperation):
            _ = WithdrawalStrategy(strategy=method, base_amount='a')
        # Test invalid timing
        with self.assertRaises(ValueError):
            _ = WithdrawalStrategy(strategy=method, timing='a')
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
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

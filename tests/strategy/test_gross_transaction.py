""" Unit tests for `LivingExpensesStrategy` and `LivingExpensesStrategy`. """

import unittest
import decimal
from decimal import Decimal
from random import Random
from forecaster import (
    Person, Money, Account, Tax, LivingExpensesStrategy)


class TestLivingExpensesStrategyMethods(unittest.TestCase):
    """ A test case for the LivingExpensesStrategy class """

    def setUp(self):
        """ Set up stock variables which might be modified. """
        # Set up inflation of various rates covering 1999-2002:
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

        # We need to provide a callable object that returns inflation
        # adjustments between years. Build that here:
        def variable_inflation(year, base_year=self.year_1):
            """ Returns inflation-adjustment factor between two years. """
            return (
                self.inflation_adjustment[year] /
                self.inflation_adjustment[base_year]
            )
        self.variable_inflation = variable_inflation

        # Build all the objects we need to build an instance of
        # `LivingExpensesStrategy`:
        self.initial_year = self.year_1
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

        # Give person1 a $1000 account and person2 a $9,000 account:
        self.account1 = Account(
            owner=self.person1,
            balance=Money(1000),
            rate=0)
        self.account2 = Account(
            owner=self.person2,
            balance=Money(9000),
            rate=0)

    def test_init(self):
        """ Test LivingExpensesStrategy.__init__ """
        # Test default init:
        method = "Constant contribution"
        strategy = LivingExpensesStrategy(method)

        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.base_amount, Money(0))
        self.assertEqual(strategy.rate, Decimal(0))

        # Test explicit init:
        method = 'Constant contribution'
        base_amount = Money('1000')
        rate = Decimal('0.5')
        inflation_adjust = self.variable_inflation
        strategy = LivingExpensesStrategy(
            strategy=method, base_amount=base_amount, rate=rate,
            inflation_adjust=inflation_adjust)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.base_amount, base_amount)
        self.assertEqual(strategy.rate, rate)
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
        method = LivingExpensesStrategy.strategy_percent_over_base
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
        method = LivingExpensesStrategy.strategy_percent_over_base
        strategy = LivingExpensesStrategy(
            strategy=method, base_amount=Money(1000), rate=0.5,
            inflation_adjust=self.variable_inflation)
        # 1999: Adjustment is 50%, so live on $500 plus 50% of
        # remaining $1500 (i.e. $750) for a total of $1250:
        self.assertEqual(
            strategy(people=self.people, year=self.year_half),
            Money(1250)
        )
        # 2000: Adjustment is 100%; should yield the usual $1500:
        self.assertEqual(
            strategy(people=self.people, year=self.year_1),
            Money(1500)
        )
        # 2001: Adjustment is 200%, so live on $2000. That's all
        # of the net income, so the 50% rate doesn't apply:
        self.assertEqual(
            strategy(people=self.people, year=self.year_2),
            Money(2000)
        )

    def test_strategy_principal_percent_retirement(self):
        """ Test LivingExpensesStrategy.strategy_principal_percent_retirement. """
        # Live off of 50% of the principal balance at retirement:
        method = LivingExpensesStrategy.strategy_principal_percent_retirement
        strategy = LivingExpensesStrategy(strategy=method, rate=0.5)

        # Retire in this year and advance to next year:
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()

        principal = self.account1.balance + self.account2.balance
        self.assertEqual(
            strategy(
                people=self.people,
                year=year,
                retirement_year=retirement_year),
            strategy.rate * principal)

    def test_strategy_principal_percent_retirement_inflation(self):
        """ Test inflation-adjustment when living on principal. """
        # Live off of 50% of the principal balance at retirement,
        # adjusted to inflation:
        method = LivingExpensesStrategy.strategy_principal_percent_retirement
        strategy = LivingExpensesStrategy(
            strategy=method, rate=0.5, inflation_adjust=self.variable_inflation)

        # Retire in this year and advance to next year:
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()

        # Determine the inflation between retirement_year and
        # the current year (since all figs. are in nominal terms)
        inflation_adjustment = self.variable_inflation(
            year, base_year=retirement_year)
        principal = self.account1.balance + self.account2.balance

        self.assertEqual(
            strategy(
                people=self.people, year=year,
                retirement_year=retirement_year),
            strategy.rate * principal * inflation_adjustment
        )

    def test_strategy_net_percent_retirement(self):
        """ Test LivingExpensesStrategy.strategy_net_percent_retirement. """
        # Live off of 50% of net income at retirement:
        method = LivingExpensesStrategy.strategy_net_percent_retirement
        strategy = LivingExpensesStrategy(strategy=method, rate=0.5)

        # Retire in this year, advance to next year, set income to $0
        # (record income first, since this is the year that matters):
        net_income = sum(person.net_income for person in self.people)
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()
            person.gross_income = Money(0)
            person.net_income = Money(0)

        self.assertEqual(
            strategy(
                people=self.people,
                year=year,
                retirement_year=retirement_year),
            strategy.rate * net_income)

    def test_strategy_net_percent_retirement_inflation(self):
        """ Test inflation-adjustment when living on net income. """
        # Live off of 50% of net income at retirement,
        # adjusted to inflation:
        method = LivingExpensesStrategy.strategy_net_percent_retirement
        strategy = LivingExpensesStrategy(
            strategy=method, rate=0.5, inflation_adjust=self.variable_inflation)

        # Retire in this year, advance to next year, set income to $0
        # (record income first, since this is the year that matters):
        net_income = sum(person.net_income for person in self.people)
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()
            person.gross_income = Money(0)
            person.net_income = Money(0)

        # Determine the inflation between retirement_year and
        # the current year (since all figs. are in nominal terms)
        inflation_adjustment = self.variable_inflation(
            year, base_year=retirement_year)

        self.assertEqual(
            strategy(
                people=self.people, year=year,
                retirement_year=retirement_year),
            strategy.rate * net_income * inflation_adjustment
        )

    def test_strategy_gross_percent_retirement(self):
        """ Test LivingExpensesStrategy.strategy_gross_percent_retirement. """
        # Live off of 50% of gross income at retirement:
        method = LivingExpensesStrategy.strategy_gross_percent_retirement
        strategy = LivingExpensesStrategy(strategy=method, rate=0.5)

        # Retire in this year, advance to next year, set income to $0
        # (record income first, since this is the year that matters):
        gross_income = sum(person.gross_income for person in self.people)
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()
            person.gross_income = Money(0)
            person.net_income = Money(0)

        self.assertEqual(
            strategy(
                people=self.people,
                year=year,
                retirement_year=retirement_year),
            strategy.rate * gross_income)

    def test_strategy_gross_percent_retirement_inflation(self):
        """ Test inflation-adjustment when living on gross income. """
        # Live off of 50% of gross income at retirement,
        # adjusted to inflation:
        method = LivingExpensesStrategy.strategy_gross_percent_retirement
        strategy = LivingExpensesStrategy(
            strategy=method, rate=0.5, inflation_adjust=self.variable_inflation)

        # Retire in this year, advance to next year, set income to $0
        # (record income first, since this is the year that matters):
        gross_income = sum(person.gross_income for person in self.people)
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()
            person.gross_income = Money(0)
            person.net_income = Money(0)

        # Determine the inflation between retirement_year and
        # the current year (since all figs. are in nominal terms)
        inflation_adjustment = self.variable_inflation(
            year, base_year=retirement_year)

        self.assertEqual(
            strategy(
                people=self.people, year=year,
                retirement_year=retirement_year),
            strategy.rate * gross_income * inflation_adjustment
        )


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

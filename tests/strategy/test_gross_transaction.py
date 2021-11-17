""" Unit tests for `LivingExpensesStrategy` and `LivingExpensesStrategy`. """

import unittest
from decimal import Decimal
from forecaster import (
    Person, Account, Tax,
    LivingExpensesStrategy, LivingExpensesStrategySchedule,
    Timing)


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
            self.year_half: 0.5,
            self.year_1: 1,
            self.year_2: 2,
            self.year_10: 10}

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
            self.initial_year: {0: 0.5}})
        # Set up people with $4000 gross income, $2000 net income:
        biweekly_timing = Timing(frequency="BW")
        self.person1 = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2001",  # next year
            gross_income=1000,
            tax_treatment=tax,
            payment_timing=biweekly_timing)
        self.person2 = Person(
            initial_year=self.initial_year,
            name="Test 2",
            birth_date="1 January 1975",
            retirement_date="31 December 2001",  # next year
            gross_income=3000,
            tax_treatment=tax,
            payment_timing=biweekly_timing)
        self.people = {self.person1, self.person2}

        # Give person1 a $1000 account and person2 a $9,000 account:
        self.account1 = Account(
            owner=self.person1,
            balance=1000,
            rate=0)
        self.account2 = Account(
            owner=self.person2,
            balance=9000,
            rate=0)

    def setUp_decimal(self):
        """ Set up stock variables based on Decimal inputs. """
        # Set up inflation of various rates covering 1999-2002:
        self.year_half = 1999  # -50% inflation (values halved) in this year
        self.year_1 = 2000  # baseline year; no inflation
        self.year_2 = 2001  # 100% inflation (values doubled) in this year
        self.year_10 = 2002  # Values multiplied by 10 in this year
        self.inflation_adjustment = {
            self.year_half: Decimal(0.5),
            self.year_1: Decimal(1),
            self.year_2: Decimal(2),
            self.year_10: Decimal(10)}

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
            self.initial_year: {Decimal(0): Decimal(0.5)}})
        # Set up people with $4000 gross income, $2000 net income:
        biweekly_timing = Timing(frequency="BW")
        self.person1 = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2001",  # next year
            gross_income=Decimal(1000),
            tax_treatment=tax,
            payment_timing=biweekly_timing)
        self.person2 = Person(
            initial_year=self.initial_year,
            name="Test 2",
            birth_date="1 January 1975",
            retirement_date="31 December 2001",  # next year
            gross_income=Decimal(3000),
            tax_treatment=tax,
            payment_timing=biweekly_timing)
        self.people = {self.person1, self.person2}

        # Give person1 a $1000 account and person2 a $9,000 account:
        self.account1 = Account(
            owner=self.person1,
            balance=Decimal(1000),
            rate=0)
        self.account2 = Account(
            owner=self.person2,
            balance=Decimal(9000),
            rate=0)

    def test_init_default(self):
        """ Test LivingExpensesStrategy.__init__ with default args."""
        # Test default init:
        method = "Constant contribution"
        strategy = LivingExpensesStrategy(method)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.base_amount, 0)
        self.assertEqual(strategy.rate, 0)

    def test_init_decimal(self):
        """ Tests init with Decimal inputs. """
        method = 'Constant contribution'
        base_amount = Decimal(1000)
        rate = Decimal(0.5)
        def inflation_adjust(year, base_year=self.year_1):
            return Decimal(self.variable_inflation(year,base_year=base_year))
        strategy = LivingExpensesStrategy(
            strategy=method, base_amount=base_amount, rate=rate,
            inflation_adjust=inflation_adjust)
        self.assertEqual(strategy.strategy, method)
        self.assertEqual(strategy.base_amount, base_amount)
        self.assertEqual(strategy.rate, rate)
        self.assertEqual(strategy.inflation_adjust, inflation_adjust)

    def test_invalid_strategies(self):
        """ Tests invalid strategies. """
        with self.assertRaises(ValueError):
            _ = LivingExpensesStrategy(strategy='Not a strategy')
        with self.assertRaises(TypeError):
            _ = LivingExpensesStrategy(strategy=1)

    def test_strategy_const_contrib(self):
        """ Test LivingExpensesStrategy.strategy_const_contribution. """
        # Rather than hardcode the key, let's look it up here.
        method = LivingExpensesStrategy.strategy_const_contribution

        # Default strategy. Set to $1 constant contributions.
        strategy = LivingExpensesStrategy(method, base_amount=1)
        # Test all default parameters (no inflation adjustments here)
        self.assertAlmostEqual(
            strategy(people=self.people),
            sum(person.net_income for person in self.people)
            - strategy.base_amount)

    def test_const_contrib_inf(self):
        """ Test inflation-adjusted constant contributions. """
        # Contribute $500/yr, leaving $1500/yr for living.
        method = LivingExpensesStrategy.strategy_const_contribution
        strategy = LivingExpensesStrategy(
            method, base_amount=500, inflation_adjust=lambda year:
            {2000: 0.5, 2001: 1, 2002: 2}[year])

        # Test different inflation_adjustments for different years.
        # 2000: the adjustment is 50% so $500 contribution is reduced
        # to $250, leaving $1750 for living expenses.
        self.assertAlmostEqual(
            strategy(people=self.people, year=2000), 1750)
        # 2001: the adjustment is 100% so $500 contribution is
        # unchanged, leaving $1500 for living expenses.
        self.assertAlmostEqual(
            strategy(people=self.people, year=2001), 1500)
        # 2002: the adjustment is 200% so $500 contribution is
        # increased to $1000, leaving $1000 for living expenses.
        self.assertAlmostEqual(
            strategy(people=self.people, year=2002), 1000)

    def test_decimal_inputs(self):
        """ Test LivingExpensesStrategy with Decimal inputs. """
        # This is based on test_const_contrib_inf, with inputs
        # converted to Decimal.

        # Convert values to Decimal:
        self.setUp_decimal()

        # Contribute $250/yr in the first year and double it each year:
        method = LivingExpensesStrategy.strategy_const_contribution
        inflation_schedule = {
            2000: Decimal(0.5),
            2001: Decimal(1),
            2002: Decimal(2)}
        strategy = LivingExpensesStrategy(
            method, base_amount=Decimal(500),
            inflation_adjust=lambda year: inflation_schedule[year])

        # In 2000, contribute $250, leaving $1750 for living expenses.
        self.assertEqual(
            strategy(people=self.people, year=2000), Decimal(1750))
        # 2001: the adjustment is 100% so $500 contribution is
        # unchanged, leaving $1500 for living expenses.
        self.assertEqual(
            strategy(people=self.people, year=2001), Decimal(1500))
        # 2002: the adjustment is 200% so $500 contribution is
        # increased to $1000, leaving $1000 for living expenses.
        self.assertEqual(
            strategy(people=self.people, year=2002), Decimal(1000))

    def test_insufficient_income(self):
        """ Test a lower net income than the contribution rate. """
        # Try to contribute more than net income:
        method = LivingExpensesStrategy.strategy_const_contribution
        strategy = LivingExpensesStrategy(method, 2001)
        # Living expenses are $0 in this case, not -$1:
        self.assertEqual(strategy(people=self.people), 0)

    def test_strategy_const_living_exp(self):
        """ Test LivingExpensesStrategy.strategy_const_living_expenses. """
        # Rather than hardcode the key, let's look it up here.
        method = LivingExpensesStrategy.strategy_const_living_expenses

        # Contribute $1000 annually, regardless of income:
        strategy = LivingExpensesStrategy(
            method, base_amount=1000)
        # This method requires net_income
        self.assertEqual(strategy(people=self.people), 1000)

    def test_const_living_exp_inf(self):
        """ Test inflation-adjusted constant living expenses. """
        # Contribute $1000 every year, adjusted to inflation:
        method = LivingExpensesStrategy.strategy_const_living_expenses
        strategy = LivingExpensesStrategy(
            strategy=method, inflation_adjust=self.variable_inflation,
            base_amount=1000)
        self.assertEqual(
            strategy(year=2000),
            strategy.base_amount * self.variable_inflation(2000))
        self.assertEqual(
            strategy(year=2001),
            strategy.base_amount * self.variable_inflation(2001))
        self.assertEqual(
            strategy(year=2002),
            strategy.base_amount * self.variable_inflation(2002))

    def test_strategy_net_percent(self):
        """ Test LivingExpensesStrategy.strategy_net_percent. """
        # Live on 50% of net income:
        method = LivingExpensesStrategy.strategy_net_percent
        strategy = LivingExpensesStrategy(method, rate=0.5)
        net_income = sum(person.net_income for person in self.people)
        self.assertEqual(
            strategy(people=self.people),
            net_income * strategy.rate)

    def test_net_percent_inf(self):
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
            net_income * strategy.rate)
        self.assertEqual(
            strategy(people=self.people, year=2002),
            net_income * strategy.rate)

    def test_strategy_gross_percent(self):
        """ Test living off percentage of gross income. """
        # Live on 50% of gross income:
        method = LivingExpensesStrategy.strategy_gross_percent
        strategy = LivingExpensesStrategy(method, rate=0.5)
        gross_income = sum(person.gross_income for person in self.people)
        self.assertEqual(
            strategy(people=self.people),
            gross_income * strategy.rate)

    def test_gross_percent_inf(self):
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
            gross_income * strategy.rate)
        self.assertEqual(
            strategy(people=self.people, year=2002),
            gross_income * strategy.rate)

    def test_strategy_earnings_percent(self):
        """ Test living off of percentage of earnings over a base amount. """
        # Live off the first $1000 plus 50% of amounts above that:
        method = LivingExpensesStrategy.strategy_percent_over_base
        strategy = LivingExpensesStrategy(
            method, base_amount=1000, rate=0.5)
        # The test people earn $2000 net. They spend $1000 plus
        # another $500 for a total of $1500.
        self.assertEqual(
            strategy(people=self.people), 1500)

    def test_earnings_percent_inf(self):
        """ Test inflation-adjusted earnings-percent living expenses. """
        # Live off the first $1000 plus 50% of amounts above that:
        method = LivingExpensesStrategy.strategy_percent_over_base
        strategy = LivingExpensesStrategy(
            strategy=method, base_amount=1000, rate=0.5,
            inflation_adjust=self.variable_inflation)
        # 1999: Adjustment is 50%, so live on $500 plus 50% of
        # remaining $1500 (i.e. $750) for a total of $1250:
        self.assertAlmostEqual(
            strategy(people=self.people, year=self.year_half),
            1250)
        # 2000: Adjustment is 100%; should yield the usual $1500:
        self.assertAlmostEqual(
            strategy(people=self.people, year=self.year_1), 1500)
        # 2001: Adjustment is 200%, so live on $2000. That's all
        # of the net income, so the 50% rate doesn't apply:
        self.assertAlmostEqual(
            strategy(people=self.people, year=self.year_2), 2000)

    def test_strategy_principal_pct_ret(self):
        """ Test living off of percentage of principal at retirement. """
        # Live off of 50% of the principal balance at retirement:
        method = LivingExpensesStrategy.strategy_principal_percent_ret
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

    def test_strategy_princ_pct_ret_inf(self):
        """ Test inflation-adjustment when living on principal. """
        # Live off of 50% of the principal balance at retirement,
        # adjusted to inflation:
        method = LivingExpensesStrategy.strategy_principal_percent_ret
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
            strategy.rate * principal * inflation_adjustment)

    def test_strategy_net_pct_ret(self):
        """ Test living off of a percentage of net income at retirement. """
        # Live off of 50% of net income at retirement:
        method = LivingExpensesStrategy.strategy_net_percent_ret
        strategy = LivingExpensesStrategy(strategy=method, rate=0.5)

        # Retire in this year, advance to next year, set income to $0
        # (record income first, since this is the year that matters):
        net_income = sum(person.net_income for person in self.people)
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()
            person.gross_income = 0
            person.net_income = 0

        self.assertEqual(
            strategy(
                people=self.people,
                year=year,
                retirement_year=retirement_year),
            strategy.rate * net_income)

    def test_strategy_net_pct_ret_inf(self):
        """ Test inflation-adjustment when living on net income. """
        # Live off of 50% of net income at retirement,
        # adjusted to inflation:
        method = LivingExpensesStrategy.strategy_net_percent_ret
        strategy = LivingExpensesStrategy(
            strategy=method, rate=0.5, inflation_adjust=self.variable_inflation)

        # Retire in this year, advance to next year, set income to $0
        # (record income first, since this is the year that matters):
        net_income = sum(person.net_income for person in self.people)
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()
            person.gross_income = 0
            person.net_income = 0

        # Determine the inflation between retirement_year and
        # the current year (since all figs. are in nominal terms)
        inflation_adjustment = self.variable_inflation(
            year, base_year=retirement_year)

        self.assertEqual(
            strategy(
                people=self.people, year=year,
                retirement_year=retirement_year),
            strategy.rate * net_income * inflation_adjustment)

    def test_strategy_gross_pct_ret(self):
        """ Test living off of gross income at retirement. """
        # Live off of 50% of gross income at retirement:
        method = LivingExpensesStrategy.strategy_gross_percent_ret
        strategy = LivingExpensesStrategy(strategy=method, rate=0.5)

        # Retire in this year, advance to next year, set income to $0
        # (record income first, since this is the year that matters):
        gross_income = sum(person.gross_income for person in self.people)
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()
            person.gross_income = 0
            person.net_income = 0

        self.assertEqual(
            strategy(
                people=self.people,
                year=year,
                retirement_year=retirement_year),
            strategy.rate * gross_income)

    def test_strategy_gross_pct_ret_inf(self):
        """ Test inflation-adjustment when living on gross income. """
        # Live off of 50% of gross income at retirement,
        # adjusted to inflation:
        method = LivingExpensesStrategy.strategy_gross_percent_ret
        strategy = LivingExpensesStrategy(
            strategy=method, rate=0.5, inflation_adjust=self.variable_inflation)

        # Retire in this year, advance to next year, set income to $0
        # (record income first, since this is the year that matters):
        gross_income = sum(person.gross_income for person in self.people)
        retirement_year = self.initial_year
        year = retirement_year + 1
        for person in self.people:
            person.next_year()
            person.gross_income = 0
            person.net_income = 0

        # Determine the inflation between retirement_year and
        # the current year (since all figs. are in nominal terms)
        inflation_adjustment = self.variable_inflation(
            year, base_year=retirement_year)

        self.assertEqual(
            strategy(
                people=self.people, year=year,
                retirement_year=retirement_year),
            strategy.rate * gross_income * inflation_adjustment)


class TestLivingExpensesStrategyScheduleMethods(unittest.TestCase):
    """ A test case for the LivingExpensesStrategySchedule class """

    def setUp(self):
        """ Set up stock variables for testing. """
        self.initial_year = 2000
        # Live on $24000/yr while working and $12000/yr in retirement:
        self.working = LivingExpensesStrategy(
            LivingExpensesStrategy.strategy_const_living_expenses,
            base_amount=24000)
        self.retirement = LivingExpensesStrategy(
            LivingExpensesStrategy.strategy_const_living_expenses,
            base_amount=12000)
        self.strategy = LivingExpensesStrategySchedule(
            self.working, self.retirement)

        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {0: 0.5}})
        # Set up a person with $50000 gross income, $2000 net income:
        self.person1 = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2001",  # next year
            gross_income=50000,
            tax_treatment=tax,
            payment_timing=Timing(frequency="BW"))
        self.people = {self.person1}

    def setUp_decimal(self):
        """ Set up stock variables with Decimal inputs. """
        self.initial_year = 2000
        # Live on $24000/yr while working and $12000/yr in retirement:
        self.working = LivingExpensesStrategy(
            LivingExpensesStrategy.strategy_const_living_expenses,
            base_amount=Decimal(24000))
        self.retirement = LivingExpensesStrategy(
            LivingExpensesStrategy.strategy_const_living_expenses,
            base_amount=Decimal(12000))
        self.strategy = LivingExpensesStrategySchedule(
            self.working, self.retirement)

        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Decimal(0): Decimal(0.5)}})
        # Set up a person with $50000 gross income, $2000 net income:
        self.person1 = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2001",  # next year
            gross_income=Decimal(50000),
            tax_treatment=tax,
            payment_timing=Timing(frequency="BW"))
        self.people = {self.person1}

    def test_working(self):
        """ Test working-age living expenses. """
        self.assertEqual(
            self.strategy(year=2000, retirement_year=2001, people=self.people),
            24000)

    def test_retirement(self):
        """ Test retirement-age living expenses. """
        self.assertEqual(
            self.strategy(year=2001, retirement_year=2000, people=self.people),
            12000)

    def test_minimum(self):
        """ Test minimum living expenses. """
        self.strategy.minimum = LivingExpensesStrategy(
            LivingExpensesStrategy.strategy_const_living_expenses,
            base_amount=18000)
        self.assertEqual(
            self.strategy(year=2001, retirement_year=2000, people=self.people),
            18000)

    def test_decimal(self):
        """ Test living expenses with Decimal inputs. """
        # Convert values to Decimal:
        self.setUp_decimal()
        self.assertEqual(
            self.strategy(year=2000, retirement_year=2001, people=self.people),
            Decimal(24000))

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

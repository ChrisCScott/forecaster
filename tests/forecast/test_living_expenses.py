""" Unit tests for `LivingExpensesForecast`. """

import unittest
from decimal import Decimal
from forecaster import (
    Person, LivingExpensesForecast,
    LivingExpensesStrategy, Tax, Timing)


class TestLivingExpensesForecast(unittest.TestCase):
    """ Tests LivingExpensesForecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Decimal(0): Decimal(0.5)}})
        # A person who is paid $200 gross ($100 net) every 2 weeks:
        timing = Timing(frequency='BW')
        self.person1 = Person(
            initial_year=self.initial_year,
            name="Test 1",
            birth_date="1 January 1980",
            retirement_date="31 December 2045",
            gross_income=Decimal(5200),
            tax_treatment=tax,
            payment_timing=timing)
        # A person who is paid $100 gross ($50 net) every 2 weeks:
        self.person2 = Person(
            initial_year=self.initial_year,
            name="Test 2",
            birth_date="1 January 1982",
            retirement_date="31 December 2047",
            gross_income=Decimal(2600),
            tax_treatment=tax,
            payment_timing=timing)
        # Track inflows from employment:
        self.available = {
            Decimal(0.5 + i) / 26: Decimal(150)
            for i in range(26)}
        self.total_available = sum(self.available.values())
        # Contribute 50% of net income (i.e. $3900):
        self.strategy = LivingExpensesStrategy(
            strategy=LivingExpensesStrategy.strategy_gross_percent,
            rate=0.5)
        self.forecast = LivingExpensesForecast(
            initial_year=self.initial_year,
            people={self.person1, self.person2},
            living_expenses_strategy=self.strategy)

    def test_living_gross_percent(self):
        """ Test living expenses based on percent of gross income. """
        # Contribute 50% of gross income:
        self.strategy = LivingExpensesStrategy(
            strategy=LivingExpensesStrategy.strategy_gross_percent,
            rate=0.5)
        self.forecast.living_expenses_strategy = self.strategy

        # It's not necessary to record inflows from employment,
        # but since this is usually how it'll be called we do
        # so here:
        self.forecast(self.available)

        # Calculate manually and compare results:
        living_expenses = (
            self.person1.gross_income + self.person2.gross_income) / 2
        self.assertEqual(
            living_expenses,
            self.forecast.living_expenses)

    def test_living_net_percent(self):
        """ Test living expenses based on percent of net income. """
        # Contribute 50% of net income:
        self.strategy = LivingExpensesStrategy(
            strategy=LivingExpensesStrategy.strategy_net_percent,
            rate=0.5)
        self.forecast.living_expenses_strategy = self.strategy

        # It's not necessary to record inflows from employment,
        # but since this is usually how it'll be called we do
        # so here:
        self.forecast(self.available)

        # Calculate manually and compare results:
        living_expenses = (
            self.person1.net_income + self.person2.net_income) / 2
        self.assertEqual(
            living_expenses,
            self.forecast.living_expenses)

    def test_living_const_contrib(self):
        """ Test living expenses based on constant contribution. """
        # Contribute $100 and live off the rest:
        self.strategy = LivingExpensesStrategy(
            strategy=LivingExpensesStrategy.strategy_const_contribution,
            base_amount=Decimal(100))
        self.forecast.living_expenses_strategy = self.strategy

        # It _is_ necessary to record inflows from employment
        # for this strategy:
        self.forecast(self.available)

        # Calculate manually and compare results:
        living_expenses = self.total_available - Decimal(100)
        self.assertEqual(
            living_expenses,
            self.forecast.living_expenses)

    def test_living_const_living(self):
        """ Test living expenses based on constant living expenses. """
        # Live off of $1200/yr:
        self.strategy = LivingExpensesStrategy(
            strategy=LivingExpensesStrategy.strategy_const_living_expenses,
            base_amount=Decimal(1200))
        self.forecast.living_expenses_strategy = self.strategy

        # It's not necessary to record inflows from employment,
        # but since this is usually how it'll be called we do
        # so here:
        self.forecast(self.available)

        # Calculate manually and compare results:
        living_expenses = Decimal(1200)
        self.assertEqual(
            living_expenses,
            self.forecast.living_expenses)

    def test_living_earnings_pct(self):
        """ Test living expenses based on percentage of raises. """
        # Live off of $1200/yr:
        self.strategy = LivingExpensesStrategy(
            strategy=LivingExpensesStrategy.strategy_percent_over_base,
            base_amount=Decimal(1200))
        self.forecast.living_expenses_strategy = self.strategy

        # It's not necessary to record inflows from employment,
        # but since this is usually how it'll be called we do
        # so here:
        self.forecast(self.available)

        # Calculate manually and compare results:
        living_expenses = Decimal(1200)
        self.assertEqual(
            living_expenses,
            self.forecast.living_expenses)

    def test_update_available(self):
        """ Test recording of cash inflows from living expenses. """
        self.forecast(self.available)
        # There should $3900 in living expenses deducted from $7800 in
        # net income, for net available of $3900.
        self.assertAlmostEqual(
            sum(self.forecast.transactions[self.available].values()),
            Decimal(-3900),
            places=2)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

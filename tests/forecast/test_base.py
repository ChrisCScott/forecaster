""" Unit tests for `Forecast`. """

import unittest
from copy import copy
from decimal import Decimal
from forecaster import (
    Money, Person, Forecast, Tax, Scenario, Timing,
    Account, TransactionTraversal, SavingForecast)

class DummyForecast(object):
    """ Acts like a SubForecast but is easier to debug with. """
    def __init__(self, initial_year, transactions=None):
        """ Inits DummyForecast.

        This class simply adds `transactions` to `available` when
        `update_available` is called (and stores copies of `available`
        before and after doing so, for debugging purposes). This
        lets you provide known behaviour to a SubForecast-like
        object for testing.

        Args:
            transactions (dict[Decimal, Money]): A mapping of
                `{when: value}` pairs that are added to
                `available` whenever `update_available` is called.
        """
        if transactions is None:
            transactions = {}
        self.transactions = transactions
        self.available_in = None
        self.available_out = None
        self.initial_year = initial_year
        self.this_year = initial_year

    def __call__(self, available):
        """ Adds transactions to `available`. """
        self.available_in = copy(available)
        for when, value in self.transactions.items():
            available[when] += value
        self.available_out = copy(available)

    def next_year(self):
        """ Advances the forecast to next year. """
        self.this_year += 1

class TestForecast(unittest.TestCase):
    """ Tests Forecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        # We will occasionally need to swap out subforecasts when
        # we want them to have no effect (e.g. no withdrawals because
        # we're not yet retired). Use null_forecast for that:
        self.null_forecast = DummyForecast(self.initial_year)
        # Paid $100 at the start of each month
        self.income_forecast_dummy = DummyForecast(
            self.initial_year,
            {Decimal(when)/12: Money(100) for when in range(12)})
        self.income_forecast_dummy.people = None
        # Spend $70 on living expenses at the start of each month
        self.living_expenses_forecast_dummy = DummyForecast(
            self.initial_year,
            {Decimal(when)/12: Money(-70) for when in range(12)})
        # Contribute the balance ($360):
        self.saving_forecast_dummy = DummyForecast(
            self.initial_year,
            {Decimal(when+1)/12: Money(-30) for when in range(12)})
        # Withdraw $300 at the start and middle of the year:
        self.withdrawal_forecast_dummy = DummyForecast(
            self.initial_year,
            {Decimal(0): Money(300), Decimal(0.5): Money(300)})
        # Refund for $100 next year:
        self.tax_forecast_dummy = DummyForecast(self.initial_year)
        self.tax_forecast_dummy.tax_adjustment = Money(100)

        # Also build a real ContributionForecast so that we can
        # test cash flows into accounts according to the overall
        # Forecast:
        # Simple tax rate: 50% on all income:
        tax = Tax(tax_brackets={
            self.initial_year: {Money(0): Decimal(0.5)}})
        # One person, to own the account:
        timing = Timing(frequency='BW')
        self.person = Person(
            initial_year=self.initial_year,
            name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 2045",
            gross_income=Money(5200),
            tax_treatment=tax,
            payment_timing=timing)
        # An account for savings to go to:
        self.account = Account(owner=self.person)
        # A strategy is required, but since there's only
        # one account the result will always be the same:
        self.strategy = TransactionTraversal(priority=[self.account])
        self.saving_forecast = SavingForecast(
            initial_year=self.initial_year,
            retirement_accounts={self.account},
            debt_accounts=set(),
            transaction_strategy=self.strategy)

        # Now assign `people`, `accounts`, and `debts` attrs to
        # appropriate subforecasts so that Forecast can retrieve
        # them:
        self.income_forecast_dummy.people = {self.person}
        self.withdrawal_forecast_dummy.accounts = {self.account}
        # Also add these to the null forecast, since it could be
        # substituted for any of the above dummy forecasts:
        self.null_forecast.people = self.income_forecast_dummy.people
        self.null_forecast.accounts = self.withdrawal_forecast_dummy.accounts
        # Forecast depends on SubForecasts have certain properties,
        # so add those here:
        self.income_forecast_dummy.net_income = (
            sum(self.income_forecast_dummy.transactions.values()))
        self.living_expenses_forecast_dummy.living_expenses = (
            sum(self.living_expenses_forecast_dummy.transactions.values()))
        self.withdrawal_forecast_dummy.gross_withdrawals = (
            sum(self.withdrawal_forecast_dummy.transactions.values()))
        self.tax_forecast_dummy.tax_owing = Money(600)
        # Add the same properties to the null forecast, since it
        # could be substituted for any of the above:
        self.null_forecast.net_income = self.income_forecast_dummy.net_income
        self.null_forecast.living_expenses = (
            self.living_expenses_forecast_dummy.living_expenses)
        self.null_forecast.gross_withdrawals = (
            self.withdrawal_forecast_dummy.gross_withdrawals)
        self.null_forecast.tax_owing = self.tax_forecast_dummy.tax_owing

        # Finally, we need a Scenario to build a Forecast.
        # This is the simplest possible: 1 year, no growth.
        self.scenario = Scenario(self.initial_year, num_years=1)

    def test_update_available(self):
        """ Test the mechanics of the update_available method.

        We don't want to test the underlying SubForecast classes,
        so just use end-to-end dummies.
        """
        # A 1-year forecast with no withdrawals. Should earn $1200
        # in income, spend $840 on living expenses, save the remaining
        # $360, and withdraw $600.
        forecast = Forecast(
            income_forecast=self.income_forecast_dummy,
            living_expenses_forecast=self.living_expenses_forecast_dummy,
            saving_forecast=self.saving_forecast_dummy,
            withdrawal_forecast=self.withdrawal_forecast_dummy,
            tax_forecast=self.tax_forecast_dummy,
            scenario=self.scenario)
        results = [
            sum(forecast.income_forecast.available_in.values(), Money(0)),
            sum(forecast.living_expenses_forecast.available_in.values()),
            sum(forecast.saving_forecast.available_in.values()),
            sum(forecast.withdrawal_forecast.available_in.values()),
            sum(forecast.tax_forecast.available_in.values()),
            sum(forecast.tax_forecast.available_out.values())]
        target = [
            Money(0),
            Money(1200),
            Money(360),
            Money(0),
            Money(600),
            Money(600)]
        for first, second in zip(results, target):
            self.assertAlmostEqual(first, second, places=2)

    def test_multi_year(self):
        """ Tests a multi-year forecast. """
        # Build a two-year forecast. Should contribute $360 each year.
        # No tax refunds or withdrawals.
        self.scenario = Scenario(self.initial_year, 2)
        self.tax_forecast_dummy.tax_adjustment = Money(0)
        forecast = Forecast(
            income_forecast=self.income_forecast_dummy,
            living_expenses_forecast=self.living_expenses_forecast_dummy,
            # NOTE: Saving forecast is not a dummy because we
            # want to actually contribute to savings accounts:
            saving_forecast=self.saving_forecast,
            withdrawal_forecast=self.null_forecast,
            tax_forecast=self.tax_forecast_dummy,
            scenario=self.scenario)
        results = [
            # pylint: disable=no-member
            # Pylint has trouble with attributes added via metaclass
            forecast.principal_history[self.initial_year],
            forecast.principal_history[self.initial_year + 1],
            self.account.balance_at_time('end')]
        target = [
            Money(0),
            Money(360),
            Money(720)]
        for first, second in zip(results, target):
            self.assertAlmostEqual(first, second, places=2)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

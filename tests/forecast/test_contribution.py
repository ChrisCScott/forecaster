""" Unit tests for `ContributionForecast`. """

import unittest
from decimal import Decimal
from collections import defaultdict
from forecaster import (
    Money, Person, Tax, Account,
    SavingForecast, TransactionTraversal,
    Timing, canada)
from tests.util import TestCaseTransactions


class TestSavingForecast(TestCaseTransactions):
    """ Tests SavingForecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Money(0): Decimal(0.5)}})
        # Accounts need an owner:
        timing = Timing(frequency='BW')
        self.person = Person(
            initial_year=self.initial_year,
            name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 2045",
            gross_income=Money(5200),
            tax_treatment=tax,
            payment_timing=timing)
        # We want at least two accounts which are contributed to
        # in different orders depending on the strategy.
        self.account = Account(
            owner=self.person)
        self.rrsp = canada.accounts.RRSP(
            owner=self.person,
            contribution_room=Money(1000))

        # Track money available for use by the forecast:
        self.available = defaultdict(lambda: Money(0))
        for i in range(26):  # biweekly inflows from employment
            self.available[Decimal(0.5 + i) / 26] += Money(150)
        for i in range(12):  # monthly living expenses and reductions:
            self.available[Decimal(i) / 12] -= Money(75)
        # The result: $3000 available
        self.total_available = sum(self.available.values())

        # Now we can set up the big-ticket items:
        # Use an ordered strategy by default:
        self.strategy = TransactionTraversal([self.account, self.rrsp])
        self.forecast = SavingForecast(
            initial_year=self.initial_year,
            retirement_accounts={self.account, self.rrsp},
            debt_accounts=set(),
            transaction_strategy=self.strategy)

    def test_ordered(self):
        """ Test saving with an ordered strategy. """
        # Set up forecast:
        self.strategy.priority = [self.rrsp, self.account]
        self.forecast(self.available)
        # We have $3000 available to contribute. We contribute the
        # first $1000 to `rrsp` and the balance to `account`
        self.assertTransactions(
            self.forecast.account_transactions[self.rrsp],
            Money(1000))
        self.assertTransactions(
            self.forecast.account_transactions[self.account],
            Money(2000))

    def test_weighted(self):
        """ Test saving with a weighted strategy. """
        # Set up forecast:
        self.strategy.priority = {self.rrsp: 500, self.account: 2500}
        self.forecast(self.available)
        # We have $3000 available to contribute. We contribute $500
        # to `rrsp` and the rest to `account`.
        self.assertTransactions(
            self.forecast.account_transactions[self.rrsp],
            Money(500))
        self.assertTransactions(
            self.forecast.account_transactions[self.account],
            Money(2500))

    def test_total(self):
        """ Test total contributed to accounts. """
        # Run forecast:
        self.forecast(self.available)

        # Regardless of setup, all available money (i.e. $3000)
        # should be contributed.
        self.assertAlmostEqual(self.forecast.total, Money(3000))

    # TODO: Test retirement_savings and debt_repayment properties.

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

""" Unit tests for `ContributionForecast`. """

import unittest
from decimal import Decimal
from collections import defaultdict
from forecaster import (
    Money, Person, Tax,
    ContributionForecast, AccountTransactionStrategy,
    Account, ContributionLimitAccount)


class TestContributionForecast(unittest.TestCase):
    """ Tests ContributionForecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Money(0): Decimal(0.5)}})
        # Accounts need an owner:
        self.person = Person(
            initial_year = self.initial_year,
            name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 2045",
            gross_income=Money(5200),
            tax_treatment=tax,
            payment_frequency='BW')
        # We want at least two accounts which are contributed to
        # in different orders depending on the strategy.
        self.account = Account(
            owner=self.person)
        self.limit_account = ContributionLimitAccount(
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
        self.strategy = AccountTransactionStrategy(
            AccountTransactionStrategy.strategy_ordered,
            {'ContributionLimitAccount': 1, 'Account': 2}
        )
        self.forecast = ContributionForecast(
            initial_year=self.initial_year,
            accounts={self.account, self.limit_account},
            account_transaction_strategy=self.strategy)

    def test_account_transactions_ordered(self):
        """ Test account transactions under ordered strategy. """
        # Set up forecast:
        self.strategy = AccountTransactionStrategy(
            strategy=AccountTransactionStrategy.strategy_ordered,
            weights={'ContributionLimitAccount': 1, 'Account': 2})
        self.forecast.account_transaction_strategy = self.strategy
        self.forecast.update_available(self.available)

        # Track total contributions to each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        account_contribution = (
            self.forecast.account_transactions[self.account])
        limit_account_contribution = (
            self.forecast.account_transactions[self.limit_account])
        # We have $3000 available to contribute. We contribute the
        # first $1000 to `limit_account` and the balance to `account`
        self.assertEqual(
            limit_account_contribution,
            self.limit_account.contribution_room)
        self.assertEqual(
            account_contribution,
            self.total_available - limit_account_contribution)

    def test_account_transactions_weighted(self):
        """ Test account transactions under weighted strategy. """
        # Set up forecast:
        self.strategy = AccountTransactionStrategy(
            strategy=AccountTransactionStrategy.strategy_weighted,
            weights={'ContributionLimitAccount': 500, 'Account': 2500})
        self.forecast.account_transaction_strategy = self.strategy
        self.forecast.update_available(self.available)

        # Track total contributions to each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        account_contribution = (
            self.forecast.account_transactions[self.account])
        limit_account_contribution = (
            self.forecast.account_transactions[self.limit_account])
        # We have $3000 available to contribute. We contribute $500
        # to `limit_account` and the rest to `account`.
        self.assertEqual(
            limit_account_contribution,
            Money(500))
        self.assertEqual(
            account_contribution,
            self.total_available - limit_account_contribution)

    def test_contributions(self):
        """ Test total contributed to accounts. """
        # Set up forecast:
        self.forecast.accounts = {self.account}
        self.forecast.update_available(self.available)

        # Regardless of setup, all available money (i.e. $3000)
        # should be contributed.
        self.assertEqual(
            self.forecast.contributions,
            Money(3000))


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

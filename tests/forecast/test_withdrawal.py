""" Unit tests for `WithdrawalForecast`. """

import unittest
from decimal import Decimal
from collections import defaultdict
from forecaster import (
    Money, Person, Tax,
    WithdrawalForecast, WithdrawalStrategy,
    AccountTransactionStrategy,
    Account, ContributionLimitAccount,
    Scenario)


class TestWithdrawalForecast(unittest.TestCase):
    """ Tests WithdrawalForecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        self.scenario = Scenario(
            initial_year=self.initial_year,
            num_years=1)
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Money(0): Decimal(0.5)}})
        # Accounts need an owner:
        self.person = Person(
            initial_year = self.initial_year,
            name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 1999",  # last year
            gross_income=Money(5200),
            tax_treatment=tax,
            payment_frequency='BW')
        # We want at least two accounts which are contributed to
        # in different orders depending on the strategy.
        self.account = Account(
            owner=self.person,
            balance=Money(60000))  # $60,000 <- BIGGER!
        self.limit_account = ContributionLimitAccount(
            owner=self.person,
            contribution_room=Money(1000),
            balance=Money(6000))  # $6,000

        # Track money available for use by the forecast:
        self.available = {}

        # Now we can set up the big-ticket items:
        self.account_strategy = AccountTransactionStrategy(
            AccountTransactionStrategy.strategy_ordered,
            {'ContributionLimitAccount': 1, 'Account': 2})
        self.withdrawal_strategy = WithdrawalStrategy(
            strategy=WithdrawalStrategy.strategy_const_withdrawal,
            base_amount=Money(12000),
            rate=Decimal(0.5))
        self.forecast = WithdrawalForecast(
            initial_year=self.initial_year,
            people={self.person},
            accounts={self.account, self.limit_account},
            scenario=self.scenario,
            withdrawal_strategy=self.withdrawal_strategy,
            account_transaction_strategy=self.account_strategy)

    def test_account_transactions_ordered(self):
        """ Test account transactions under ordered strategy. """
        # Set up forecast:
        self.account_strategy = AccountTransactionStrategy(
            strategy=AccountTransactionStrategy.strategy_ordered,
            weights={'ContributionLimitAccount': 1, 'Account': 2})
        self.forecast.account_transaction_strategy = self.account_strategy
        self.forecast.update_available(self.available)

        # Track total withdrawals from each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        account_withdrawal = (
            self.forecast.account_transactions[self.account])
        limit_account_withdrawal = (
            self.forecast.account_transactions[self.limit_account])
        # We are withdrawing $12,000. We'll withdraw the whole balance
        # of `limit_account` ($6000), with the rest from `account`:
        self.assertEqual(
            limit_account_withdrawal,
            Money(-6000))
        self.assertEqual(
            account_withdrawal,
            Money(-6000))

    def test_account_transactions_weighted(self):
        """ Test account transactions under weighted strategy. """
        # Set up forecast:
        self.account_strategy = AccountTransactionStrategy(
            strategy=AccountTransactionStrategy.strategy_weighted,
            weights={'ContributionLimitAccount': 2000, 'Account': 10000})
        self.forecast.account_transaction_strategy = self.account_strategy
        self.forecast.update_available(self.available)

        # Track total withdrawals from each account for convenience:
        # pylint: disable=unsubscriptable-object
        # These properties return dicts, but pylint has trouble
        # inferring that.
        account_withdrawal = (
            self.forecast.account_transactions[self.account])
        limit_account_withdrawal = (
            self.forecast.account_transactions[self.limit_account])
        # We are withdrawing $12,000. We'll withdraw the whole balance
        # of `limit_account` ($6000), with the rest from `account`:
        self.assertEqual(
            limit_account_withdrawal,
            Money(-2000))
        self.assertEqual(
            account_withdrawal,
            Money(-10000))

    def test_gross_withdrawals(self):
        """ Test total withdrawn from accounts. """
        # Set up forecast:
        self.forecast.accounts = {self.account}
        self.forecast.update_available(self.available)

        # For default constant strategy, should withdraw $12,000.
        self.assertEqual(
            self.forecast.gross_withdrawals,
            Money(12000))

    def test_tax_withheld(self):
        """ Test tax withheld from accounts. """
        # Set up forecast:
        self.forecast.update_available(self.available)
        # Manually set tax withholdings:
        self.account.tax_withheld = Money(100)
        self.limit_account.tax_withheld = Money(400)

        # Total withholdings are $500
        self.assertEqual(
            self.forecast.tax_withheld,
            Money(500))

    def test_net_withdrawals(self):
        """ Test total withdrawn from accounts, net of taxes. """
        # Set up forecast:
        self.forecast.update_available(self.available)
        # Manually set tax withholdings:
        self.account.tax_withheld = Money(100)
        self.limit_account.tax_withheld = Money(400)

        # Total withdrawals are $12,000 and total withheld is $500,
        # for total of $11,500 in net withdrawals:
        self.assertEqual(
            self.forecast.net_withdrawals,
            Money(11500))

    # TODO: Test different withdrawal strategies?
    # TODO: Test update_available to ensure that withdrawals
    #       are being recorded to self.available correctly?


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

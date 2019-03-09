""" Unit tests for `WithdrawalForecast`. """

import unittest
from decimal import Decimal
from forecaster import (
    Money, Person, Tax, Timing,
    WithdrawalForecast,
    AccountTransactionStrategy,
    Account, ContributionLimitAccount)


class TestWithdrawalForecast(unittest.TestCase):
    """ Tests WithdrawalForecast. """

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
            retirement_date="31 December 1999",  # last year
            gross_income=Money(5200),
            tax_treatment=tax,
            payment_timing=timing)
        # We want at least two accounts which are withdrawn from
        # in different orders depending on the strategy.
        self.account = Account(
            owner=self.person,
            balance=Money(60000))  # $60,000 <- BIGGER!
        self.limit_account = ContributionLimitAccount(
            owner=self.person,
            contribution_room=Money(1000),
            balance=Money(6000))  # $6,000

        # Assume there are $2000 in inflows and $22,000 in outflows,
        # for a net need of $20,000:
        self.available = {
            Decimal(0.25): Money(1000),
            Decimal(0.5): Money(-11000),
            Decimal(0.75): Money(1000),
            Decimal(1): Money(-11000)
        }

        # Now we can set up the big-ticket items:
        self.account_strategy = AccountTransactionStrategy(
            AccountTransactionStrategy.strategy_ordered,
            {'ContributionLimitAccount': 1, 'Account': 2})
        self.forecast = WithdrawalForecast(
            initial_year=self.initial_year,
            people={self.person},
            accounts={self.account, self.limit_account},
            account_transaction_strategy=self.account_strategy)

    def test_account_trans_ordered(self):
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
        # We are withdrawing $20,000. We'll withdraw the whole balance
        # of `limit_account` ($6000), with the rest from `account`:
        self.assertEqual(
            limit_account_withdrawal,
            Money(-6000))
        self.assertEqual(
            account_withdrawal,
            Money(-14000))

    def test_account_trans_weighted(self):
        """ Test account transactions under weighted strategy. """
        # Set up forecast:
        self.account_strategy = AccountTransactionStrategy(
            strategy=AccountTransactionStrategy.strategy_weighted,
            weights={'ContributionLimitAccount': 3000, 'Account': 17000})
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
        # We are withdrawing $20,000. We'll withdraw $3000 from
        # `limit_account`, with the rest from `account`:
        self.assertEqual(
            limit_account_withdrawal,
            Money(-3000))
        self.assertEqual(
            account_withdrawal,
            Money(-17000))

    def test_gross_withdrawals(self):
        """ Test total withdrawn from accounts. """
        # Set up forecast:
        self.forecast.accounts = {self.account}
        self.forecast.update_available(self.available)

        # For default `available`, should withdraw $20,000.
        self.assertEqual(
            self.forecast.gross_withdrawals,
            Money(20000))

    def test_tax_withheld(self):
        """ Test tax withheld from accounts. """
        # Manually set tax withholdings:
        self.account.tax_withheld = Money(100)
        self.limit_account.tax_withheld = Money(400)
        # Set up forecast:
        self.forecast.update_available(self.available)

        # Total withholdings are $500
        self.assertEqual(
            self.forecast.tax_withheld,
            Money(500))

    def test_net_withdrawals(self):
        """ Test total withdrawn from accounts, net of taxes. """
        # Manually set tax withholdings:
        self.account.tax_withheld = Money(100)
        self.limit_account.tax_withheld = Money(400)
        # Set up forecast:
        self.forecast.update_available(self.available)

        # Total withdrawals are $20,000 and total withheld is $500,
        # for total of $19,500 in net withdrawals:
        self.assertEqual(
            self.forecast.net_withdrawals,
            Money(19500))

    def test_update_available(self):
        """ Test total withdrawn from accounts. """
        # Set up forecast:
        self.forecast.accounts = {self.account}
        self.forecast.update_available(self.available)

        # The amount withdrawn should zero out `available`,
        # subject to any withholding taxes:
        self.assertEqual(
            sum(self.available.values()),
            -self.forecast.tax_withheld)



if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

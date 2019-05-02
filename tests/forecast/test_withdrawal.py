""" Unit tests for `WithdrawalForecast`. """

import unittest
from decimal import Decimal
from forecaster import (
    Money, Person, Tax, Timing,
    WithdrawalForecast,
    TransactionTraversal,
    Account, canada)
from tests.util import TestCaseTransactions

class TestWithdrawalForecast(TestCaseTransactions):
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
        self.rrsp = canada.accounts.RRSP(
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
        self.strategy = TransactionTraversal(
            priority=[self.rrsp, self.account])
        self.forecast = WithdrawalForecast(
            initial_year=self.initial_year,
            people={self.person},
            accounts={self.account, self.rrsp},
            transaction_strategy=self.strategy)

    def test_account_trans_ordered(self):
        """ Test account transactions under ordered strategy. """
        # Set up forecast:
        self.strategy = TransactionTraversal(
            priority=[self.rrsp, self.account])
        self.forecast.transaction_strategy = self.strategy
        self.forecast(self.available)
        # We are withdrawing $20,000. We'll withdraw the whole balance
        # of `rrsp` ($6000), with the rest from `account`:
        self.assertTransactions(
            self.forecast.account_transactions[self.rrsp],
            Money(-6000))
        self.assertTransactions(
            self.forecast.account_transactions[self.account],
            Money(-14000))

    def test_account_trans_weighted(self):
        """ Test account transactions under weighted strategy. """
        # Set up forecast:
        self.strategy = TransactionTraversal(
            priority={self.rrsp: 3000, self.account: 17000})
        self.forecast.transaction_strategy = self.strategy
        self.forecast(self.available)
        # We are withdrawing $20,000. We'll withdraw $3000 from
        # `rrsp`, with the rest from `account`:
        self.assertTransactions(
            self.forecast.account_transactions[self.rrsp],
            Money(-3000))
        self.assertTransactions(
            self.forecast.account_transactions[self.account],
            Money(-17000))

    def test_gross_withdrawals(self):
        """ Test total withdrawn from accounts. """
        # Set up forecast:
        self.forecast(self.available)

        # For default `available`, should withdraw $20,000.
        self.assertEqual(
            self.forecast.gross_withdrawals,
            Money(20000))

    def test_tax_withheld(self):
        """ Test tax withheld from accounts. """
        # Manually set tax withholdings:
        self.account.tax_withheld = Money(100)
        self.rrsp.tax_withheld = Money(400)
        # Set up forecast:
        self.forecast(self.available)

        # Total withholdings are $500
        self.assertEqual(
            self.forecast.tax_withheld,
            Money(500))

    def test_net_withdrawals(self):
        """ Test total withdrawn from accounts, net of taxes. """
        # Manually set tax withholdings:
        self.account.tax_withheld = Money(100)
        self.rrsp.tax_withheld = Money(400)
        # Set up forecast:
        self.forecast(self.available)

        # Total withdrawals are $20,000 and total withheld is $500,
        # for total of $19,500 in net withdrawals:
        self.assertEqual(
            self.forecast.net_withdrawals,
            Money(19500))

    def test_mutate_available(self):
        """ Test effect of invoking __call__ on `available`. """
        # Invoke __call__:
        self.forecast(self.available)

        # The amount withdrawn should zero out `available`,
        # subject to any withholding taxes:
        self.assertTransactions(self.available, -self.forecast.tax_withheld)



if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

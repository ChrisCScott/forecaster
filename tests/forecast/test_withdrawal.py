""" Unit tests for `WithdrawalForecast`. """

import unittest
from decimal import Decimal
from forecaster import (
    Person, Tax, Timing, WithdrawalForecast, TransactionStrategy,
    Account, canada, recorded_property)
from tests.util import TestCaseTransactions

class WithholdingAccount(Account):
    """ Testing account. 50% of withdrawals withheld. """

    @recorded_property
    def tax_withheld(self):
        """ Always withhold 50% """
        return self.outflows() / 2

class TestWithdrawalForecast(TestCaseTransactions):
    """ Tests WithdrawalForecast. """

    def setUp(self):
        """ Builds stock variables to test with. """
        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {0: 0.5}})
        # Accounts need an owner:
        timing = Timing(frequency='BW')
        self.person = Person(
            initial_year=self.initial_year,
            name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 1999",  # last year
            gross_income=5200,
            tax_treatment=tax,
            payment_timing=timing)
        # We want at least two accounts which are withdrawn from
        # in different orders depending on the strategy.
        self.account = Account(
            owner=self.person,
            balance=60000)  # $60,000 <- BIGGER!
        self.rrsp = canada.accounts.RRSP(
            owner=self.person,
            contribution_room=1000,
            balance=6000)  # $6,000

        # Assume there are $2000 in inflows and $22,000 in outflows,
        # for a net need of $20,000:
        self.available = {
            0.25: 1000,
            0.5: -11000,
            0.75: 1000,
            1: -11000
        }

        # Now we can set up the big-ticket items:
        self.strategy = TransactionStrategy(
            strategy=TransactionStrategy.strategy_ordered,
            weights={"RRSP": 1, "Account": 2})
        self.forecast = WithdrawalForecast(
            initial_year=self.initial_year,
            people={self.person},
            accounts={self.account, self.rrsp},
            transaction_strategy=self.strategy)

        # Set up another forecast for testing withholding behaviour:
        self.withholding_account = WithholdingAccount(
            owner=self.person,
            balance=100000)
        self.withholding_strategy = TransactionStrategy(
            strategy=TransactionStrategy.strategy_ordered,
            weights={"WithholdingAccount": 1})
        self.withholding_forecast = WithdrawalForecast(
            initial_year=self.initial_year,
            people={self.person},
            accounts={self.withholding_account},
            transaction_strategy=self.withholding_strategy)

    def setUp_decimal(self):
        """ Builds stock variables to test with. """
        # pylint: disable=invalid-name
        # Pylint doesn't like `setUp_decimal`, but it's not our naming
        # convention, so don't complain to us!
        # pylint: enable=invalid-name

        self.initial_year = 2000
        # Simple tax treatment: 50% tax rate across the board.
        tax = Tax(tax_brackets={
            self.initial_year: {Decimal(0): Decimal(0.5)}},
            high_precision=Decimal)
        # Accounts need an owner:
        timing = Timing(frequency='BW',high_precision=Decimal)
        self.person = Person(
            initial_year=self.initial_year,
            name="Test",
            birth_date="1 January 1980",
            retirement_date="31 December 1999",  # last year
            gross_income=Decimal(5200),
            tax_treatment=tax,
            payment_timing=timing,
            high_precision=Decimal)
        # We want at least two accounts which are withdrawn from
        # in different orders depending on the strategy.
        self.account = Account(
            owner=self.person,
            balance=Decimal(60000),  # $60,000 <- BIGGER!
            high_precision=Decimal)
        self.rrsp = canada.accounts.RRSP(
            owner=self.person,
            contribution_room=Decimal(1000),
            balance=Decimal(6000),  # $6,000
            high_precision=Decimal)

        # Assume there are $2000 in inflows and $22,000 in outflows,
        # for a net need of $20,000:
        self.available = {
            Decimal(0.25): Decimal(1000),
            Decimal(0.5): Decimal(-11000),
            Decimal(0.75): Decimal(1000),
            Decimal(1): Decimal(-11000)
        }

        # Now we can set up the big-ticket items:
        self.strategy = TransactionStrategy(
            strategy=TransactionStrategy.strategy_ordered,
            weights={"RRSP": Decimal(1), "Account": Decimal(2)})
        self.forecast = WithdrawalForecast(
            initial_year=self.initial_year,
            people={self.person},
            accounts={self.account, self.rrsp},
            transaction_strategy=self.strategy,
            high_precision=Decimal)

        # Set up another forecast for testing withholding behaviour:
        self.withholding_account = WithholdingAccount(
            owner=self.person,
            balance=Decimal(100000),
            high_precision=Decimal)
        self.withholding_strategy = TransactionStrategy(
            strategy=TransactionStrategy.strategy_ordered,
            weights={"WithholdingAccount": Decimal(1)},
            high_precision=Decimal)
        self.withholding_forecast = WithdrawalForecast(
            initial_year=self.initial_year,
            people={self.person},
            accounts={self.withholding_account},
            transaction_strategy=self.withholding_strategy,
            high_precision=Decimal)

    def test_account_trans_ordered(self):
        """ Test account transactions under ordered strategy. """
        # Set up forecast:
        self.forecast.transaction_strategy = TransactionStrategy(
            strategy=TransactionStrategy.strategy_ordered,
            weights={"RRSP": 1, "Account": 2})
        self.forecast(self.available)
        # We are withdrawing $20,000. We'll withdraw the whole balance
        # of `rrsp` ($6000), with the rest from `account`:
        self.assertTransactions(
            self.forecast.account_transactions[self.rrsp], -6000)
        self.assertTransactions(
            self.forecast.account_transactions[self.account], -14000)

    def test_account_trans_weighted(self):
        """ Test account transactions under weighted strategy. """
        # Set up forecast:
        self.forecast.transaction_strategy = TransactionStrategy(
            strategy=TransactionStrategy.strategy_weighted,
            weights={"RRSP": 3000, "Account": 17000})
        self.forecast(self.available)
        # We are withdrawing $20,000. We'll withdraw $3000 from
        # `rrsp`, with the rest from `account`:
        self.assertTransactions(
            self.forecast.account_transactions[self.rrsp], -3000)
        self.assertTransactions(
            self.forecast.account_transactions[self.account], -17000)

    def test_gross_withdrawals(self):
        """ Test total withdrawn from accounts. """
        # Set up forecast:
        self.forecast(self.available)

        # For default `available`, should withdraw $20,000.
        self.assertEqual(
            self.forecast.gross_withdrawals, 20000)

    def test_tax_withheld(self):
        """ Test tax withheld from accounts. """
        # Set up forecast:
        self.withholding_forecast(self.available)

        # Total withholdings are $10000 (half of $20,000 withdrawn)
        self.assertAlmostEqual(
            self.withholding_forecast.tax_withheld, -10000)

    def test_net_withdrawals(self):
        """ Test total withdrawn from accounts, net of taxes. """
        # Set up forecast:
        self.withholding_forecast(self.available)

        # Total withdrawals are $20,000 and total withheld is $10,000,
        # for total of $10,000 in net withdrawals:
        self.assertAlmostEqual(
            self.withholding_forecast.net_withdrawals, 10000)

    def test_mutate_available(self):
        """ Invoke __call__ on `available`. """
        # Invoke __call__:
        self.withholding_forecast(self.available)

        # The amount withdrawn should zero out `available`,
        # subject to 50% withholding taxes (i.e. `available` should
        # only be reduced to -$10,000):
        self.assertTransactions(self.available, -10000)

    def test_decimal(self):
        """ Test WithdrawalStrategy with Decimal inputs. """
        # Convert values to Decimal:
        self.setUp_decimal()

        # This test is based on test_mutate_available:
        # Invoke __call__:
        self.withholding_forecast(self.available)

        # The amount withdrawn should zero out `available`,
        # subject to 50% withholding taxes (i.e. `available` should
        # only be reduced to -$10,000):
        self.assertTransactions(self.available, Decimal(-10000))


if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

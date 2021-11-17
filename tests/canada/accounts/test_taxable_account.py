""" Tests for forecaster.canada.TaxableAccount. """

import unittest
import decimal
from decimal import Decimal
from forecaster.canada import TaxableAccount
from tests.accounts.test_base import TestAccountMethods

class TestTaxableAccountMethods(TestAccountMethods):
    """ Test TaxableAccount """

    def setUp(self):
        super().setUp()
        self.AccountType = TaxableAccount

    def test_init_acb_default(self, *args, **kwargs):
        """ Init account without explicit ACB. """
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        # Should be same as balance:
        self.assertEqual(account.acb, account.balance)

    def test_init_acb_explicit(self, *args, **kwargs):
        """ Init account with explicit ACB. """
        account = self.AccountType(
            self.owner, *args,
            acb=0, balance=100, rate=1, **kwargs)
        self.assertEqual(account.acb, Decimal(0))

    def test_capital_gain_zero(self, *args, **kwargs):
        """ Test unrealized capital gains. """
        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.capital_gain, Decimal(0))
        # ACB is unchanged:
        self.assertEqual(account.acb, Decimal(50))

    def test_capital_gain_real_start(self, *args, **kwargs):
        """ Test capital gains realized at start of year. """
        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
        # Add a $100 start-of-year transaction. This should increase
        # ACB (to $150), but doesn't change capital gains:
        account.add_transaction(100, 'start')
        # Withdraw the entire starting balance.
        account.add_transaction(-200, 'start')
        # Regardless of the transaction, capital gain is only $50:
        self.assertEqual(account.capital_gain, Decimal(50))
        # ACB is unchanged, since it's the start of year figure:
        self.assertEqual(account.acb, Decimal(50))

    def test_capital_gain_real_end(self, *args, **kwargs):
        """ Test capital gains realized at end of year. """
        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
        # Add a $100 start-of-year transaction. This should increase
        # ACB to $150; the end of year balance will be $400, with $250
        # in capital gains:
        account.add_transaction(100, 'start')
        # Withdraw the entire ending balance.
        account.add_transaction(-400, 'end')
        self.assertEqual(account.capital_gain, Decimal(250))
        # ACB is unchanged, since it's the start of year figure:
        self.assertEqual(account.acb, Decimal(50))

    def test_capital_gain_real_partial(self, *args, **kwargs):
        """ Test capital gains only partially realized. """
        # Init account with $100 acb, no capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=100, balance=100, rate=1, **kwargs)
        # Add a $100 start-of-year transaction. ACB is now $200.
        # The ending balance will be $400, with $200 in capital gains:
        account.add_transaction(100, 'start')
        # Withdraw half the ending balance.
        account.add_transaction(-200, 'end')
        # Capital gains should be half of the total gains, i.e. $100
        self.assertEqual(account.capital_gain, Decimal(100))
        # ACB is unchanged, since it's the start of year figure:
        self.assertEqual(account.acb, Decimal(100))

    def test_capital_gain_real_next(self, *args, **kwargs):
        """ Test realized capital gains followed by next_year. """
        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
        # Add a start-of-year inflow to make it interesting.
        # Increases ACB by $100 to $150 and the ending balance to $400.
        account.add_transaction(100, 'start')
        # Withdraw half the end-of-year balance ($200).
        # Of this, $125 is capital gain. ACB is halved to $75.
        account.add_transaction(-200, 'end')
        account.next_year()
        # ACB should be updated at the start of the year to $75:
        self.assertEqual(account.acb, Decimal(75))
        # Capital gains are back to $0:
        self.assertEqual(account.capital_gain, Decimal(0))

    def test_taxable_income_zero(self, *args, **kwargs):
        """ Test TaxableAccount.taxable_income with no sales. """
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.taxable_income, Decimal(0))

    def test_taxable_income_gain(self, *args, **kwargs):
        """ Test TaxableAccount.taxable_income with withdrawal on gain. """
        # Initial balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
        # Withdraw the entire end-of-year balance ($200).
        account.add_transaction(-200, 'end')
        # Capital gains are $150, of which half is taxable income.
        self.assertEqual(account.taxable_income, Decimal(75))

    def test_taxable_income_gain_next(self, *args, **kwargs):
        """ Test taxable_income after calling next_year post-withdrawal. """
        # Initial balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
        # Withdraw the entire end-of-year balance ($200).
        account.add_transaction(-200, 'end')
        # Capital gains are $150, of which half is taxable income.
        account.next_year()
        # Should have $0 acb and $0 balance.
        # Add $100 to account at start of year
        account.add_transaction(100, 'start')
        # It will grow to $200 by end of year; withdraw it all:
        account.add_transaction(-200, 'end')
        # Taxable income should be $50 (half of $100 growth);
        # if next_year failed to track acb correctly then we'll get
        # a different result.
        self.assertEqual(account.taxable_income, Decimal(50))

    def test_taxable_income_loss(self, *args, **kwargs):
        """ Test taxable_income with withdrawal on loss. """
        # Initial balance is $100, of which $25 is capital gains.
        # This account will lose half of its value by the end of year.
        account = self.AccountType(
            self.owner, *args,
            acb=75, balance=100, rate=-0.5, **kwargs)
        # Withdraw the entire end-of-year balance ($50).
        account.add_transaction(-50, 'end')
        # Capital loss of $25 was incurred. That's halved to -$12.50:
        self.assertEqual(account.taxable_income, Decimal(-12.50))

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

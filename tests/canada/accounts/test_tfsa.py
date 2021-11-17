""" Tests for forecaster.canada.TFSA. """

import unittest
import decimal
from decimal import Decimal
from random import Random
from forecaster import Person
from forecaster.canada import TFSA, constants
from tests.canada.accounts.test_registered_account import (
    TestRegisteredAccountMethods)

class TestTFSAMethods(TestRegisteredAccountMethods):
    """ Test TFSA. """

    def setUp(self):
        """ Sets up variables for testing TFSAs. """
        super().setUp()
        self.AccountType = TFSA

        # Ensure that inflation_adjustments covers the entire range of
        # constants.TFSAAnnualAccrual
        min_year = min(constants.TFSA_ANNUAL_ACCRUAL)
        max_year = max(constants.TFSA_ANNUAL_ACCRUAL) + 10
        self.extend_inflation_adjustments(min_year, max_year)

    def setUp_decimal(self):
        """ Sets up variables for testing TFSAs. """
        super().setUp_decimal()
        self.AccountType = TFSA

        # Ensure that inflation_adjustments covers the entire range of
        # constants.TFSAAnnualAccrual
        min_year = min(constants.TFSA_ANNUAL_ACCRUAL)
        max_year = max(constants.TFSA_ANNUAL_ACCRUAL) + 10
        self.extend_inflation_adjustments(
            min_year, max_year, high_precision=Decimal)

    def test_init_contrib_default(self, *args, **kwargs):
        """ Init TFSA with implicit contribution_room. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contributor, self.owner)

    def test_init_cont_room_explicit(self, *args, **kwargs):
        """ Init TFSA with explicit contribution_room. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contribution_room, self.contribution_room)

    def test_init_cont_room_default(self, *args, **kwargs):
        """ Init TFSA with default contribution_room. """
        # TFSAs began in 2009. Confirm that we're correctly determining
        # future contribution room based on an inflation-adjusted 2009
        # amount (a schedule of such accruals is returned by
        # get_accruals).
        accruals = self.get_accruals()
        # Use a person who's at least old enough to qualify for all
        # available TFSA accruals.
        owner = Person(self.initial_year, "test", 1950, retirement_date=2015)
        # For each starting year, confirm that available contribution
        # room is the sum of past accruals.
        for year in accruals:
            account = self.AccountType(
                owner, *args,
                inflation_adjust=self.inflation_adjust,
                initial_year=year, **kwargs)
            target = sum([
                accruals[i] for i in range(min(accruals), year + 1)])
            self.assertEqual(account.contribution_room, target)
            # We're starting each TFSA in a different year, which can
            # confuse the linked-account recordkeeping (later-year
            # accounts will default to using the contribution room
            # of the first account). Destroy the link to simplify this.
            account.max_inflow_link.unregister()

    def test_init_inflation_adjust(self, *args, **kwargs):
        """ Init TFSA with explicit inflation_adjust. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            initial_year=self.initial_year, **kwargs)
        self.assertEqual(account.inflation_adjust, self.inflation_adjust)

    def test_init_invalid_inf_adj(self, *args, **kwargs):
        """ Test TFSA.__init__ with invalid inflation_adjust input. """
        with self.assertRaises(TypeError):
            _ = self.AccountType(
                self.owner, *args, inflation_adjust='invalid', **kwargs)

    def test_next(self, *args, **kwargs):
        """ Test TFSA.next_year. """
        super().test_next(*args, **kwargs)

        # Set up variables for testing.
        accruals = self.get_accruals()
        rand = Random()
        owner = Person(
            min(accruals), self.owner.name, 1950,
            retirement_date=2015,
            gross_income=self.owner.gross_income,
            raise_rate={
                year: 0 for year in range(min(accruals), max(accruals) + 2)},
            tax_treatment=self.owner.tax_treatment)
        account = self.AccountType(
            owner, *args, inflation_adjust=self.inflation_adjust,
            rate=0, balance=0, **kwargs)

        # For each year, confirm that the balance and contribution room
        # are updated appropriately
        transactions = 0
        for year in accruals:
            # Add a transaction (either an inflow or outflow)
            transaction = rand.randint(
                -int(account.balance), int(account.contribution_room))
            account.add_transaction(transaction)
            # Confirm that contribution room is the same as accruals,
            # less any net transactions
            accrual = sum(
                [accruals[i] for i in range(min(accruals), year + 1)])
            target = accrual - transactions
            self.assertEqual(account.contribution_room, target)
            # Confirm that balance is equal to the sum of transactions
            # over the previous years (note that this is a no-growth
            # scenario, since rate=0)
            self.assertEqual(account.balance, transactions)
            # Advance the account to next year and repeat tests
            account.next_year()
            # Update the running total of transactions, to be referenced
            # in the next round of tests.
            transactions += transaction

    def get_accruals(self):
        """ Builds a dict of {year: accrual} pairs.

        Each accrual is a number corresponding to the total TFSA
        contribution room accrued since inception (2009) to year.
        """
        # Build a secquence of accruals covering known accruals and
        # 10 years where we'll need to estimate accruals with rounding
        accruals = {}
        base_year = min(constants.TFSA_ANNUAL_ACCRUAL)
        base_accrual = constants.TFSA_ANNUAL_ACCRUAL[base_year]
        for year in range(min(constants.TFSA_ANNUAL_ACCRUAL),
                          max(constants.TFSA_ANNUAL_ACCRUAL) + 10):
            if year in constants.TFSA_ANNUAL_ACCRUAL:
                accruals[year] = constants.TFSA_ANNUAL_ACCRUAL[year]
            else:
                accrual = base_accrual * self.inflation_adjust(
                    base_year, year
                )
                accrual = round(
                    accrual / constants.TFSA_ACCRUAL_ROUNDING_FACTOR
                ) * constants.TFSA_ACCRUAL_ROUNDING_FACTOR
                accruals[year] = accrual
        return accruals

    def test_taxable_income_gain(self, *args, **kwargs):
        """ Test TFSA.taxable_income with a gain in the account. """
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000, **kwargs)
        # Throw in some transactions for good measure, including a
        # withdrawal to realize any gains:
        account.add_transaction(100, 'start')
        account.add_transaction(-200, 'end')
        self.assertEqual(account.taxable_income, 0)

    def test_decimal(self, *args, **kwargs):
        """ Test TFSA with Decimal inputs. """
        # Convert values to Decimal:
        self.setUp_decimal()

        # Set up variables for testing.
        accruals = self.get_accruals()
        rand = Random()
        owner = Person(
            min(accruals), self.owner.name, 1950,
            retirement_date=2015,
            gross_income=self.owner.gross_income,
            raise_rate={
                year: 0 for year in range(min(accruals), max(accruals) + 2)},
            tax_treatment=self.owner.tax_treatment,
            high_precision=Decimal)
        account = self.AccountType(
            owner, *args, inflation_adjust=self.inflation_adjust,
            rate=Decimal(0), balance=Decimal(0), high_precision=Decimal,
            **kwargs)

        # For each year, confirm that the balance and contribution room
        # are updated appropriately
        transactions = Decimal(0)
        for year in accruals:
            # Add a transaction (either an inflow or outflow)
            transaction = rand.randint(
                -int(account.balance), int(account.contribution_room))
            account.add_transaction(transaction)
            # Confirm that contribution room is the same as accruals,
            # less any net transactions
            accrual = sum(
                [accruals[i] for i in range(min(accruals), year + 1)])
            target = Decimal(accrual) - transactions
            self.assertEqual(account.contribution_room, target)
            # Confirm that balance is equal to the sum of transactions
            # over the previous years (note that this is a no-growth
            # scenario, since rate=0)
            self.assertEqual(account.balance, transactions)
            # Advance the account to next year and repeat tests
            account.next_year()
            # Update the running total of transactions, to be referenced
            # in the next round of tests.
            transactions += Decimal(transaction)

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

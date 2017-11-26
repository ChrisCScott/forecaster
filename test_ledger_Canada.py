""" Tests Canada-specific accounts in the ledger_Canada module. """

import unittest
from collections import defaultdict
import decimal
from decimal import Decimal
from random import Random
from ledger_Canada import *
from tax import Tax
from settings import Settings
from utility import *
from test_ledger import TestAccountMethods
from test_helper import *


class TestRegisteredAccountMethods(TestAccountMethods):
    """ Tests RegisteredAccount. """

    @classmethod
    def setUpClass(cls):
        """ Sets up variables for testing RegisteredAccount """
        super().setUpClass()

        cls.AccountType = RegisteredAccount

        # Randomly generate inflation adjustments based on inflation
        # rates of 1%-20%. Be sure to include both Settings.initial_year
        # and cls.initial_year in the range, since we use default-valued
        # inits a lot (which calls Settings.initial_year).
        # Add a few extra years on to the end for testing purposes.
        cls.inflation_adjustments = {
            min(cls.initial_year, Settings.initial_year): Decimal(1)
        }
        cls.extend_inflation_adjustments(
            min(cls.inflation_adjustments),
            max(cls.initial_year, Settings.initial_year) + 5)

        # HACK: Assigning directly to cls.inflation_adjust creates a
        # bound method, so we need to create a static method and then
        # assign to a class attribute:
        @staticmethod
        def inflation_adjust(target_year, base_year):
            return (
                cls.inflation_adjustments[target_year] /
                cls.inflation_adjustments[base_year]
            )
        cls.inflation_adjust = inflation_adjust

        cls.contribution_room = 0

    @classmethod
    def extend_inflation_adjustments(cls, min_year, max_year):
        """ Convenience method.

        Ensures cls.inflation_adjustment spans min_year and max_year.
        """
        rand = Random()

        # Extend inflation_adjustments backwards, assuming 1-20% inflation
        i = min(cls.inflation_adjustments)
        while i > min_year:
            cls.inflation_adjustments[i - 1] = (
                cls.inflation_adjustments[i] /
                Decimal(1 + rand.randint(1, 20)/100)
            )
            i -= 1

        # Extend inflation_adjustments forwards, assuming 1-20% inflation
        i = max(cls.inflation_adjustments)
        while i < max_year:
            cls.inflation_adjustments[i + 1] = (
                cls.inflation_adjustments[i] *
                Decimal(1 + rand.randint(1, 20)/100)
            )
            i += 1

    def test_init(self, *args, **kwargs):
        super().test_init(*args,
                          inflation_adjust=self.inflation_adjust,
                          contribution_room=self.contribution_room,
                          **kwargs)

        # Basic init using pre-built RegisteredAccount-specific args
        # and default Account args
        account = self.AccountType(self.owner, *args,
                                   inflation_adjust=self.inflation_adjust,
                                   contribution_room=self.contribution_room,
                                   **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.inflation_adjust, self.inflation_adjust)
        self.assertEqual(account.contribution_room, self.contribution_room)

        # Try again with default contribution_room
        account = self.AccountType(self.owner, *args,
                                   inflation_adjust=self.inflation_adjust,
                                   **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.inflation_adjust, self.inflation_adjust)
        # Different subclasses have different default contribution room
        # values. There's also no settings value for RegisteredAccount's
        # contribution_room parameter (it has a hardcoded default of 0),
        # so don't test this subclasses
        if self.AccountType == RegisteredAccount:
            self.assertEqual(account.contribution_room, 0)

        # Test invalid `person` input
        with self.assertRaises(TypeError):
            account = self.AccountType('invalid person', *args,
                                       inflation_adjust=self.inflation_adjust,
                                       **kwargs)

        # Try type conversion for inflation_adjustments
        inflation_adjustments = {
            '2000': '1',
            2001.0: 1.25,
            Decimal(2002): 1.5,
            2003: Decimal('1.75'),
            2017.0: Decimal(2.0)
        }

        def inflation_adjust(val, this_year, target_year):
            return val * (
                inflation_adjustments[target_year] /
                inflation_adjustments[this_year]
            )

        account = self.AccountType(self.owner,
                                   *args, contribution_room=500,
                                   inflation_adjust=self.inflation_adjust,
                                   initial_year=2000, **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.contribution_room, Money('500'))

        # Try invalid inflation_adjustments.
        # First, pass in a non-dict
        with self.assertRaises(TypeError):
            account = self.AccountType(
                self.owner, *args,
                inflation_adjust='invalid',
                contribution_room=self.contribution_room, **kwargs)

        # Finally, test a non-Money-convertible contribution_room:
        with self.assertRaises(decimal.InvalidOperation):
            account = self.AccountType(
                self.owner, *args,
                contribution_room='invalid', **kwargs)

    def test_properties(self, *args, **kwargs):
        # Basic check: properties return scalars (current year's values)
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contribution_room,
                         self.contribution_room)

        # NOTE: RegisteredAccount.next_year() raises NotImplementedError
        # and some subclasses require args for next_year(). That is
        # already dealt with by test_next, so check that properties are
        # pointing to the current year's values after calling next_year
        # in text_next.

    def test_add_transaction(self, *args, **kwargs):
        # Add mandatory argument for building RegisteredAccount objects
        super().test_add_transaction(*args, **kwargs)

    def test_next(self, *args, next_args=[], next_kwargs={}, **kwargs):
        # next_contribution_room is not implemented for
        # RegisteredAccount, and it's required for next_year, so confirm
        # that trying to call next_year() throws an appropriate error.
        if self.AccountType == RegisteredAccount:
            account = RegisteredAccount(self.owner)
            with self.assertRaises(NotImplementedError):
                account.next_year(*next_args, **next_kwargs)
        # For other account types, try a conventional next_year test
        else:
            super().test_next(*args, next_args=next_args,
                              next_kwargs=next_kwargs, **kwargs)

    def test_returns(self, *args, **kwargs):
        # super().test_returns calls next_year(), which calls
        # next_contribution_room(), which is not implemented for
        # RegisteredAccount. Don't test returns for this class,
        # and instead allow subclasses to pass through.
        if self.AccountType != RegisteredAccount:
            super().test_returns(*args, **kwargs)

    def test_max_inflow(self, *args, **kwargs):
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.max_inflow(), self.contribution_room)

        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=1000000, **kwargs)
        self.assertEqual(account.max_inflow(), Money(1000000))


class TestRRSPMethods(TestRegisteredAccountMethods):
    """ Test RRSP """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.AccountType = RRSP

        # Ensure that inflation_adjustments covers the entire range of
        # Constants.RRSPContributionAccrualMax and the years where
        # self.owner is 71-95 (plus a few extra for testing)
        min_year = min(min(Constants.RRSPContributionRoomAccrualMax),
                       cls.owner.birth_date.year +
                       min(Constants.RRSPRRIFMinWithdrawal))
        max_year = max(max(Constants.RRSPContributionRoomAccrualMax),
                       cls.owner.birth_date.year +
                       max(Constants.RRSPRRIFMinWithdrawal)) + 2
        cls.extend_inflation_adjustments(min_year, max_year)

    def test_init(self, *args, **kwargs):
        super().test_init(*args, **kwargs)

        # The only thing that RRSP.__init__ does is set
        # RRIF_conversion_year, so test that:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(self.owner.age(account.RRIF_conversion_year),
                         Constants.RRSPRRIFConversionAge)

    def test_taxable_income(self, *args, **kwargs):
        # Create an RRSP with a $1,000,000 balance and no withdrawals:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000000,
            **kwargs)
        # Since withdrawals = $0, there's no taxable income
        self.assertEqual(account.taxable_income, 0)

        # Now add a withdrawal, confirm it's included in taxable income
        account.add_transaction(-100, 'end')
        self.assertEqual(account.taxable_income, Money(100))

        # Now add a contribution (at a different time), confirm that it
        # has no effect on taxable_income
        account.add_transaction(100, 'start')
        self.assertEqual(account.taxable_income, Money(100))

    def test_tax_withheld(self, *args, **kwargs):
        # First, test RRSP (not RRIF) behaviour:
        # Test RRSP with no withdrawals -> no tax withheld
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            balance=1000000,
            **kwargs)
        self.assertEqual(account.tax_withheld, 0)

        # Now add a withdrawal in the lowest withholding tax bracket,
        # say $1. This should be taxed at the lowest rate
        account.add_transaction(-1, 'end')
        self.assertEqual(account.tax_withheld, Money(
            1 * min(Constants.RRSPWithholdingTaxRate.values())
        ))
        # Now add a transaction in the highest tax bracket, say $1000000
        # This should be taxed at the highest rate
        account.add_transaction(-999999, 'start')
        self.assertEqual(account.tax_withheld, Money(
            1000000 * max(Constants.RRSPWithholdingTaxRate.values())
        ))

        # NOTE: tax thresholds are not currently inflation-adjusted;
        # implement inflation-adjustment and then test for it here?

    def test_tax_deduction(self, *args, **kwargs):
        # Create an RRSP with a $1,000,000 balance and no contributions:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000000,
            **kwargs)
        # Since contributions = $0, there's no taxable income
        self.assertEqual(account.taxable_income, 0)

        # Now add an inflow, confirm it's included in taxable income
        account.add_transaction(100, 'end')
        self.assertEqual(account.tax_deduction, Money(100))

        # Now add an outflow (at a different time), confirm that it
        # has no effect on taxable_income
        account.add_transaction(-100, 'start')
        self.assertEqual(account.tax_deduction, Money(100))

    def test_next(self, *args, next_args=[], next_kwargs={}, **kwargs):
        super().test_next(*args, next_args=next_args,
                          next_kwargs={'income': Money(100000), **kwargs},
                          **kwargs)

        initial_contribution_room = Money(100)
        # Set income to a non-Money object to test type-conversion.
        # Use a value less than inflation-adjusted RRSPAccrualMax
        income = Money(100000)
        # Build a copy of self.owner with the income defined above and
        # no raises (so income is the same each year).
        owner = Person(
            self.owner.name, self.owner.birth_date,
            retirement_date=self.owner.retirement_date,
            gross_income=income,
            raise_rate={year: 0 for year in self.owner.raise_rate_history},
            tax_treatment=self.owner.tax_treatment,
            initial_year=self.initial_year)
        # Basic test:
        account = self.AccountType(
            owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room, **kwargs)
        account.next_year()
        self.assertEqual(account.contribution_room,
                         initial_contribution_room +
                         Money(income) *
                         Constants.RRSPContributionRoomAccrualRate)

        # Pick the initial year so that we'll know the accrual max. for
        # next year
        initial_year = min(Constants.RRSPContributionRoomAccrualMax) - 1
        # Use income that's $1000 more than is necessary to max out RRSP
        # contribution room accrual for the year.
        income = (Constants.RRSPContributionRoomAccrualMax[initial_year + 1] /
                  Constants.RRSPContributionRoomAccrualRate) + 1000
        owner = Person(
            self.owner.name, self.owner.birth_date,
            retirement_date=self.owner.retirement_date,
            gross_income=income,
            raise_rate={year: 0 for year in self.owner.raise_rate_history},
            tax_treatment=self.owner.tax_treatment,
            initial_year=self.initial_year)
        account = self.AccountType(
            owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room,
            initial_year=initial_year, **kwargs)
        account.next_year()
        # New contribution room should be the max, plus rollover from
        # the previous year.
        self.assertEqual(
            account.contribution_room,
            initial_contribution_room +
            Money(Constants.RRSPContributionRoomAccrualMax[initial_year + 1])
        )

        # Try again, but this time contribute the max. in the first year
        account = self.AccountType(
            owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room,
            initial_year=initial_year, **kwargs)
        account.add_transaction(account.contribution_room)
        account.next_year()
        # New contribution room should be the max; no rollover.
        self.assertEqual(
            account.contribution_room,
            Money(Constants.RRSPContributionRoomAccrualMax[initial_year + 1])
        )

        # Try again, but this time start with the last year for which we
        # know the nominal accrual max already. The next year's accrual
        # max will need to be estimated via inflation-adjustment:
        initial_year = max(Constants.RRSPContributionRoomAccrualMax)
        # Inflation-adjust the (known) accrual max for the previous year
        # to get the max for this year.
        max_accrual = (
            Constants.RRSPContributionRoomAccrualMax[initial_year] *
            self.inflation_adjust(initial_year + 1, initial_year)
        )
        # Let's have income that's between the initial year's max
        # accrual and the next year's max accrual:
        income = Money(
            (max_accrual +
             Constants.RRSPContributionRoomAccrualMax[initial_year]
             ) / 2
        ) / Constants.RRSPContributionRoomAccrualRate
        owner = Person(
            self.owner.name, self.owner.birth_date,
            retirement_date=self.owner.retirement_date,
            gross_income=income,
            raise_rate={year: 0 for year in self.owner.raise_rate_history},
            tax_treatment=self.owner.tax_treatment,
            initial_year=self.initial_year)
        account = self.AccountType(
            owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room,
            initial_year=initial_year, **kwargs)
        account.next_year()
        # New contribution room should be simply determined by the
        # accrual rate set in Constants plus rollover.
        self.assertEqual(
            account.contribution_room,
            initial_contribution_room +
            Constants.RRSPContributionRoomAccrualRate * income
        )

        # Try again, but now with income greater than the inflation-
        # adjusted accrual max.
        income = max_accrual / Constants.RRSPContributionRoomAccrualRate + 1000
        owner = Person(
            self.owner.name, self.owner.birth_date,
            retirement_date=self.owner.retirement_date,
            gross_income=income,
            raise_rate={year: 0 for year in self.owner.raise_rate_history},
            tax_treatment=self.owner.tax_treatment,
            initial_year=self.initial_year)
        account = self.AccountType(
            owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room,
            initial_year=initial_year, **kwargs)
        account.add_transaction(account.contribution_room)  # no rollover
        account.next_year()
        # New contribution room should be the max accrual; no rollover.
        self.assertAlmostEqual(account.contribution_room,
                               Money(max_accrual), 3)

    def test_min_outflow(self, *args, **kwargs):
        # Have a static RRSP (no inflows/outflows/change in balance)
        balance = 1000000
        initial_year = min(self.inflation_adjustments)
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            balance=balance, rate=0, initial_year=initial_year, **kwargs)
        last_year = min(
            max(self.inflation_adjustments) + 1,
            max(self.owner.raise_rate_history)
        )
        # For each year over a lifetime, check min_outflow is correct:
        for year in range(initial_year, last_year):
            age = self.owner.age(year)
            # First, check that we've converted to an RRIF if required:
            if age > Constants.RRSPRRIFConversionAge:
                self.assertTrue(account.RRIF_conversion_year < year)
            # Next, if we've converted to an RRIF, check various
            # min_outflow scenarios:
            if account.RRIF_conversion_year < year:
                # If we've converted early, use the statutory formula
                # (i.e. 1/(90-age))
                if age < min(Constants.RRSPRRIFMinWithdrawal):
                    min_outflow = account.balance / (90 - age)
                # Otherwise, use the prescribed withdrawal amount:
                else:
                    if age > max(Constants.RRSPRRIFMinWithdrawal):
                        min_outflow = account.balance * \
                            max(Constants.RRSPRRIFMinWithdrawal.values())
                    # If we're past the range of prescribed amounts,
                    # use the largest prescribed amount
                    else:
                        min_outflow = account.balance * \
                            Constants.RRSPRRIFMinWithdrawal[age]
            # If this isn't an RRIF yet, there's no min. outflow.
            else:
                min_outflow = 0
            self.assertEqual(account.min_outflow(), min_outflow)
            # Advance the account and test again on the next year:
            account.next_year()

    def test_convert_to_RRIF(self, *args, **kwargs):
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertNotEqual(account.RRIF_conversion_year, account.initial_year)
        account.convert_to_RRIF()
        self.assertEqual(account.RRIF_conversion_year, account.initial_year)

        # NOTE: If we implement automatic RRIF conversions, test that.


class TestTFSAMethods(TestRegisteredAccountMethods):
    """ Test TFSA """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = TFSA

        # Ensure that inflation_adjustments covers the entire range of
        # Constants.TFSAAnnualAccrual
        min_year = min(Constants.TFSAAnnualAccrual)
        max_year = max(Constants.TFSAAnnualAccrual) + 10
        cls.extend_inflation_adjustments(min_year, max_year)

    def test_init(self, *args, **kwargs):
        super().test_init(*args, **kwargs)

        # TFSAs began in 2009. Confirm that we're using that as our
        # baseline for future contribution_room determinations and that
        # we've correctly set contribution_room to $5000.
        # Basic test: manually set contribution_room
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account._base_accrual, Money(5000))
        self.assertEqual(account._base_accrual_year, 2009)
        self.assertEqual(account.contribution_room, self.contribution_room)

        accruals = self.get_accruals()

        # For each starting year, confirm that available contribution
        # room is the sum of past accruals.
        # Use a person who's at least old enough to qualify for all
        # available TFSA accruals.
        owner = Person("test", 1950, retirement_date=2015)
        for year in accruals:
            account = self.AccountType(
                owner, *args,
                inflation_adjust=self.inflation_adjust,
                initial_year=year, **kwargs)
            self.assertEqual(
                account.contribution_room,
                Money(sum([
                    accruals[i] for i in range(min(accruals), year + 1)
                    ]))
            )

    def test_next(self, *args, next_args=[], next_kwargs={}, **kwargs):
        super().test_next(*args, next_args=next_args,
                          next_kwargs=next_kwargs, **kwargs)

        # Set up variables for testing.
        accruals = self.get_accruals()
        rand = Random()
        owner = Person(
            self.owner.name, 1950,
            retirement_date=2015,
            gross_income=self.owner.gross_income,
            raise_rate={
                year: 0 for year in range(min(accruals), max(accruals) + 2)},
            tax_treatment=self.owner.tax_treatment,
            initial_year=min(accruals))
        account = self.AccountType(
            owner, *args,
            inflation_adjust=self.inflation_adjust,
            rate=0, initial_year=min(accruals), balance=0, **kwargs)

        # For each year, confirm that the balance and contribution room
        # are updated appropriately
        transactions = Money(0)
        for year in accruals:
            # Add a transaction (either an inflow or outflow)
            transaction = rand.randint(-account.balance.amount,
                                       account.contribution_room.amount)
            account.add_transaction(transaction)
            # Confirm that contribution room is the same as accruals,
            # less any net transactions
            accrual = sum(
                [accruals[i] for i in range(min(accruals), year + 1)]
            )
            self.assertEqual(
                account.contribution_room, Money(accrual) - transactions
            )
            # Confirm that balance is equal to the sum of transactions
            # over the previous years (note that this is a no-growth
            # scenario, since rate=0)
            self.assertEqual(account.balance, transactions)
            # Advance the account to next year and repeat tests
            account.next_year()
            # Update the running total of transactions, to be referenced
            # in the next round of tests.
            transactions += Money(transaction)

    def get_accruals(self):
        # Build a secquence of accruals covering known accruals and
        # 10 years where we'll need to estimate accruals with rounding
        accruals = {}
        base_year = min(Constants.TFSAAnnualAccrual)
        base_accrual = Constants.TFSAAnnualAccrual[base_year]
        for year in range(min(Constants.TFSAAnnualAccrual),
                          max(Constants.TFSAAnnualAccrual) + 10):
            if year in Constants.TFSAAnnualAccrual:
                accruals[year] = Constants.TFSAAnnualAccrual[year]
            else:
                accrual = base_accrual * self.inflation_adjust(
                    base_year, year
                )
                accrual = round(
                    accrual / Constants.TFSAInflationRoundingFactor
                ) * Constants.TFSAInflationRoundingFactor
                accruals[year] = accrual
        return accruals

    def test_taxable_income(self, *args, **kwargs):
        # This method should always return $0
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000, **kwargs)
        # Throw in some transactions for good measure:
        account.add_transaction(100, 'start')
        account.add_transaction(-200, 'end')
        self.assertEqual(account.taxable_income, Money(0))


class TestTaxableAccountMethods(TestAccountMethods):
    """ Test TaxableAccount """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = TaxableAccount

    def test_init(self, *args, **kwargs):
        super().test_init(*args, **kwargs)

        # Default init
        account = self.AccountType(self.owner, *args, **kwargs)
        self.assertEqual(account.acb, account.balance)
        self.assertEqual(account.capital_gain, Money(0))

        # Confirm that acb is set to balance by default
        account = self.AccountType(self.owner, *args, balance=100, **kwargs)
        self.assertEqual(account.acb, account.balance)
        self.assertEqual(account.capital_gain, Money(0))

        # Confirm that initializing an account with explicit acb works.
        # (In this case, acb is 0, so the balance is 100% capital gains,
        # but those gains are unrealized, so capital_gain is $0)
        account = self.AccountType(self.owner, *args,
                                   acb=0, balance=100, rate=1, **kwargs)
        self.assertEqual(account.acb, Money(0))
        self.assertEqual(account.capital_gain, Money(0))

    def test_properties(self, *args, **kwargs):

        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(self.owner, *args,
                                   acb=50, balance=100, rate=1,
                                   **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.capital_gain, Money(0))
        # Withdrawal the entire end-of-year balance.
        account.add_transaction(-200, 'end')
        # Transactions will affect acb in the following year, not this
        # one - therefore acb should be unchanged here.
        self.assertEqual(account.acb, Money(50))
        # capital_gains in this year should be updated to reflect the
        # new transaction.
        self.assertEqual(account.capital_gain, Money(150))
        # Now add a start-of-year inflow to confirm that capital_gains
        # isn't confused.
        account.add_transaction(100, 'start')
        self.assertEqual(account.acb, Money(50))
        # By the time of the withdrawal, acb=$150 and balance=$400.
        # The $200 withdrawal will yield a $125 capital gain.
        self.assertEqual(account.capital_gain, Money(125))

    def test_next(self, *args, next_args=[], next_kwargs={}, **kwargs):
        super().test_next(*args, next_args=next_args, next_kwargs=next_kwargs,
                          **kwargs)

        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(self.owner, *args,
                                   acb=50, balance=100, rate=1,
                                   **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.capital_gain, Money(0))
        # Withdrawal the entire end-of-year balance.
        account.add_transaction(-200, 'end')
        self.assertEqual(account.capital_gain, Money(150))

        account.next_year()
        # Expect $0 balance, $0 acb, and (initially) $0 capital gains
        self.assertEqual(account.balance, Money(0))
        self.assertEqual(account.acb, Money(0))
        self.assertEqual(account.capital_gain, Money(0))
        # Add inflow in the new year. It will grow by 100%.
        account.add_transaction(100, 'start')
        self.assertEqual(account.acb, Money(0))
        self.assertEqual(account.capital_gain, Money(0))

        account.next_year()
        # Expect $200 balance
        self.assertEqual(account.acb, Money(100))
        self.assertEqual(account.capital_gain, Money(0))
        account.add_transaction(-200, 'start')
        self.assertEqual(account.acb, Money(100))
        self.assertEqual(account.capital_gain, Money(100))

    def test_taxable_income(self, *args, **kwargs):
        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(self.owner, *args,
                                   acb=50, balance=100, rate=1,
                                   **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.taxable_income, Money(0))
        # Withdrawal the entire end-of-year balance.
        account.add_transaction(-200, 'end')
        self.assertEqual(account.taxable_income, Money(150)/2)

        account.next_year()
        # Expect $0 balance, $0 acb, and (initially) $0 capital gains
        self.assertEqual(account.taxable_income, Money(0))
        # Add inflow in the new year. It will grow by 100%.
        account.add_transaction(100, 'start')
        self.assertEqual(account.taxable_income, Money(0))

        account.next_year()
        # Expect $200 balance
        self.assertEqual(account.taxable_income, Money(0))
        account.add_transaction(-200, 'start')
        self.assertEqual(account.taxable_income, Money(100)/2)


class TestPrincipleResidenceMethods(TestAccountMethods):
    """ Test PrincipleResidence. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = PrincipleResidence

    def test_taxable_income(self, *args, **kwargs):
        account = self.AccountType(
            self.owner, *args, balance=1000, rate=1, nper=1)

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

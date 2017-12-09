""" Tests Canada-specific accounts in the ledger.canada module. """

import unittest
import decimal
from decimal import Decimal
from random import Random
import context  # pylint: disable=unused-import
from forecaster.person import Person
from forecaster.ledger import Money
from forecaster.canada.accounts import RRSP, TFSA, TaxableAccount, \
    PrincipleResidence
from forecaster.canada import constants
from tests.test_accounts import TestAccountMethods, \
    TestRegisteredAccountMethods
# pylint: disable=wildcard-import,unused-wildcard-import
from tests.test_helper import *


class TestRRSPMethods(TestRegisteredAccountMethods):
    """ Test RRSP """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.AccountType = RRSP

        # Randomly generate inflation adjustments based on inflation
        # rates of 1%-20%. Add a few extra years on to the end for
        # testing purposes.
        cls.inflation_adjustments = {cls.initial_year: Decimal(1)}

        # HACK: Assigning directly to cls.inflation_adjust creates a
        # bound method, so we need to create a static method and then
        # assign to a class attribute:
        @staticmethod
        def inflation_adjust(target_year, base_year):
            """ Inflation from base_year to target_year """
            return (
                cls.inflation_adjustments[target_year] /
                cls.inflation_adjustments[base_year]
            )
        cls.inflation_adjust = inflation_adjust

        # Ensure that inflation_adjustments covers the entire range of
        # constants.RRSPContributionAccrualMax and the years where
        # self.owner is 71-95 (plus a few extra for testing)
        min_year = min(min(constants.RRSP_ACCRUAL_MAX),
                       cls.owner.birth_date.year +
                       min(constants.RRSP_RRIF_WITHDRAWAL_MIN))
        max_year = max(max(constants.RRSP_ACCRUAL_MAX),
                       cls.owner.birth_date.year +
                       max(constants.RRSP_RRIF_WITHDRAWAL_MIN)) + 2
        cls.extend_inflation_adjustments(min_year, max_year)

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
                Decimal(1 + rand.randint(1, 20) / 100)
            )
            i -= 1

        # Extend inflation_adjustments forwards, assuming 1-20% inflation
        i = max(cls.inflation_adjustments)
        while i < max_year:
            cls.inflation_adjustments[i + 1] = (
                cls.inflation_adjustments[i] *
                Decimal(1 + rand.randint(1, 20) / 100)
            )
            i += 1

    def test_init(self, *args, **kwargs):
        super().test_init(*args, **kwargs)

        # The only thing that RRSP.__init__ does is set inflation_adjust
        # and rrif_conversion_year, so test those:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(self.owner.age(account.rrif_conversion_year),
                         constants.RRSP_RRIF_CONVERSION_AGE)
        self.assertEqual(account.inflation_adjust, self.inflation_adjust)

        # Try type conversion for inflation_adjustments
        inflation_adjustments = {
            '2000': '1',
            2001.0: 1.25,
            Decimal(2002): 1.5,
            2003: Decimal('1.75'),
            2017.0: Decimal(2.0)
        }

        account = self.AccountType(
            self.owner, *args,
            contribution_room=500, inflation_adjust=inflation_adjustments,
            **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.contribution_room, Money('500'))
        self.assertEqual(account.inflation_adjust(2000), Decimal(1))
        self.assertEqual(account.inflation_adjust(2001), Decimal(1.25))
        self.assertEqual(account.inflation_adjust(2002), Decimal(1.5))
        self.assertEqual(account.inflation_adjust(2003), Decimal(1.75))
        self.assertEqual(account.inflation_adjust(2017), Decimal(2))

        # Try invalid inflation_adjustments.
        # First, pass in a non-dict
        with self.assertRaises(TypeError):
            account = self.AccountType(
                self.owner, *args,
                inflation_adjust='invalid',
                contribution_room=self.contribution_room, **kwargs)

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
            1 * min(constants.RRSP_WITHHOLDING_TAX_RATE.values())
        ))
        # Now add a transaction in the highest tax bracket, say $1000000
        # This should be taxed at the highest rate
        account.add_transaction(-999999, 'start')
        self.assertEqual(account.tax_withheld, Money(
            1000000 * max(constants.RRSP_WITHHOLDING_TAX_RATE.values())
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

    def test_next_year(self, *args, **kwargs):
        super().test_next_year(*args, **kwargs)

        initial_year = min(constants.RRSP_ACCRUAL_MAX)
        initial_contribution_room = Money(100)
        # Set income to a non-Money object to test type-conversion.
        # Use a value that won't result in a deduction exceeding the
        # inflation-adjusted RRSPAccrualMax (~$25,000 in 2017)
        income = Money(100000)  # -> $18,000 deduction
        # Build a copy of self.owner with the income defined above and
        # no raises (so income is the same each year).
        owner = Person(
            initial_year, self.owner.name, self.owner.birth_date,
            retirement_date=self.owner.retirement_date,
            gross_income=income,
            raise_rate=0,
            tax_treatment=self.owner.tax_treatment)
        # Basic test:
        account = self.AccountType(
            owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room, **kwargs)
        account.next_year()
        self.assertEqual(
            account.contribution_room,
            initial_contribution_room + Money(income) *
            constants.RRSP_ACCRUAL_RATE
        )

        # Pick the initial year so that we'll know the accrual max. for
        # next year
        initial_year = min(constants.RRSP_ACCRUAL_MAX) - 1
        # Use income that's $1000 more than is necessary to max out RRSP
        # contribution room accrual for the year.
        income = (
            constants.RRSP_ACCRUAL_MAX[initial_year + 1] /
            constants.RRSP_ACCRUAL_RATE
        ) + 1000
        owner = Person(
            initial_year, self.owner.name, self.owner.birth_date,
            retirement_date=self.owner.retirement_date,
            gross_income=income,
            raise_rate=0,
            tax_treatment=self.owner.tax_treatment)
        account = self.AccountType(
            owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room, **kwargs)
        account.next_year()
        # New contribution room should be the max, plus rollover from
        # the previous year.
        self.assertEqual(
            account.contribution_room,
            initial_contribution_room +
            Money(constants.RRSP_ACCRUAL_MAX[
                initial_year + 1
            ])
        )

        # Try again, but this time contribute the max. in the first year
        account = self.AccountType(
            owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room, **kwargs)
        account.add_transaction(account.contribution_room)
        account.next_year()
        # New contribution room should be the max; no rollover.
        self.assertEqual(
            account.contribution_room,
            Money(constants.RRSP_ACCRUAL_MAX[initial_year + 1])
        )

        # Try again, but this time start with the last year for which we
        # know the nominal accrual max already. The next year's accrual
        # max will need to be estimated via inflation-adjustment:
        initial_year = max(constants.RRSP_ACCRUAL_MAX)
        # Inflation-adjust the (known) accrual max for the previous year
        # to get the max for this year.
        max_accrual = (
            constants.RRSP_ACCRUAL_MAX[initial_year] *
            self.inflation_adjust(initial_year + 1, initial_year)
        )
        # Let's have income that's between the initial year's max
        # accrual and the next year's max accrual:
        income = Money(
            (max_accrual +
             constants.RRSP_ACCRUAL_MAX[initial_year]
             ) / 2
        ) / constants.RRSP_ACCRUAL_RATE
        owner = Person(
            initial_year, self.owner.name, self.owner.birth_date,
            retirement_date=self.owner.retirement_date,
            gross_income=income,
            raise_rate=0,
            tax_treatment=self.owner.tax_treatment)
        account = self.AccountType(
            owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room, **kwargs)
        account.next_year()
        # New contribution room should be simply determined by the
        # accrual rate set in Constants plus rollover.
        self.assertEqual(
            account.contribution_room,
            initial_contribution_room +
            constants.RRSP_ACCRUAL_RATE * income
        )

        # Try again, but now with income greater than the inflation-
        # adjusted accrual max.
        income = max_accrual / constants.RRSP_ACCRUAL_RATE + 1000
        owner = Person(
            initial_year, self.owner.name, self.owner.birth_date,
            retirement_date=self.owner.retirement_date,
            gross_income=income,
            raise_rate=0,
            tax_treatment=self.owner.tax_treatment)
        account = self.AccountType(
            owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=initial_contribution_room, **kwargs)
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
            balance=balance, rate=0, **kwargs)
        last_year = min(
            max(self.inflation_adjustments) + 1,
            # pylint: disable=no-member
            # Pylint gets confused by attributes added by metaclass.
            # recorded_property members always have a corresponding
            # *_history member:
            max(self.owner.raise_rate_history)
        )
        # For each year over a lifetime, check min_outflow is correct:
        for year in range(initial_year, last_year):
            age = self.owner.age(year)
            # First, check that we've converted to an RRIF if required:
            if age > constants.RRSP_RRIF_CONVERSION_AGE:
                self.assertTrue(account.rrif_conversion_year < year)
            # Next, if we've converted to an RRIF, check various
            # min_outflow scenarios:
            if account.rrif_conversion_year < year:
                # If we've converted early, use the statutory formula
                # (i.e. 1/(90-age))
                if age < min(constants.RRSP_RRIF_WITHDRAWAL_MIN):
                    min_outflow = account.balance / (90 - age)
                # Otherwise, use the prescribed withdrawal amount:
                else:
                    if age > max(constants.RRSP_RRIF_WITHDRAWAL_MIN):
                        min_outflow = account.balance * \
                            max(constants.RRSP_RRIF_WITHDRAWAL_MIN.values())
                    # If we're past the range of prescribed amounts,
                    # use the largest prescribed amount
                    else:
                        min_outflow = account.balance * \
                            constants.RRSP_RRIF_WITHDRAWAL_MIN[age]
            # If this isn't an RRIF yet, there's no min. outflow.
            else:
                min_outflow = 0
            self.assertEqual(account.min_outflow(), min_outflow)
            # Advance the account and test again on the next year:
            account.next_year()

    def test_convert_to_rrif(self, *args, **kwargs):
        """ Test RRSP.convert_to_rrif. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertNotEqual(account.rrif_conversion_year, account.initial_year)
        account.convert_to_rrif()
        self.assertEqual(account.rrif_conversion_year, account.initial_year)

        # NOTE: If we implement automatic RRIF conversions, test that.


class TestTFSAMethods(TestRegisteredAccountMethods):
    """ Test TFSA """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = TFSA

        # Randomly generate inflation adjustments based on inflation
        # rates of 1%-20%. Add a few extra years on to the end for
        # testing purposes.
        cls.inflation_adjustments = {cls.initial_year: Decimal(1)}

        # HACK: Assigning directly to cls.inflation_adjust creates a
        # bound method, so we need to create a static method and then
        # assign to a class attribute:
        @staticmethod
        def inflation_adjust(target_year, base_year):
            """ Inflation from base_year to target_year. """
            return (
                cls.inflation_adjustments[target_year] /
                cls.inflation_adjustments[base_year]
            )
        cls.inflation_adjust = inflation_adjust

        # Ensure that inflation_adjustments covers the entire range of
        # constants.TFSAAnnualAccrual
        min_year = min(constants.TFSA_ANNUAL_ACCRUAL)
        max_year = max(constants.TFSA_ANNUAL_ACCRUAL) + 10
        cls.extend_inflation_adjustments(min_year, max_year)

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
                Decimal(1 + rand.randint(1, 20) / 100)
            )
            i -= 1

        # Extend inflation_adjustments forwards, assuming 1-20% inflation
        i = max(cls.inflation_adjustments)
        while i < max_year:
            cls.inflation_adjustments[i + 1] = (
                cls.inflation_adjustments[i] *
                Decimal(1 + rand.randint(1, 20) / 100)
            )
            i += 1

    def test_init(self, *args, **kwargs):
        super().test_init(*args, **kwargs)

        # Basic test: manually set contribution_room
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(account.contribution_room, self.contribution_room)

        accruals = self.get_accruals()

        # TFSAs began in 2009. Confirm that we're correctly determining
        # future contribution room based on an inflation-adjusted 2009
        # amount (a schedule of such accruals is returned by
        # get_accruals).
        # For each starting year, confirm that available contribution
        # room is the sum of past accruals.
        # Use a person who's at least old enough to qualify for all
        # available TFSA accruals.
        owner = Person(self.initial_year, "test", 1950, retirement_date=2015)
        for year in accruals:
            account = self.AccountType(
                owner, *args,
                inflation_adjust=self.inflation_adjust,
                initial_year=year, **kwargs)
            self.assertEqual(
                account.contribution_room,
                Money(
                    sum([
                        accruals[i] for i in range(min(accruals), year + 1)
                    ])
                )
            )
        self.assertEqual(account.inflation_adjust, self.inflation_adjust)

        # Try type conversion for inflation_adjustments
        inflation_adjustments = {
            '2000': '1',
            2001.0: 1.25,
            Decimal(2002): 1.5,
            2003: Decimal('1.75'),
            2017.0: Decimal(2.0)
        }

        account = self.AccountType(
            self.owner, *args, inflation_adjust=self.inflation_adjust,
            **kwargs)
        self.assertEqual(account.inflation_adjust, self.inflation_adjust)

        # Try type conversion for inflation_adjustments
        inflation_adjustments = {
            '2000': '1',
            2001.0: 1.25,
            Decimal(2002): 1.5,
            2003: Decimal('1.75'),
            2017.0: Decimal(2.0)
        }

        account = self.AccountType(
            self.owner, *args,
            contribution_room=500, inflation_adjust=inflation_adjustments,
            **kwargs)
        self.assertEqual(account.contributor, self.owner)
        self.assertEqual(account.contribution_room, Money('500'))
        self.assertEqual(account.inflation_adjust(2000), Decimal(1))
        self.assertEqual(account.inflation_adjust(2001), Decimal(1.25))
        self.assertEqual(account.inflation_adjust(2002), Decimal(1.5))
        self.assertEqual(account.inflation_adjust(2003), Decimal(1.75))
        self.assertEqual(account.inflation_adjust(2017), Decimal(2))

        # Try an invalid inflation_adjustment.
        with self.assertRaises(TypeError):
            account = self.AccountType(
                self.owner, *args, inflation_adjust='invalid', **kwargs)

    def test_next_year(self, *args, **kwargs):
        super().test_next_year(*args, **kwargs)

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
        """ Builds a dict of {year: accrual} pairs.

        Each accrual is a Money object corresponding to the total TFSA
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
        account = self.AccountType(
            self.owner, *args, **kwargs)
        self.assertEqual(account.acb, account.balance)
        self.assertEqual(account.capital_gain, Money(0))

        # Confirm that acb is set to balance by default
        account = self.AccountType(
            self.owner, *args, balance=100, **kwargs)
        self.assertEqual(account.acb, account.balance)
        self.assertEqual(account.capital_gain, Money(0))

        # Confirm that initializing an account with explicit acb works.
        # (In this case, acb is 0, so the balance is 100% capital gains,
        # but those gains are unrealized, so capital_gain is $0)
        account = self.AccountType(
            self.owner, *args,
            acb=0, balance=100, rate=1, **kwargs)
        self.assertEqual(account.acb, Money(0))
        self.assertEqual(account.capital_gain, Money(0))

    def test_properties(self, *args, **kwargs):
        """ Test TaxableAccount properties (i.e. acb, capital_gains). """

        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
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

    def test_next_year(self, *args, **kwargs):
        super().test_next_year(*args, **kwargs)

        # Init account with $50 acb.
        # Balance is $100, of which $50 is capital gains.
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
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
        account = self.AccountType(
            self.owner, *args,
            acb=50, balance=100, rate=1, **kwargs)
        # No capital gains are realized yet, so capital_gains=$0
        self.assertEqual(account.taxable_income, Money(0))
        # Withdrawal the entire end-of-year balance.
        account.add_transaction(-200, 'end')
        self.assertEqual(account.taxable_income, Money(150) / 2)

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
        self.assertEqual(account.taxable_income, Money(100) / 2)


class TestPrincipleResidenceMethods(TestAccountMethods):
    """ Test PrincipleResidence. """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.AccountType = PrincipleResidence

    def test_taxable_income(self, *args, **kwargs):
        account = self.AccountType(
            self.owner, *args, balance=1000, rate=1, nper=1)
        self.assertEqual(account.taxable_income, Money(0))
        # Now let the residence appreciate 100% (to $2000) and then sell
        # the home (i.e. withdraw $2000):
        account.next_year()
        account.add_transaction(-2000)
        self.assertEqual(account.taxable_income, Money(0))

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.main()

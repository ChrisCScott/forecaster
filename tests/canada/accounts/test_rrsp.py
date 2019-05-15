""" Tests RRSP. """

import unittest
import decimal
from decimal import Decimal
from forecaster import Person, Money
from forecaster.canada import RRSP, constants
from tests.canada.accounts.test_registered_account import (
    TestRegisteredAccountMethods)

class TestRRSPMethods(TestRegisteredAccountMethods):
    """ Test RRSP """

    def setUp(self):
        """ Sets up variables for testing RRSP. """
        super().setUp()

        self.AccountType = RRSP

        # Ensure that inflation_adjustments covers the entire range of
        # constants.RRSP_ACCRUAL_MAX and the years where self.owner is
        # 71-95 (plus a few extra for testing)
        min_year = min(min(constants.RRSP_ACCRUAL_MAX),
                       self.owner.birth_date.year +
                       min(constants.RRSP_RRIF_WITHDRAWAL_MIN))
        max_year = max(max(constants.RRSP_ACCRUAL_MAX),
                       self.owner.birth_date.year +
                       max(constants.RRSP_RRIF_WITHDRAWAL_MIN)) + 2
        self.extend_inflation_adjustments(min_year, max_year)

        self.initial_contribution_room = Money(100)
        # Set income to a non-Money object to test type-conversion.
        # Use a value that won't result in a deduction exceeding the
        # inflation-adjusted RRSPAccrualMax (~$25,000 in 2017)
        self.owner.income = Money(100000)  # -> $18,000 accrual
        # Ensure there are no raises so income is the same in each year:
        self.owner.raise_rate_function = lambda _: 0
        self.owner.gross_income = Money(100000)
        self.owner.spouse = Person(
            self.initial_year, "Spouse", "2 February 1998",
            gross_income=50000,
            retirement_date=self.owner.retirement_date)

    def test_init_basic(self, *args, **kwargs):
        """ Basic init tests for RRSP. """
        super().test_init_basic(*args, **kwargs)

        # The only thing that RRSP.__init__ does is set
        # `rrif_conversion_year`, so test that:
        account = self.AccountType(
            self.owner, *args,
            contribution_room=self.contribution_room, **kwargs)
        self.assertEqual(
            self.owner.age(account.rrif_conversion_year),
            constants.RRSP_RRIF_CONVERSION_AGE)

    def test_taxable_income_gain(self, *args, **kwargs):
        """ Test taxable_income with no withdrawals or contributions. """
        # Create an RRSP with a $1,000,000 balance, 100% growth,
        # and no withdrawals:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            balance=1000000, rate=1,
            **kwargs)
        # Since withdrawals = $0, there's no taxable income
        self.assertEqual(account.taxable_income, 0)

    def test_taxable_income_loss(self, *args, **kwargs):
        """ Test taxable_income with no withdrawals or contributions. """
        # Create an RRSP with a $1,000,000 balance, a 50% loss,
        # and no withdrawals:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            balance=1000000, rate=-0.5,
            **kwargs)
        # Since withdrawals = $0, there's no taxable income
        self.assertEqual(account.taxable_income, 0)

    def test_taxable_income_outflow(self, *args, **kwargs):
        """ Test taxable_income with a withdrawal. """
        # Build an account and add a withdrawal.
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000000,
            **kwargs)
        account.add_transaction(-100, 'end')
        # Confirm the withdrawal is included in taxable income
        self.assertEqual(account.taxable_income, Money(100))

    def test_taxable_income_inflow(self, *args, **kwargs):
        """ Test that a contribution doesn't affect taxable_income. """
        # Build an account and add a contribution and a withdrawal.
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000000,
            **kwargs)
        # Add a contribution and a withdrawal (at different times, so
        # that they don't cancel each other out.)
        account.add_transaction(-100, 'end')
        account.add_transaction(100, 'start')
        # Confirm that the contribution has no effect on taxable_income
        # (which should be $100 due to the withdrawal)
        self.assertEqual(account.taxable_income, Money(100))

    def test_tax_withheld_pos(self, *args, **kwargs):
        """ Test tax_withheld with no transactions and positive balance. """
        # For ease of testing, ensure that the initial year is
        # represented in RRSP_WITHHOLDING_RATE:
        initial_year = min(constants.RRSP_WITHHOLDING_TAX_RATE)
        self.set_initial_year(initial_year)

        # Test RRSP with no withdrawals -> no tax withheld
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            balance=1000000,
            **kwargs)
        self.assertEqual(account.tax_withheld, 0)

    def test_tax_withheld_neg(self, *args, **kwargs):
        """ Test tax_withheld with no transactions and negative balance. """
        # Balance makes no difference to withholding, so result should
        # be the same as with positive balance:
        self.test_tax_withheld_pos(*args, **kwargs)

    def test_tax_withheld_small_outflow(self, *args, **kwargs):
        """ Test tax_withheld with a small inflow. """
        # For ease of testing, ensure that the initial year is
        # represented in RRSP_WITHHOLDING_RATE:
        initial_year = min(constants.RRSP_WITHHOLDING_TAX_RATE)
        withholding_rates = constants.RRSP_WITHHOLDING_TAX_RATE[initial_year]
        self.set_initial_year(initial_year)

        # Add a withdrawal in the lowest withholding tax bracket ($1).
        # This should be taxed at the lowest rate.
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            balance=1000000,
            **kwargs)
        account.add_transaction(-1, 'end')
        self.assertEqual(
            account.tax_withheld,
            Money(1 * min(withholding_rates.values()))
        )

    def test_tax_withheld_large_outflow(self, *args, **kwargs):
        """ Test tax_withheld with a large outflow. """
        # For ease of testing, ensure that the initial year is
        # represented in RRSP_WITHHOLDING_RATE:
        initial_year = min(constants.RRSP_WITHHOLDING_TAX_RATE)
        withholding_rates = constants.RRSP_WITHHOLDING_TAX_RATE[initial_year]
        self.set_initial_year(initial_year)

        # Add a transaction in the highest tax bracket. (Note that the
        # value of the transaction must be larger than the bracket
        # threshold, otherwise it falls within the lower bracket.)
        # This should be taxed at the highest rate.
        bracket = max(withholding_rates)
        val = Money(bracket + 1)
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            balance=val * 2,
            **kwargs)
        account.add_transaction(-val, 'start')
        self.assertEqual(
            account.tax_withheld,
            val * withholding_rates[bracket]
        )

    def test_tax_withheld_inflation(self, *args, **kwargs):
        """ Test inflation adjustment of tax_withheld withholding rates. """
        # Ensure that the initial year is not represented in
        # RRSP_WITHHOLDING_RATE:
        initial_year = max(constants.RRSP_WITHHOLDING_TAX_RATE) + 1
        self.set_initial_year(initial_year)
        # Set up 100% inflation between the previous year and this one.
        self.inflation_adjustments[self.initial_year - 1] = Decimal(1)
        self.inflation_adjustments[self.initial_year] = Decimal(2)
        # Inflation-adjust based on the previous (represented) year:
        withholding_rates = {
            rate * self.inflation_adjust(initial_year, initial_year - 1):
            constants.RRSP_WITHHOLDING_TAX_RATE[initial_year - 1][rate]
            for rate in constants.RRSP_WITHHOLDING_TAX_RATE[initial_year - 1]
        }

        # Add a transaction that would be in the highest tax bracket in
        # `initial_year - 1` but would be in the second-highest bracket
        # in initial_year due to 100% inflation.
        top_bracket = max(withholding_rates)
        second_bracket = max(
            bracket for bracket in withholding_rates if bracket < top_bracket
        )
        # We want a value that's at least as large as the top bracket
        # from the previous year and sits somewhere between the second
        # and top brackets this year:
        val = Money(max(
            max(constants.RRSP_WITHHOLDING_TAX_RATE[initial_year - 1]) + 1,
            (top_bracket + second_bracket) / 2
        ))
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            balance=val * 2,
            **kwargs)

        account.add_transaction(-val)
        rate = withholding_rates[second_bracket]
        self.assertEqual(account.tax_withheld, Money(val * rate))

    def test_tax_deduction_zero(self, *args, **kwargs):
        """ Test RRSP.tax_deduction with no transactions. """
        # Create an RRSP with a $1,000,000 balance and no contributions:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000000,
            **kwargs)
        # Since contributions = $0, there's no tax deduction
        self.assertEqual(account.taxable_income, 0)

    def test_tax_deduction_pos(self, *args, **kwargs):
        """ Test RRSP.tax_deduction with an inflow. """
        # Create an RRSP with a $1,000,000 balance and no contributions:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000000,
            **kwargs)
        # Now add an inflow, confirm it's deducted from taxable income
        account.add_transaction(100, 'end')
        self.assertEqual(account.tax_deduction, Money(100))

    def test_tax_deduction_neg(self, *args, **kwargs):
        """ Test RRSP.tax_deduction with an outflow. """
        # Create an RRSP with a $1,000,000 balance and no contributions:
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room, balance=1000000,
            **kwargs)
        # Add an inflow and an outflow (at different times), confirm
        # that the outflow has no effect on tax_deduction.
        account.add_transaction(100, 'end')
        account.add_transaction(-100, 'start')
        self.assertEqual(account.tax_deduction, Money(100))

    def test_cont_basic(self, *args, **kwargs):
        """ Test `contribution_room` with no contributions. """
        # Ensure we know the accrual max for this year:
        self.set_initial_year(min(constants.RRSP_ACCRUAL_MAX))
        income = self.owner.gross_income
        account = self.AccountType(
            self.owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=self.initial_contribution_room, **kwargs)
        account.next_year()
        self.assertEqual(
            account.contribution_room,
            self.initial_contribution_room
            + income * constants.RRSP_ACCRUAL_RATE)

    def test_cont_excess_rollover(self, *args, **kwargs):
        """ Test `contribution_room` with lots of income and no inflows. """
        # Pick the initial year so that we'll know the accrual max. for
        # next year
        self.set_initial_year(min(constants.RRSP_ACCRUAL_MAX) - 1)
        # Use income that's $1000 more than is necessary to max out RRSP
        # contribution room accrual for the year.
        self.owner.gross_income = Money(
            constants.RRSP_ACCRUAL_MAX[self.initial_year + 1]
            / constants.RRSP_ACCRUAL_RATE
            + 1000)
        account = self.AccountType(
            self.owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=self.initial_contribution_room, **kwargs)
        account.next_year()
        # New contribution room should be the max, plus rollover from
        # the previous year.
        self.assertEqual(
            account.contribution_room,
            self.initial_contribution_room
            + Money(constants.RRSP_ACCRUAL_MAX[self.initial_year + 1])
        )

    def test_cont_excess_no_rollover(self, *args, **kwargs):
        """ Test `contribution_room` with lots of income, no rollover. """
        # Pick the initial year so that we'll know the accrual max. for
        # next year
        self.set_initial_year(min(constants.RRSP_ACCRUAL_MAX) - 1)
        # Use income that's $1000 more than is necessary to max out RRSP
        # contribution room accrual for the year.
        self.owner.gross_income = Money(
            constants.RRSP_ACCRUAL_MAX[self.initial_year + 1]
            / constants.RRSP_ACCRUAL_RATE
            + 1000)
        # Try again, but this time contribute the max. in the first year
        account = self.AccountType(
            self.owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=self.initial_contribution_room, **kwargs)
        account.add_transaction(account.contribution_room)
        account.next_year()
        # New contribution room should be the max; no rollover.
        self.assertEqual(
            account.contribution_room,
            Money(constants.RRSP_ACCRUAL_MAX[self.initial_year + 1])
        )

    def test_cont_inf_adjust_basic(self, *args, **kwargs):
        """ Test inflation-adjust for `contribution_room` accrual max. """
        # Start with the last year for which we know the nominal accrual
        # max already. The next year's accrual max will need to be
        # estimated via inflation-adjustment:
        self.set_initial_year(max(constants.RRSP_ACCRUAL_MAX))
        # Inflation-adjust the (known) accrual max for the previous year
        # to get the max for this year.
        max_accrual = (
            constants.RRSP_ACCRUAL_MAX[self.initial_year] *
            self.inflation_adjust(self.initial_year + 1, self.initial_year)
        )
        # Let's have income that's between the initial year's max
        # accrual and the next year's max accrual:
        income = Money(
            (max_accrual +
             constants.RRSP_ACCRUAL_MAX[self.initial_year]
             ) / 2
        ) / constants.RRSP_ACCRUAL_RATE
        self.owner.gross_income = income
        account = self.AccountType(
            self.owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=self.initial_contribution_room, **kwargs)
        account.next_year()
        # New contribution room should be simply determined by the
        # accrual rate set in Constants plus rollover.
        self.assertEqual(
            account.contribution_room,
            self.initial_contribution_room +
            constants.RRSP_ACCRUAL_RATE * income
        )

    def test_cont_inf_adjust_excess(self, *args, **kwargs):
        """ Test inflation-adjust for `contribution_room` accrual max. """
        # Start with the last year for which we know the nominal accrual
        # max already. The next year's accrual max will need to be
        # estimated via inflation-adjustment:
        self.set_initial_year(max(constants.RRSP_ACCRUAL_MAX))
        # Inflation-adjust the (known) accrual max for the previous year
        # to get the max for this year.
        max_accrual = (
            constants.RRSP_ACCRUAL_MAX[self.initial_year] *
            self.inflation_adjust(self.initial_year + 1, self.initial_year)
        )
        # Try again, but now with income greater than the inflation-
        # adjusted accrual max.
        income = Money(max_accrual / constants.RRSP_ACCRUAL_RATE + 1000)
        self.owner.gross_income = income
        account = self.AccountType(
            self.owner, *args,
            rate=0, inflation_adjust=self.inflation_adjust,
            contribution_room=self.initial_contribution_room, **kwargs)
        account.add_transaction(account.contribution_room)  # no rollover
        account.next_year()
        # New contribution room should be the max accrual, since there's
        # no rollover due to the maxed-out contribution last year.
        self.assertAlmostEqual(
            account.contribution_room, Money(max_accrual), 3)

    def test_min_outflow(self, *args, **kwargs):
        """ Test RRSP.min_outflow. """
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
            self.assertEqual(account.min_outflow_limit(), min_outflow)
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

    def test_rrif_explicit(self, *args, **kwargs):
        """ Test explicitly setting RRSP.rrif_conversion_year. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            rrif_conversion_year=None, **kwargs)
        year = account.rrif_conversion_year
        # Advance RRIF conversion by 1 year
        account.rrif_conversion_year = year - 1
        self.assertEqual(account.rrif_conversion_year, year - 1)

    def test_rrif_explicit_late(self, *args, **kwargs):
        """ Test setting RRSP.rrif_conversion_year too far in future. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            rrif_conversion_year=None, **kwargs)
        # The owner will be 71 long before 2100, so we should get an error:
        with self.assertRaises(ValueError):
            account.rrif_conversion_year = 2100

    def test_rrif_implicit_retire_later(self, *args, **kwargs):
        """ Test RRSP.rrif_conversion_year when retiring after 71. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            rrif_conversion_year=None, **kwargs)
        # Set retirement for just after the mandatory conversion year:
        mandatory_year = (
            account.owner.birth_date.year + constants.RRSP_RRIF_CONVERSION_AGE)
        account.owner.retirement_date = mandatory_year + 1
        self.assertEqual(account.rrif_conversion_year, mandatory_year)

    def test_rrif_implicit_retirement(self, *args, **kwargs):
        """ Test RRSP.rrif_conversion_year when retiring before 71. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            rrif_conversion_year=None, **kwargs)
        # Set retirement for just before the mandatory conversion year:
        mandatory_year = (
            account.owner.birth_date.year + constants.RRSP_RRIF_CONVERSION_AGE)
        account.owner.retirement_date = mandatory_year - 1
        self.assertEqual(account.rrif_conversion_year, mandatory_year)

    def test_rrif_unset(self, *args, **kwargs):
        """ Test setting and unsetting RRSP.rrif_conversion_year. """
        account = self.AccountType(
            self.owner, *args,
            inflation_adjust=self.inflation_adjust,
            contribution_room=self.contribution_room,
            rrif_conversion_year=None, **kwargs)
        # Keep track of the implicitly-determined year:
        year = account.rrif_conversion_year
        # Set to a different year:
        account.rrif_conversion_year = year - 1
        # Then unset by passing `None`:
        account.rrif_conversion_year = None
        # Should have the same value as before the earlier assignment:
        self.assertEqual(account.rrif_conversion_year, year)

    def test_spousal_contribution(self, *args, **kwargs):
        """ Tests contributions to spousal RRSP. """
        # Ensure that the spouses have different incomes for testing:
        self.owner.spouse.gross_income = Money(100000)
        self.owner.gross_income = Money(10000)
        # The contribution limits are based on self.owner (not spouse)
        regular_account = self.AccountType(
            self.owner, *args,
            contribution_room=Money(1000), **kwargs)
        spousal_account = self.AccountType(
            self.owner.spouse, *args,
            contributor=self.owner, **kwargs)
        # Use up the contribution room in this year:
        spousal_account.add_transaction(1000)
        spousal_account.next_year()
        if regular_account.this_year < spousal_account.this_year:
            # Also advance regular account if not done automatically:
            regular_account.next_year()
        # Contribution room for the accounts should be the same, and
        # should equal the annual accrual for `self.owner` (without
        # carryover, since we used up all contribution room last year):
        self.assertEqual(
            spousal_account.max_inflow_limit,
            Money(10000) * constants.RRSP_ACCRUAL_RATE)
        self.assertEqual(
            regular_account.max_inflow_limit,
            spousal_account.max_inflow_limit)

if __name__ == '__main__':
    # NOTE: BasicContext is useful for debugging, as most errors are treated
    # as exceptions (instead of returning "NaN"). It is lower-precision than
    # ExtendedContext, which is the default.
    decimal.setcontext(decimal.BasicContext)
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

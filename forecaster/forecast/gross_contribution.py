""" This module provides a Forecast class for use in forecasts.

This is where most of the financial forecasting logic of the Forecaster
package lives. It applies Scenario, Strategy, and Tax information to
determine how account balances will grow or shrink year-over-year.
"""

from collections import defaultdict
from decimal import Decimal
from forecaster.ledger import Money
from forecaster.utility import when_conv

# pylint: disable=too-many-instance-attributes
# This object has a complex state. We could store the records for each
# year in some sort of pandas-style frame or table, but for now each
# data column is its own named attribute.
class GrossContributionForecast(object):
    """ A forecast of each year's gross contributions, before reductions.

    Attributes:
        contribution_strategy (ContributionStrategy): A callable
            object that determines the gross contribution for a
            year. See the documentation for `ContributionStrategy` for
            acceptable args when calling this object.

        tax_carryover (dict[int, Money]): The amount of any refund or
            outstanding tax payable, based on the previous year's
            tax withholdings.
        other_carryover (dict[int, Money]): The amount of inter-year
            carryover (other than tax refunds), such as excess
            withdrawals being recontributed.
        contributions_from_income (dict[int, Money]): The amount to be
            contributed to savings from employment income in each year.
        contributions_from_carryover (dict[int, Money]): The amount to
            be contributed to savings from tax_carryover and
            other_carryover.
        contributions_from_asset_sales (dict[int, Money]): The amount to
            be contributed to savings from asset sales in each year.
        gross_contributions (dict[int, Money]): The amount available to
            contribute to savings, before any reductions. This is the
            sum of net income and various contributions_from_* values.
    """

    def __init__(
        self, contribution_strategy
    ):
        self.tax_carryover = {}
        self.other_carryover = {}
        self.contributions_from_income = {}
        self.contributions_from_carryover = {}
        self.contributions_from_asset_sales = {}
        self.gross_contributions = {}

    def record_gross_contribution(self, year):
        """ Records gross contributions for the year. """
        # First, consider carryover amounts.
        # In the first year, these are $0:
        if year == self.scenario.initial_year:
            self.tax_carryover[year] = Money(0)
            self.other_carryover[year] = Money(0)
        else:
            # If more was withheld than was owed, we have a refund
            # (positive), otherwise we have an amount owing (negative)
            self.tax_carryover[year] = (
                self.total_tax_withheld[year - 1]
                - self.total_tax_owing[year - 1]
            )
            # We determine timing for tax refunds down below, along
            # with timing for contributions from income.

            self.other_carryover[year] = Money(0)  # TODO #30
            self.add_transaction(
                transaction=self.other_carryover[year],
                when=0
            )

        self.asset_sale[year] = Money(0)  # TODO #32
        # TODO: Determine timing of asset sale
        self.add_transaction(
            transaction=self.asset_sale[year],
            when=0
        )

        # Prepare arguments for ContributionStrategy __call__ method:
        # (This determines gross contributions from income)
        retirement_year = self.retirement_year()
        if self.tax_carryover[year] > 0:
            refund = self.tax_carryover[year]
        else:
            refund = Money(0)
        other_contributions = (
            self.other_carryover[year] + self.asset_sale[year]
        )
        self.gross_contributions[year] = self.contribution_strategy(
            year=year,
            refund=refund,
            other_contributions=other_contributions,
            net_income=self.net_income[year],
            gross_income=self.gross_income[year],
            retirement_year=retirement_year
        )

        # Now we need to assign a transaction timing to each
        # contribution. We do this in a source-specific way;
        # i.e. income from each person is assumed to be contributed
        # when they are paid, tax refunds are contributed at the
        # time that refunds are issued by the tax authority,
        # and other contributions (i.e. carryovers) are contributed
        # at the beginning of the year.

        # HACK: The current structure of ContriutionStrategy doesn't
        # let us determine the source of each dollar of contribution,
        # so we need to do that manually here. Changes to
        # ContributionStrategy might break this code!
        contributions_from_income = (
            # Start with the entirety of our contributions
            self.gross_contributions[year]
            # Deduct refunds, prorated based on reinvestment rate
            - refund * self.contribution_strategy.refund_reinvestment_rate
            # Deduct the other contributions identified above
            - other_contributions
            # What's left is just the contributions from income.
        )

        # Since different people can have different payment timings,
        # determine how much of the contributions from income should
        # be assigned to each person (and thus use their timings).
        if self.net_income[year] != 0:
            # Assume each person contributes a share of the gross
            # contributions proportionate to their (net) income:
            weight = {
                person: person.net_income / self.net_income[year]
                for person in self.people
            }
        else:
            # There should be no contributions from income if there
            # is no income:
            assert(contributions_from_income == 0)
            # We still need to determine a weighting, since it's used
            # for tax refunds/etc. Use equal weighting:
            weight = {
                person: Decimal(1) / Decimal(len(self.people))
                for person in self.people
            }

        # Now record those transactions:
        for person in weight:
            # Record contributions from income:
            self.add_transaction(
                transaction=contributions_from_income * weight[person],
                frequency=person.payment_frequency
            )
            # Record contributions from tax refunds:
            # (Only refunds are considered here)
            if self.tax_carryover[year] > 0:
                self.add_transaction(
                    transaction=self.tax_carryover[year] * weight[person],
                    frequency=person.tax_treatment.payment_timing
                )

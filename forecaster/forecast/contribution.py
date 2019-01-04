""" Provides a ContributionForecast class for use by Forecast. """

from forecaster.ledger import Money, recorded_property
from forecaster.forecast.subforecast import SubForecast

class ContributionForecast(SubForecast):
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
        self, initial_year, contribution_strategy
    ):
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # TODO #53 removes this requirement.
        super().__init__(initial_year)

        self.contribution_strategy = contribution_strategy

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # Record carryovers at the start of the year.
        for transaction in (self.tax_carryover, self.other_carryover):
            self.add_transaction(
                transaction, when=0,
                from_account=None, to_account=available)
        # TODO: Determine timing of asset sale.
        # Also: should this receive an Account (e.g. other_assets)
        # as the `from_account`? Conider whether this class should
        # receive that or whether it should be moved to
        # `IncomeForecast`
        self.add_transaction(
            value=self.asset_sale, when=0,
            from_account=None, to_account=available
        )
        # NOTE, TODO: This code assumes `contribution_strategy`
        # returns the amount that will be _spent_ on living expenses,
        # _not_ the amount saved after living expenses. This conforms
        # with the proposals of #40 and #32.
        # Assume living expenses are incurred at the start of each
        # month.
        self.add_transaction(
            value=self.living_expenses, when=0, frequency=12,
            from_account=available, to_account=None)

    @recorded_property
    def tax_carryover(self):
        """ TODO """
        if self.this_year == self.initial_year:
            # In the first year, carryovers are $0:
            return Money(0)
        else:
            # If more was withheld than was owed, we have a refund
            # (positive), otherwise we have an amount owing (negative)
            # TODO: Need to determine the difference between tax
            # withheld and tax owing *in the previous year*.
            # There's currently no mechanism for this class to talk
            # to talk to `TaxForecast`; consider how to address this.
            '''
            self.tax_carryover = (
                self.total_tax_withheld_history[self.this_year - 1]
                - self.total_tax_owing_history[self.this_year - 1]
            )
            '''
            return Money(0)  # TODO

    @recorded_property
    def asset_sale(self):
        """ TODO """
        return Money(0)  # TODO #32

    @recorded_property
    def other_carryover(self):
        """ TODO """
        if self.this_year == self.initial_year:
            # In the first year, carryovers are $0:
            return Money(0)
        else:
            # If more was withheld than was owed, we have a refund
            # (positive), otherwise we have an amount owing (negative)
            return Money(0)  # TODO #30

    @recorded_property
    def living_expenses(self):
        """ TODO """
        # Prepare arguments for call to `contribution_strategy`
        refund = max(self.tax_carryover, Money(0))
        other_contributions = (
            self.other_carryover + self.asset_sale
        )
        # TODO: Receive net_income and gross_income from
        # `IncomeForecast` and `retirement_year` from
        # `Forecast` (or wherever else it might be stored...)
        # pylint: disable=no-member
        self.net_income = Money(0)  # TODO
        self.gross_income = Money(0)  # TODO
        self.retirement_year = Money(0)  # TODO
        return self.contribution_strategy(
            year=self.this_year,
            refund=refund,
            other_contributions=other_contributions,
            net_income=self.net_income,  # TODO
            gross_income=self.gross_income,  # TODO
            retirement_year=self.retirement_year  # TODO
        )

    def gross_contributions(self):
        """ TODO """
        # TODO: Total income available for living expenses
        # should probably be determined by `IncomeForecast`
        income = (
            self.tax_carryover + self.other_carryover
            + self.asset_sale + self.net_income)
        return income - self.living_expenses

""" Provides a ContributionForecast class for use by Forecast. """

from forecaster.ledger import Money, recorded_property
from forecaster.forecast.subforecast import SubForecast

class ContributionForecast(SubForecast):
    """ A forecast of each year's living expenses.

    Attributes:
        contribution_strategy (AccountTransactionStrategy): A callable
            object that determines the contributions to each of the
            plannees' accounts for the year.
            See the documentation for `ContributionStrategy` for
            acceptable args when calling this object.
        accounts (Iterable[Account]): The accounts to be contributed
            to.

        contributions (Money): The amount contributed to retirement
            accounts.
    """

    def __init__(
        self, initial_year, contribution_strategy, accounts
    ):
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # TODO #53 removes this requirement.
        super().__init__(initial_year)

        self.contribution_strategy = contribution_strategy
        self.accounts = accounts

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # We sim to contribute 100% of the amount available.
        # (If the amount available is negative, contribute nothing.)
        self.contributions = max(
            sum(transaction for transaction in available.values()),
            Money(0)
        )

        # Determine transactions for each account:
        transactions = self.contribution_strategy(
            total=self.contributions,
            accounts=self.accounts
        )

        # NOTE: We assume here contributions are made monthly.
        for account in transactions:
            self.add_transaction(
                value=transactions[account],
                when=0.5,
                frequency=12,
                from_account=available,
                to_account=account
            )

    @recorded_property
    def contributions(self):
        """ Contributions to retirement accounts for the year. """
        # We need access to `available` to set this, so it's set
        # via the `update_available` method.
        return Money(0)

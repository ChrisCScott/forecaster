""" Provides a ContributionForecast class for use by Forecast. """

from forecaster.ledger import (
    Money, recorded_property, recorded_property_cached)
from forecaster.forecast.subforecast import SubForecast

class ContributionForecast(SubForecast):
    """ A forecast of each year's living expenses.

    Attributes:
        account_transaction_strategy (AccountTransactionStrategy):
            A callable object that determines the contributions to
            each of the plannees' accounts for the year.
            See the documentation for `ContributionStrategy` for
            acceptable args when calling this object.
        accounts (Iterable[Account]): The accounts to be contributed
            to.

        contributions (Money): The amount contributed to retirement
            accounts.
    """

    def __init__(
        self, initial_year, account_transaction_strategy, accounts
    ):
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # NOTE: Issue #53 removes this requirement.
        super().__init__(initial_year)

        self.account_transaction_strategy = account_transaction_strategy
        self.accounts = accounts

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # NOTE: We assume here contributions are made monthly.

        # pylint: disable=not-an-iterable,unsubscriptable-object
        # pylint can't infer the type of account_transactions
        # because we don't import `AccountTransactionsStrategy`
        for account in self.account_transactions:
            self.add_transaction(
                value=self.account_transactions[account],
                when=0.5,
                frequency=12,
                from_account=available,
                to_account=account
            )

    @recorded_property_cached
    def account_transactions(self):
        """ Transactions for each account, according to the strategy.

        This is what `account_transaction_strategy` returns.
        """
        return self.account_transaction_strategy(
            total=self.contributions,
            accounts=self.accounts
        )

    @recorded_property
    def contributions(self):
        """ Contributions to retirement accounts for the year. """
        # We aim to contribute 100% of the amount available.
        # (If the amount available is negative, contribute nothing.)
        return max(self.total_available, Money(0))

""" Provides a ContributionForecast class for use by Forecast. """

from forecaster.ledger import (
    recorded_property, recorded_property_cached)
from forecaster.forecast.subforecast import SubForecast
from forecaster.utility import Timing

class ContributionForecast(SubForecast):
    """ A forecast of each year's contributions to various accounts.

    Args:
        initial_year (int): The first year of the forecast.
        accounts (Iterable[Account]): The accounts to be contributed
            to.
        account_transaction_strategy (AccountTransactionStrategy):
            A callable object that determines the contributions to
            each of the plannees' accounts for the year.
            See the documentation for `ContributionStrategy` for
            acceptable args when calling this object.

    Attributes:
        contributions (Money): The amount contributed to retirement
            accounts.
    """

    def __init__(
            self, initial_year, accounts, account_transaction_strategy):
        """ Initializes an instance of ContributionForecast. """
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

        # NOTE: We let the account_transactions_strategy determine
        # timing. It will use each account's default timing. Consider
        # whether we should set `strict_timing=True`
        # pylint: disable=not-an-iterable,unsubscriptable-object
        # pylint can't infer the type of account_transactions
        # because we don't import `AccountTransactionsStrategy`
        for account in self.account_transactions:
            self.add_transactions(
                transactions=self.account_transactions[account],
                from_account=available,
                to_account=account)

    @recorded_property_cached
    def account_transactions(self):
        """ Transactions for each account, according to the strategy.

        This is what `account_transaction_strategy` returns.

        Returns:
            dict[Account,dict[Decimal, Money]]: A mapping from
                accounts to transactions (as a `when: value` mapping).
        """
        return self.account_transaction_strategy(
            total=self.total_available,
            accounts=self.accounts)

    @recorded_property_cached
    def contributions(self):
        """ Contributions to retirement accounts for the year. """
        # pylint: disable=not-an-iterable,unsubscriptable-object
        # pylint can't infer the type of account_transactions
        # because we don't import `AccountTransactionsStrategy`
        return sum(
            sum(self.account_transactions[account].values())
            for account in self.account_transactions)

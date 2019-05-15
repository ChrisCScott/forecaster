""" Provides a WithdrawalForecast class for use by Forecast. """

from forecaster.ledger import (
    Money, recorded_property, recorded_property_cached)
from forecaster.forecast.subforecast import SubForecast
from forecaster.utility import transactions_from_timing

class WithdrawalForecast(SubForecast):
    """ A forecast of withdrawals from a portfolio over time.

    Args:
        initial_year (int): The first year of the forecast.
        people (Iterable[Person]): The plannees.
        accounts (Iterable[Account]): Retirement accounts of the
            `people`.
        transaction_strategy (TransactionStrategy):
            A callable object that determines the schedule of
            transactions for any contributions during the year.
            See the documentation for `TransactionStrategy`
            for acceptable args when calling this object.

    Attributes:
        account_transactions (dict[Account, Money]): The total
            amount withdrawn from each account.
        gross_withdrawals (Money): The total amount withdrawn from all
            accounts.
        tax_withheld (Money): Taxes deducted at source on withdrawals
            from savings.
        net_withdrawals (Money): The total amount withdrawn from all
            accounts, net of withholding taxes.
    """

    # pylint: disable=too-many-arguments
    # NOTE: Consider combining the various strategy objects into a dict
    # or something (although it's not clear how this benefits the code.)
    def __init__(
            self, initial_year, people, accounts,
            transaction_strategy):
        """ Initializes an instance of WithdrawalForecast. """
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # NOTE: Issue #53 removes this requirement.
        super().__init__(initial_year)

        # Store input values
        self.people = people
        self.accounts = accounts
        self.transaction_strategy = transaction_strategy

        self.account_transactions = {}
        self.tax_withheld = Money(0)

    def __call__(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().__call__(available)

        self.account_transactions = self.transaction_strategy(
            available, accounts=self.accounts)

        # pylint: disable=not-an-iterable,unsubscriptable-object,no-member
        # pylint can't infer the type of account_transactions
        # because we don't import `TransactionsStrategy`

        # Keep track of tax withholdings before adding transactions to
        # accounts so we can check later for changes.
        tax_withheld = {
            account: account.tax_withheld for account in self.accounts}

        # Record the transactions for each account as dictated by
        # `transaction_strategy`:
        for account in self.account_transactions:
            # NOTE: `available` is used as the `from_account` because
            # values returned by `transaction_strategy` are negative.
            # Thus, money will flow _to_ `available` _from_ `account`.
            self.add_transactions(
                transactions=self.account_transactions[account],
                from_account=available,
                to_account=account)

            # If the tax withholdings have changed (usually we'd expect
            # an increase, but this code works for decreases too) then
            # record a transaction out of the account:
            if account.tax_withheld != tax_withheld[account]:
                # Find the change in tax withholdings for the account
                new_withholdings = account.tax_withheld - tax_withheld[account]
                # Assume they're withheld with the same timing and
                # weighting as the withdrawals themselves:
                transactions = transactions_from_timing(
                    self.account_transactions[account],
                    new_withholdings)
                # The withholdings come from money we've already
                # withdrawn, so remove money from `available`.
                # (transactions will be negative is there's an amount
                # owing, so use `to_account`)
                self.add_transactions(
                    transactions=transactions,
                    to_account=available)
                # Keep track of total tax withheld:
                self.tax_withheld += new_withholdings

    def undo_transactions(self):
        """ Reverses all transactions cause by this subforecast. """
        super().undo_transactions()
        # Reset tax_withheld:
        self.tax_withheld = Money(0)

    @recorded_property_cached
    def gross_withdrawals(self):
        """ Total gross withdrawals for the year. """
        # The amount withdrawn is simply the shortfall in cashflow
        # over the course of the year.
        # TODO: Increase gross withdrawals based on tax liability #34
        # Aim is for `net_withdrawals` to approximate `total_available`.
        return -self.total_available

    @recorded_property
    def net_withdrawals(self):
        """ Total withdrawals, net of withholding taxes, for the year. """
        return self.gross_withdrawals + self.tax_withheld

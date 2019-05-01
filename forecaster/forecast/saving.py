""" Provides a SavingForecast class for use by Forecast. """

from forecaster.ledger import recorded_property_cached
from forecaster.forecast.subforecast import SubForecast

class SavingForecast(SubForecast):
    """ A forecast of each year's contributions to various accounts.

    Args:
        initial_year (int): The first year of the forecast.
        retirement_accounts (Iterable[Account]): Retirement savings
            accounts to be contributed to.
        debt_accounts (Iterable[Debt]): Debt accounts to be repaid.
        transaction_strategy (TransactionStrategy): A callable object
            that determines the contributions to each of the plannees'
            accounts for the year.
            See the documentation for `TransactionStrategy` for
            acceptable args when calling this object.

    Attributes:
        account_transactions (dict[Account, dict[Decimal, Money]]):
            The allocation of transactions to accounts determined by
            `transaction_strategy` for the current year.
        debt_repayment (Money): The amount contributed to debts.
        retirement_savings (Money): The amount contributed to
            retirement savings accounts.
        total (Money): The amount contributed to all accounts.
    """

    def __init__(
            self, initial_year, retirement_accounts, debt_accounts,
            transaction_strategy):
        """ Initializes an instance of SavingForecast. """
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # NOTE: Issue #53 removes this requirement.
        super().__init__(initial_year)

        self.transaction_strategy = transaction_strategy
        self.retirement_accounts = retirement_accounts
        self.debt_accounts = debt_accounts

        self.account_transactions = {}

    def __call__(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().__call__(available)

        self.account_transactions = self.transaction_strategy(available)

        # NOTE: We let the transactions_strategy determine
        # timing. It will use each account's default timing. Consider
        # whether we should set `strict_timing=True`
        for account in self.account_transactions:
            self.add_transactions(
                transactions=self.account_transactions[account],
                from_account=available,
                to_account=account)

        # TODO: Add transactions (with `from_account=None`) to Debt
        # accounts based on how much of their repayments are drawn from
        # living expenses. (See former `ReductionForecast` code for
        # a related implementation of this.)

    @recorded_property_cached
    def debt_repayment(self):
        """ Total debt repaid for the year from savings. """
        # NOTE: We don't add in non-`available` contributions here.
        # Those are considered living expenses, which is not what this
        # class is all about.
        return sum(
            sum(self.account_transactions[account].values())
            for account in self.retirement_accounts
            if account in self.account_transactions)

    @recorded_property_cached
    def retirement_savings(self):
        """ Total amount saved for retirement for the year. """
        return sum(
            sum(self.account_transactions[account].values())
            for account in self.retirement_accounts
            if account in self.account_transactions)

    @recorded_property_cached
    def total(self):
        """ Contributions to accounts for the year. """
        return sum(
            sum(self.account_transactions[account].values())
            for account in self.account_transactions)

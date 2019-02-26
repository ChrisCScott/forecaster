""" Provides a WithdrawalForecast class for use by Forecast. """

from forecaster.ledger import (
    Money, recorded_property, recorded_property_cached)
from forecaster.forecast.subforecast import SubForecast
from forecaster.utility import Timing

class WithdrawalForecast(SubForecast):
    """ A forecast of withdrawals from a portfolio over time.

    Args:
        initial_year (int): The first year of the forecast.
        people (Iterable[Person]): The plannees.
        accounts (Iterable[Account]): Retirement accounts of the
            `people`.
        account_transaction_strategy (AccountTransactionStrategy):
            A callable object that determines the schedule of
            transactions for any contributions during the year.
            See the documentation for `AccountTransactionStrategy`
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
            account_transaction_strategy):
        """ Initializes an instance of WithdrawalForecast. """
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # NOTE: Issue #53 removes this requirement.
        super().__init__(initial_year)

        # Store input values
        self.people = people
        self.accounts = accounts
        self.account_transaction_strategy = account_transaction_strategy

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # pylint: disable=not-an-iterable,unsubscriptable-object,no-member
        # pylint can't infer the type of account_transactions
        # because we don't import `AccountTransactionsStrategy`

        # TODO #59: Limit amount withdrawn to `account_transactions`
        # for each account.
        # It's fine to _prefer_ withdrawing at times when cashflow is
        # negative, but we shouldn't be _increasing_ withdrawals as
        # default behaviour (though maybe we can do it if a flag is set)

        # Set up variables to track progress as we make withdrawals:
        accum = Money(0)
        transactions_total = sum(self.account_transactions.values())
        tax_withheld = {
            account: account.tax_withheld
            for account in self.account_transactions}
        # We want to step through the time-series of transactions
        # and withdraw whenever we dip into negative balance.
        for when in sorted(available.keys()):
            accum += available[when]
            timings = Timing(when=when)
            if accum < 0:  # negative balance - time to withdraw!
                # Withdraw however much we're short by:
                withdrawal = -accum
                for account in self.account_transactions:
                    # Withdraw from each account proportionately to
                    # the total amounts withdrawn from each account:
                    account_transaction = withdrawal * (
                        self.account_transactions[account]
                        / transactions_total)
                    # Add the gross transaction from the account
                    # (not accounting for withholdings):
                    self.add_transaction(
                        value=account_transaction,
                        timings=timings,
                        from_account=account,
                        to_account=available,
                        strict_timing=True
                    )
                    # Now deduct any increased witholding tax
                    # from the new `available` balance:
                    new_withholding = (
                        account.tax_withheld
                        - tax_withheld[account])
                    if new_withholding > 0:
                        self.add_transaction(
                            value=new_withholding,
                            timings=timings,
                            from_account=available,
                            to_account=None,
                            strict_timing=True
                        )
                    tax_withheld[account] += new_withholding
                # NOTE: This essentially adds the *gross* withdrawals
                # to `accum`, with the result being that any taxes
                # withheld will result in a negative end-of-year
                # balance.
                # This can be partially addressed by only adding the
                # *net* withdrawals, except that would result in
                # larger amounts being withdrawn later in the year,
                # and more being withdrawn than was anticipated by
                # `account_transactions`.
                # If we do move in this direction, we need to think
                # carefully about how to redesign this class so that
                # `gross_withdrawals` is determined dynamically and
                # `net_withdrawals` is set up-front.
                # (Right now it's the reverse.)
                accum += withdrawal

    @recorded_property_cached
    def account_transactions(self):
        """ Transactions for each account, according to the strategy.

        This is what `account_transaction_strategy` returns.
        """
        # NOTE: gross_withdrawals is positive, but
        # AccountTransactionStrategy expects a negative value for
        # withdrawals.

        # pylint: disable=invalid-unary-operand-type
        # gross_withdrawals returns Money, which accepts unary `-`
        return self.account_transaction_strategy(
            total=-self.gross_withdrawals,
            accounts=self.accounts)

    @recorded_property_cached
    def gross_withdrawals(self):
        """ Total gross withdrawals for the year. """
        # The amount withdrawn is simply the shortfall in cashflow
        # over the course of the year.
        # TODO: Increase gross withdrawals based on tax liability #34
        # Aim is for `net_withdrawals` to approximate `total_available`.
        return -self.total_available

    @recorded_property
    def tax_withheld(self):
        """ Total tax withheld on withdrawals for the year. """
        return sum(
            (account.tax_withheld for account in self.accounts),
            Money(0))

    @recorded_property
    def net_withdrawals(self):
        """ Total withdrawals, net of withholding taxes, for the year. """
        return self.gross_withdrawals - self.tax_withheld

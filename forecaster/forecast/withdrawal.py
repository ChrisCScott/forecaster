""" Provides a WithdrawalForecast class for use by Forecast. """

from forecaster.ledger import (
    Money, recorded_property, recorded_property_cached)
from forecaster.accounts import Account
from forecaster.forecast.subforecast import SubForecast

class WithdrawalForecast(SubForecast):
    """ A forecast of withdrawals from a portfolio over time.

    Attributes:
        initial_year (int): The first year of the SubForecast.
        people (Iterable[Person]): The plannees.
        accounts (Iterable[Account]): Retirement accounts of the
            `people`.
        scenario (Scenario): Economic information for the forecast
            (e.g. inflation and stock market returns for each year)

        withdrawal_strategy (WithdrawalStrategy): A callable
            object that determines the amount to withdraw for a
            year. See the documentation for `WithdrawalStrategy` for
            acceptable args when calling this object.
        account_transaction_strategy (AccountTransactionStrategy):
            A callable object that determines the schedule of
            transactions for any contributions during the year.
            See the documentation for `AccountTransactionStrategy`
            for acceptable args when calling this object.

        gross_withdrawals (dict[int, Money]): The total amount withdrawn
            from all accounts.
        tax_withheld_on_withdrawals (dict[int, Money]): Taxes deducted
            at source on withdrawals from savings.
        net_withdrawals (dict[int, Money]): The total amount withdrawn
            from all accounts, net of withholding taxes.
    """

    # pylint: disable=too-many-arguments
    # NOTE: Consider combining the various strategy objects into a dict
    # or something (although it's not clear how this benefits the code.)
    def __init__(
        self, initial_year, people, accounts, scenario,
        withdrawal_strategy, account_transaction_strategy
    ):
        """ Constructs an instance of class WithdrawalForecast.

        Args:
            initial_year (int): The first year of the SubForecast.
            people (Iterable[Person]): The plannees.
            accounts (Iterable[Account]): The retirement accounts of
                the plannees.
            scenario (Scenario): Economic information for the forecast
                (e.g. inflation and stock market returns for each year)
            withdrawal_strategy (WithdrawalStrategy): A callable
                object that determines the amount to withdraw for a
                year. See the documentation for `WithdrawalStrategy` for
                acceptable args when calling this object.
            account_transaction_strategy
                (AccountTransactionStrategy):
                A callable object that determines the schedule of
                transactions for any contributions during the year.
                See the documentation for `AccountTransactionStrategy`
                for acceptable args when calling this object.
        """
        # Recall that, as a Ledger object, we need to call the
        # superclass initializer and let it know what the first
        # year is so that `this_year` is usable.
        # NOTE: Issue #53 removes this requirement.
        super().__init__(initial_year)

        # Store input values
        self.people = people
        self.accounts = accounts
        self.scenario = scenario
        self.withdrawal_strategy = withdrawal_strategy
        self.account_transaction_strategy = account_transaction_strategy

    def update_available(self, available):
        """ Records transactions against accounts; mutates `available`. """
        # The superclass has some book-keeping to do before we get
        # started on doing the updates:
        super().update_available(available)

        # NOTE: We assume here withdrawals are made monthly.
        # This is not a very good assumption.
        # TODO: Revise either this class or
        # `AccountTransactionStrategy` to include a `frequency`
        # attribute (and, optionally, a `when` attribute),
        # to be passed here.

        # pylint: disable=not-an-iterable,unsubscriptable-object
        # pylint can't infer the type of account_transactions
        # because we don't import `AccountTransactionsStrategy`
        for account in self.account_transactions:
            self.add_transaction(
                value=-self.account_transactions[account],
                when=0.5,
                frequency=12,  # TODO
                from_account=account,
                to_account=available
            )

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
        # NOTE: This is a pretty brittle way to determine the
        # retirement year. Issues #15 and #28 will require this
        # code to be changed in a future version.
        retirement_year = min(
            person.retirement_date.year for person in self.people)

        return self.withdrawal_strategy(
            people=self.people,
            accounts=self.accounts,
            retirement_year=retirement_year,  # TODO
            total_available=self.total_available,
            year=self.this_year)

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

""" TODO """

from forecaster.accounts import Account
from forecaster.ledger import (
    Money, recorded_property, recorded_property_cached)

class TaxableAccount(Account):
    """ A taxable account, non-registered account.

    This account uses Canadian rules for determining taxable income from
    capital assets. That involves tracking the adjusted cost base (acb)
    of the assets.

    See Account for other attributes not listed below.

    Attributes:
        acb (Money): The adjusted cost base of the assets in the account
            at the start of the year.
        capital_gain (Money): The total capital gains for the year.
            This is evaluated lazily, so it may return different values
            if you add or remove transactions.
    """
    # TODO (v2): Reimplement TaxableAccount based on Asset objects
    # (subclassed from Money), which independently track acb and possess
    # an asset class (or perhaps `distribution` dict defining the
    # relative proportions of sources of taxable income?)
    # Perhaps also implement a tax_credit and/or tax_deduction method
    # (e.g. to account for Canadian dividends)
    # TODO: Define a proportion of growth attributable to capital gains?
    # Potentially subclass this method into a CapitalAsset class where
    # all growth is capital gains - this would allow for modelling
    # non-principle-residence real estate holdings.
    # (But we might want to also model rental income as well...)

    def __init__(
            self, owner, balance=0, rate=0,
            nper=1, inputs=None, initial_year=None, acb=None, **kwargs):
        """ Constructor for `TaxableAccount`.

        See documentation for `Account` for information on args not
        listed below.

        Args:
            acb (Money): The adjusted cost base of the assets in the
                account at the start of `initial_year`.
        """
        # This method does have a lot of arguments, but they're mostly
        # inherited from a superclass. We're stuck with them here.
        # pylint: disable=too-many-arguments

        super().__init__(
            owner=owner, balance=balance, rate=rate, nper=nper,
            inputs=inputs, initial_year=initial_year, **kwargs)

        # If acb wasn't provided, assume there have been no capital
        # gains or losses, so acb = balance.
        self.acb = Money(acb if acb is not None else self.balance)

    # pylint: disable=method-hidden
    # The `self.acb` assignment in `__init__ doesn't actually overwrite
    # this member; it assigns to it via a setter.
    @recorded_property_cached
    def acb(self):
        """ The adjusted cost base of assets in the account this year. """
        # This is set in advance in the previous year when capital_gains
        # is determined.
        # pylint: disable=no-member
        # Pylint gets confused by attributes added via metaclass.
        # they always have a corresponding *_history member:
        return self._acb_history[self.this_year]

    @recorded_property_cached
    def capital_gain(self):
        """ The capital gains (or losses) for this year.

        Note that, unlike other Account attributes, capital_gain is
        given as of the *end* of the year, and is based on transaction
        activity. Therefore, changing any transactions will affect
        capital_gain.
        """
        acb = self.acb
        capital_gain = 0
        transactions = self.transactions

        # ACB is sensitive to transaction order, so be sure to iterate
        # over transactions from first to last.
        # pylint: disable=no-member
        # Pylint gets confused by attributes added via metaclass.
        # `transactions` returns a dict, so it has a `keys` member:
        for when in sorted(transactions.keys()):
            # pylint: disable=unsubscriptable-object
            # Pylint gets confused by attributes added via metaclass.
            # `transactions` returns a dict, so it is subscriptable:
            value = transactions[when]
            # There are different acb formulae for inflows and outflows
            if value >= 0:  # inflow
                acb += value
            else:  # outflow
                # Capital gains are calculated based on the acb and
                # balance before the transaction occurred.
                balance = self.balance_at_time(when) - value
                capital_gain += -value * (1 - (acb / balance))
                acb *= 1 - (-value / balance)

        # We've generated the ACB for the next year, so store it now.
        self._acb_history[self.this_year + 1] = acb
        return capital_gain

    def add_transaction(self, value, when='end'):
        super().add_transaction(value, when)
        # Invalidate the cache for acb and capital gains, since
        # transactions will affect it.
        # pylint: disable=no-member
        # Pylint gets confused by attributes added via metaclass.
        # All `_*_history` members are dicts added automatically:
        self._capital_gain_history.pop(self.this_year, None)
        self._acb_history.pop(self.this_year + 1, None)

    @recorded_property
    def taxable_income(self):
        """ The total tax owing based on activity in the account.

        Tax can arise from realizing capital gains, receiving dividends
        (Canadian or foreign), or receiving interest. Optionally,
        `sources` may define the relative weightings of each of these
        sources of income. See the following link for more information:
        http://www.moneysense.ca/invest/asset-ocation-everything-in-its-place/

        Returns:
            Taxable income for the year from this account as a `Money`
                object.
        """
        # Only 50% of capital gains are included in taxable income
        return self.capital_gain / 2

        # TODO: Apportion growth between asset classes.
        # This would require us to track asset allocation and would
        # enable us to determine how much growth is capital gains,
        # dividends, etc.

    # TODO: Implement tax_withheld and tax_credit.
    # tax_withheld: foreign withholding taxes.
    # tax_credit: Canadian dividend credit

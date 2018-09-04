""" TODO """

from forecaster.accounts import ContributionLimitAccount
from forecaster.utility import build_inflation_adjust

class RegisteredAccount(ContributionLimitAccount):
    """ An abstract base class for RRSPs, TFSAs, etc. """

    # This class is also abstract; it's up to subclasses to implement
    # `next_contribution_room` concretely.
    # pylint: disable=abstract-method

    def __init__(self, *args, inflation_adjust=None, **kwargs):
        """ Inits RegisteredAccount.

        See documentation for `Account` and `ContributionLimitAccount`
        for information on any args not listed below.

        Args:
            inflation_adjust: A method with the following form:
                `inflation_adjust(val, this_year, target_year)`.

                Returns a Decimal object which is the inflation-
                adjustment factor from base_year to target_year.

                Optional. If not provided, all values are assumed to be
                in real terms, so no inflation adjustment is performed.
        """
        super().__init__(*args, **kwargs)
        self.inflation_adjust = build_inflation_adjust(inflation_adjust)

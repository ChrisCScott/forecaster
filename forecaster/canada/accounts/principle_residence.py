""" A Canadian principle residence. """

from forecaster.accounts import Account
from forecaster.ledger import recorded_property

class PrincipleResidence(Account):
    """ A Canadian principle residence. Gains in value are not taxable. """

    @recorded_property
    def taxable_income(self):
        """ The taxable income generated by the account for the year. """
        return self.precision_convert(0) # Money value

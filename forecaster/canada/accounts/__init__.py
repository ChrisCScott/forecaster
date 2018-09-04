""" A package for providing Canadian accounts of various kinds. """

# See forecaster.__init__.py for version, author, and licensing info.

__all__ = [
    'registered_account', 'rrsp', 'tfsa', 'taxable_account',
    'principle_residence'
]

from forecaster.canada.accounts.registered_account import RegisteredAccount
from forecaster.canada.accounts.rrsp import RRSP
from forecaster.canada.accounts.tfsa import TFSA
from forecaster.canada.accounts.taxable_account import TaxableAccount
from forecaster.canada.accounts.principle_residence import PrincipleResidence

""" Tests for Canada-specific Tax subclasses. """

import unittest
from decimal import Decimal
from settings import Settings
from tax_Canada import *
from ledger_Canada import *
from test_helper import *


class TestCanadianResidentTax(unittest.TestCase):
    """ Tests CanadianResidentTax """

    def test_init(self):
        # TODO
        pass

if __name__ == '__main__':
    unittest.main()

''' Unit tests for `People` and `Account` classes. '''

import unittest
from datetime import datetime
from settings import Settings
from ledger import Person
from ledger import Account


class TestPersonMethods(unittest.TestCase):
    """ A test suite for the `Person` class. """

    def test_init(self):
        """ Tests Person.__init__ """
        name = "Testy McTesterson"
        birth_date = datetime(2000, 1, 1)
        retirement_date = datetime(2065, 1, 1)
        person = Person(name, birth_date, retirement_date)
        self.assertEqual(person.name, name)
        self.assertEqual(person.birth_date, birth_date)
        self.assertEqual(person.retirement_date, retirement_date)

        person = Person(name, birth_date)
        self.assertEqual(person.name, name)
        self.assertEqual(person.birth_date, birth_date)
        self.assertIsNone(person.retirement_date)

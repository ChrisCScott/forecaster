""" Unit tests for `AccountLink` """

import unittest
from forecaster import Account, Person, AccountLink

class TestAccountLinkMethods(unittest.TestCase):
    """ Tests AccountLink. """

    def setUp(self):
        """ Sets up variables for testing LinkedLimitAccount """
        super().setUp()

        # Set up some stock owners and accounts for testing:
        self.person1 = Person(
            initial_year=2000,
            name="Test One",
            birth_date="1 January 1980",
            retirement_date="31 December 2030")
        self.person2 = Person(
            initial_year=2000,
            name="Test One",
            birth_date="1 January 1980",
            retirement_date="31 December 2030")
        self.token1 = "token1"
        self.token2 = "token2"
        self.account1 = Account(
            owner=self.person1)
        self.account2 = Account(
            owner=self.person2)
        # Build a link to test against, for convenience:
        self.link = AccountLink(link=(self.person1, self.token1))

    def test_init_basic(self):
        """ Tests __init__ with minimal args. """
        # Just confirm that the link inits without error and sets its
        # parameters correctly.
        link = AccountLink(link=(self.person1, self.token1))
        self.assertEqual(
            (link.owner, link.token),
            (self.person1, self.token1))

    def test_init_copy(self):
        """ Tests __init__ as a copy constructor. """
        # Build a link then copy it and confirm it was copied correctly.
        link1 = AccountLink(link=(self.person1, self.token1))
        link2 = AccountLink(link=link1)
        # Confirm that the copy's attrs are set properly:
        self.assertEqual(
            (link2.owner, link2.token),
            (self.person1, self.token1))
        # The copied link should reference the exact same shared data:
        self.assertIs(link1.group, link2.group)
        self.assertIs(link1.data, link2.data)

    def test_init_optional(self):
        """ Tests __init__ called with default arguments. """
        # Try passing in a default_factory that instructs the
        # AccountLink to generate a list-type `data` record:
        link = AccountLink(
            link=(self.person2, self.token2),
            default_factory=list)
        # `link.data` should point to an empty list:
        self.assertIsInstance(link.data, list)
        self.assertEqual(link.data, [])

    def test_group_basic(self):
        """ Test that group is set properly for 1 account. """
        self.link.link_account(self.account1)
        self.assertEqual(self.link.group, {self.account1})

    def test_group_multi(self):
        """ Test that group is set properly for 2 accounts. """
        self.link.link_account(self.account1)
        self.link.link_account(self.account2)
        # Both accounts should be in the group:
        self.assertEqual(self.link.group, {self.account1, self.account2})

    def test_group_del(self):
        """ Test that group is set properly after removing an account. """
        self.link.link_account(self.account1)
        self.link.link_account(self.account2)
        self.link.unlink_account(self.account1)
        # Only account2 should be in the group:
        self.assertEqual(self.link.group, {self.account2})

    def test_group_separate_links(self):
        """ Test that two links have independent groups. """
        self.link.link_account(self.account1)
        self.link.link_account(self.account2)
        # Build another link with a different owner/token pair:
        link = AccountLink(link=(self.person2, self.token2))
        link.link_account(self.account1)
        # Confirm that the links have independently-set groups:
        self.assertEqual(self.link.group, {self.account1, self.account2})
        self.assertEqual(link.group, {self.account1})

    def test_links_same(self):
        """ Test that two links the same token/owner pair are linked. """
        # Build a new link with the same owner/token pair as an
        # existing link:
        link = AccountLink(link=(self.link.owner, self.link.token))
        # self.link and link should point to the _exact_ same data/group
        self.assertIs(self.link.data, link.data)
        self.assertIs(self.link.group, link.group)

    def test_links_different_token(self):
        """ Test that two links with different tokens aren't linked. """
        # Build a new link with the same owner and a different token:
        link = AccountLink(link=(self.link.owner, self.token2))
        # Modify link's data/group to ensure they're not linked to
        # self.link:
        link.link_account(self.account1)
        link.data["test"] = "test"
        # self.link and link should point to different data/group
        self.assertNotEqual(self.link.data, link.data)
        self.assertNotEqual(self.link.group, link.group)

    def test_links_different_owner(self):
        """ Test that two links with different owners aren't linked. """
        # Build a new link with a different owner and the same token:
        link = AccountLink(link=(self.person2, self.link.token))
        # Modify link's data/group to ensure they're not linked to
        # self.link:
        link.link_account(self.account1)
        link.data["test"] = "test"
        # self.link and link should point to different data/group
        self.assertNotEqual(self.link.data, link.data)
        self.assertNotEqual(self.link.group, link.group)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

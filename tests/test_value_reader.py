''' Unit tests for `ValueReader` class. '''

import unittest
import os
import json
from forecaster.value_reader import ValueReader

class TestValueReader(unittest.TestCase):
    """ Tests the `ValueReader` class. """

    def write(self, vals):
        """ Convenience method for writing to a testing JSON file """
        with open(self.filename, 'w', encoding="utf-8") as file:
            json.dump(
                vals,
                file,
                ensure_ascii=True, # Escape non-ASCII characters
                allow_nan=True, # Required to support float('inf')
                indent=2, # Pretty-print with indenting,
                sort_keys=True) # Sort to make it easier for humans to read)

    def setUp(self):
        """ Use a consistent file for testing: """
        self.filename = "_testing.json"
        self.values = {
            'dict': {'key': 'val'},
            'float': 0.5,
            'int': 1,
            'inf': float('inf'),
            'str': 'str',
            'list': ['a', 'b', 'c']
        }
        self.write(self.values)

    def tearDown(self):
        """ Remove file created during testing. """
        os.remove(self.filename)

    def test_init_read(self):
        """ Test reading a file on init. """
        reader = ValueReader(self.filename)
        self.assertEqual(reader.values, self.values)

    def test_read(self):
        """ Test reading a file with explicit `read()` call. """
        reader = ValueReader()
        reader.read(self.filename)
        self.assertEqual(reader.values, self.values)

    def test_read_again(self):
        """ Test reading from a file, then reading from a different file """
        # Read the file:
        reader = ValueReader(self.filename)
        # Change the file by removing one attribute and adding another:
        del self.values['str']
        self.values['new_attr'] = 'new_val'
        self.write(self.values)
        # Read in the changed file:
        reader.read(self.filename)
        # The new values should match the updated self.values exactly:
        self.assertEqual(reader.values, self.values)

    def test_add_json_attribute(self):
        """ Test `add_json_attribute()` """
        reader = ValueReader()
        reader.add_json_attribute('name', 'value')
        # pylint: disable=no-member
        # The member `name` should be added by the above line
        self.assertEqual(reader.name, 'value')
        # pylint: enable=no-member

    def test_remove_json_attribute(self):
        """ Test `remove_json_attribute()` """
        reader = ValueReader()
        reader.add_json_attribute('name', 'value')
        reader.remove_json_attribute('name')
        # Should be removed as both an attribute and a key in 'values':
        self.assertNotIn('name', reader.__dict__)
        self.assertNotIn('name', reader.values)

    def test_write(self):
        """ Test `write()` """
        # Write a simple datastructure to file:
        reader = ValueReader()
        # Flush the contents of the testing file:
        self.write({})
        # Modify the default values, just to be sure:
        del self.values['str']
        self.values['new_attr'] = 'new_val'
        # Write the modified values to file:
        reader.write(self.filename, self.values)
        # Read them back in manually via the JSON library:
        file = open(self.filename, 'rt', encoding='utf-8')
        decoded_values = json.load(file)
        # The decoded values should be exactly the same:
        self.assertEqual(self.values, decoded_values)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

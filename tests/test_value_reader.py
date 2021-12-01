''' Unit tests for `ValueReader` class. '''

import unittest
import os
import json
from decimal import Decimal
from forecaster.value_reader import (
    ValueReader, ValueReaderAttribute, resolve_data_path)

class TestValueReader(unittest.TestCase):
    """ Tests the `ValueReader` class. """

    def write(self, vals, filename=None):
        """ Convenience method for writing to a testing JSON file """
        if filename is None:
            filename = self.filename
        # Open file in `data` directory if it's a relative path:
        filename = resolve_data_path(filename)
        # Write to the file (creating it if it doesn't already exist):
        with open(filename, 'w', encoding="utf-8") as file:
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
            'infty': float('inf'),
            'str': 'str',
            'list': ['a', 'b', 'c']
        }
        # Write a file to the `data/` dir:
        self.write(self.values)

    def tearDown(self):
        """ Remove file created during testing. """
        # Remove the file that was added during setUp:
        filename = resolve_data_path(self.filename)
        os.remove(filename)
        # Other files added by tests need to be cleaned up by the tests.

    def test_init_read(self):
        """ Test reading a file on init. """
        reader = ValueReader(self.filename)
        self.assertEqual(reader.values, self.values)

    def test_read(self):
        """ Test reading a file with explicit `read()` call. """
        reader = ValueReader()
        reader.read(self.filename)
        self.assertEqual(reader.values, self.values)

    def test_read_abs(self):
        """ Test reading from a file with an absolute path. """
        reader = ValueReader()
        # Build an absolute path to a file outside of the `data/` dir:
        # (This adds a file to the same folder as this test suite)
        filename = os.path.join(os.path.dirname(__file__), self.filename)
        # Write to the file so that we can open it:
        self.write(self.values, filename=filename)
        # Open the file:
        reader.read(self.filename)
        self.assertEqual(reader.values, self.values)
        # Clean up:
        os.remove(filename)

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

    def test_attribute(self):
        """ Test ValueReaderAttribute descriptor """
        # Subclass `ValueReader` to test `ValueReaderAttribute`:
        class TestReader(ValueReader):
            """ A ValueReader with one ValueReaderAttribute attr. """
            test_attr = ValueReaderAttribute()

        # Assign a value to the attribute:
        reader = TestReader()
        value = "new value"
        reader.test_attr = value
        # The value should be accessible via both the `test_attr`
        # attribute and as a value in the `values` dict:
        self.assertEqual(reader.test_attr, value)
        self.assertEqual(reader.values['test_attr'], value)

    def test_attribute_default(self):
        """ Test ValueReaderAttribute descriptor with default value. """
        # Subclass `ValueReader` to test `ValueReaderAttribute`:
        class TestReader(ValueReader):
            """ A ValueReader with one ValueReaderAttribute attr. """
            test_attr = ValueReaderAttribute("default")

        reader = TestReader()
        # Confirm the default value is set correctly:
        self.assertEqual(reader.test_attr, "default")
        # Assign a new value to the attribute:
        reader.test_attr = "value"
        # Confirm that the new value is returned (not the default value)
        self.assertEqual(reader.test_attr, "value")

    def test_attribute_no_default(self):
        """ Test ValueReaderAttribute with use_defaults=False. """
        # Subclass `ValueReader` to test `ValueReaderAttribute`:
        class TestReader(ValueReader):
            """ A ValueReader with one ValueReaderAttribute attr. """
            test_attr = ValueReaderAttribute("default")

        reader = TestReader(use_defaults=False)
        # Confirm the default value is not returned:
        with self.assertRaises(KeyError):
            _ = reader.test_attr #@IgnoreException

    def test_write(self):
        """ Test `write()` """
        reader = ValueReader()
        # Flush the contents of the testing file:
        self.write({})
        # Modify the default values, just to be sure:
        del self.values['str']
        self.values['new_attr'] = 'new_val'
        # Write the modified values to file:
        reader.write(self.filename, self.values)
        # Read them back in manually via the JSON library:
        filename = resolve_data_path(self.filename)
        with open(filename, 'rt', encoding='utf-8') as file:
            decoded_values = json.load(file)
        # The decoded values should be exactly the same:
        self.assertEqual(self.values, decoded_values)

    def test_write_self(self):
        """ Test `write()` called with no explicit values. """
        reader = ValueReader()
        # Flush the contents of the testing file:
        self.write({})
        # Modify the default values, just to be sure:
        del self.values['str']
        self.values['new_attr'] = 'new_val'
        # Write the modified values to file:
        reader.values = self.values
        reader.write(self.filename)
        # Read them back in manually via the JSON library:
        filename = resolve_data_path(self.filename)
        with open(filename, 'rt', encoding='utf-8') as file:
            decoded_values = json.load(file)
        # The decoded values should be exactly the same:
        self.assertEqual(self.values, decoded_values)

    def test_decimal_read(self):
        """ Tests converting to Decimal values on read. """
        reader = ValueReader(self.filename, high_precision=Decimal)
        self.assertEqual(reader.values['float'], Decimal(self.values['float']))

    def test_decimal_write(self):
        """ Tests writing Decimal values and reading back in. """
        # Write a Decimal value to a file:
        writer = ValueReader(high_precision=Decimal)
        writer.values = {'decimal': Decimal(0.5)}
        writer.write(self.filename)
        # Use a fresh ValueReader just to be extra-sure it works:
        reader = ValueReader(self.filename, high_precision=Decimal)
        self.assertEqual(
            reader.values['decimal'],
            Decimal(0.5))

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

""" Tests free methods and classes in the utility.register module. """

import unittest
from forecaster.utility.register import (
    MethodRegister, registered_method, registered_method_named)

class Example(MethodRegister):
    """ A MethodRegister subclass with decorated methods for testing. """
    @registered_method
    def a_method(self):
        return "Hello"

    @registered_method_named("name")
    def a_named_method(self):
        return "My name is"

    def unregistered_method(self):
        raise NotImplementedError("Don't call me!")

    def __init__(self, method):
        self.method = method

class TestMethodRegister(unittest.TestCase):
    """ A test case for `MethodRegister` and its decorators. """

    def test_registered_method_key(self):
        """ Tests calling a `registered_method` attribute by key. """
        example = Example("a_method")
        val = example.call_registered_method(example.method)
        self.assertEqual(val, "Hello")

    def test_registered_method_named_key(self):
        """ Tests calling a `registered_method_named` attribute by key. """
        example = Example("name")
        val = example.call_registered_method(example.method)
        self.assertEqual(val, "My name is")

    def test_registered_method_ref(self):
        """ Tests calling a `registered_method` attribute by ref. """
        example = Example(Example.a_method)
        val = example.call_registered_method(example.method)
        self.assertEqual(val, "Hello")

    def test_registered_method_named_ref(self):
        """ Tests calling a `registered_method_named` attribute by ref. """
        example = Example(Example.a_named_method)
        val = example.call_registered_method(example.method)
        self.assertEqual(val, "My name is")

    def test_invalid_key(self):
        """ Tests calling a key not associated with a registered_method. """
        example = Example("invalid key")
        with self.assertRaises(KeyError):
            _ = example.call_registered_method(example.method)

    def test_invalid_ref(self):
        """ Tests calling a method that isn't registered. """
        example = Example(Example.unregistered_method)
        with self.assertRaises(KeyError):
            _ = example.call_registered_method(example.method)

if __name__ == '__main__':
    unittest.TextTestRunner().run(
        unittest.TestLoader().loadTestsFromName(__name__))

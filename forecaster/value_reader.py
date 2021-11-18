""" Provides a class for reading stored values from files. """

import json
from forecaster.utility.precision import HighPrecisionOptional

class _ValueReaderAttribute(object):
    """ A descriptor for managed attributes of `ValueReader`.

    Attributes with this descriptor are get and set via the `values`
    dict (rather than `__dict__`).
    """
    def __init__(self, name):
        self.name = name

    def __get__(self, obj, objtype=None):
        # Get the value from the `values` dict:
        return obj.values[self.name]

    def __set__(self, obj, value):
        # Set the value in the `values` dict:
        obj.values[self.name] = value

    def __delete__(self, obj):
        # Remove the value from the `values` dict:
        del obj.values[self.name]
        # Also remove this descriptor:
        del obj.__dict__[self.name]

class ValueReader(HighPrecisionOptional):
    """ Reads values from JSON-encoded files.

    Floating-point constants are converted to high-precision types if
    the `high_precision` argument is provided.

    This class provides no attributes, unless `make_attr` is set to
    True, in which case it generates an attribute for each top-level
    entry in the JSON file.

    Arguments:
        filename (str): The filename of a JSON file to read.
            The file must be UTF-8 encoded. Optional.
        make_attr (bool): If True, each top-level entry of the JSON file
            is made an attribute of this ValueReader object, with its
            value set to the value in the JSON file.
            Optional. Defaults to False.
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal).
    """

    def __init__(
            self, filename=None, make_attr=False,
            *, cls=None, high_precision=None):
        # Set up high-precision support:
        super().__init__(high_precision=high_precision)
        # Set up instance attributes:
        self.make_attr = make_attr
        self.values = {}
        # For convenience, let users call `read` as part of init:
        if filename is not None:
            self.read(filename, cls=cls)

    # TODO: Allow this class to resolve relative paths relative to
    # the top-level `settings` folder, rather than relative to the cwd.
    # (Use `os` to determine a path to `settings/` relative to __file__)
    # Consider whether this feature should be enabled by default;
    # maybe so, but consider that an equivalent argument will be
    # provided for `write`, and maybe we don't want to be overwriting
    # files full of default values as default behaviour?

    def read(self, filename, *, cls=None):
        """ Reads in values from file "filename". """
        # Clear all existing JSON attributes from this object:
        if self.make_attr:
            vals = tuple(self.values.keys()) # Copy keys to allow mutation
            for val in vals:
                self.remove_json_attribute(val)

        # Read in JSON values to the `values` dict:
        with open(filename, "rt", encoding="utf-8") as file:
            self.values = json.load(
                file,
                cls=cls, # Custom JSONEncoder
                parse_float=self._parse_float, # High-precision support
                parse_constant=self._parse_constant) # Support +/- infinity

        if not isinstance(self.values, dict):
            raise TypeError('JSON file must provide dict of key: value pairs')

        # Expose all values as attributes if requested:
        if self.make_attr:
            for (key, val) in self.values:
                self.add_json_attribute(key, val)

    def _parse_float(self, val):
        """ Parses float values (except infinite/NaN).

        Supports high-precision types.
        """
        # Attempt casting to high-precision if enabled:
        if self.high_precision is not None:
            # `val` is received as a str. Some high-precision types
            # can cast directly from str (and prefer to do so, to avoid
            # loss of precision), so try that first:
            try:
                return self.high_precision(val)
            # If that doesn't work, cast to float first:
            # pylint: disable=bare-except
            # We don't know what kind of exception the high-precision
            # type might raise
            except:
                fval = float(val)
                return self.high_precision(fval)
            # pylint: enable=bare-except
        # If we're not in high-precision mode, simply return a float:
        return float(val)

    def _parse_constant(self, val):
        """ Parses 'Infinity', '-Infinity', and 'NaN' from JSON files. """
        # Construct an appropriately-typed numeric value:
        inf = float('inf')
        if self.high_precision is not None:
            inf = self.high_precision(inf)
        # Parse the infinite values appropriately:
        if val == 'Infinity':
            return inf
        if val == '-Infinity':
            return -inf

        # We don't support non-infinite special constants (which, as of
        # Python 3.7, is just 'NaN'):
        raise ValueError("'" + val + "' value not supported.")

    def add_json_attribute(self, name, value):
        """ Adds a new attribute that's stored in the `values` dict:

        This method wraps new attributes in the `_ValueReaderAttribute`
        descriptor to ensure that they are added to the `values` dict.
        """
        # Create a descriptor for this attribute:
        descriptor = _ValueReaderAttribute(name)
        # Add the descriptor as an attribute:
        self.__setattr__(name, descriptor)
        # Now set the value of the attribute using the descriptor:
        self.__setattr__(name, value)

    def remove_json_attribute(self, name):
        """ Removes an attribute added by `add_json_attribute`. """
        # Call the descriptor's delete method to delete the value:
        self.__delattr__(name)
        # Remove the descriptor to get rid of the attribute entirely:
        if name in self.__dict__:
            self.__dict__.pop(name)

    # TODO: Implement relative path resolution, as described above.

    def write(self, filename, vals, *, cls=None):
        """ Writes values to a UTF-8 encoded JSON file.

        filename (str): The filename of the JSON file to write.
        vals (dict[str, Any] | ValueReader): A mapping of str-valued
            keys to values, to be represented in JSON and retrievable by
            ValueReader. Or, alternatively, a ValueReader object; in
            this case all values in its `values` dict are encoded.
        cls (JSONEncoder): A custom JSONEncoder with an overloaded
            `default` method for serializing additional types. See
            documentation for the `cls` argument to `json.dump` for more
            information. Optional.
        """
        # For convenience
        if isinstance(vals, ValueReader):
            vals = vals.values

        with open(filename, "w", encoding="utf-8") as file:
            json.dump(
                vals,
                file,
                ensure_ascii=True, # Escape non-ASCII characters
                allow_nan=True, # Required to support float('inf')
                indent=2, # Pretty-print with indenting,
                cls=cls, # Allow caller to provide custom JSONEncoder
                sort_keys=True) # Sort to make it easier for humans to read

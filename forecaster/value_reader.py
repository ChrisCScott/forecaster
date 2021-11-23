""" Provides a class for reading stored values from files. """

import json
from forecaster.utility.precision import HighPrecisionOptional

INFINITY = float('inf')

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

class HighPrecisionJSONEncoder(json.JSONEncoder):
    """ Extends JSONEncoder to support high-precision numeric types.

    This class encodes high-precision types losslessly to strings and,
    on read, converts back from string to the high-precision type.

    For high-precision types that support `__str__` and can init from
    the resulting string (e.g. `Decimal(str(Decimal(5)))` inits as
    expected), all you need to do is pass `high_precision`. For types
    that don't support this, be sure to provide suitable methods for
    both `high_precision` and `high_precision_serialize`.

    Any argument supported by `JSONEncoder` is also supported by this
    class. It can be provided as the `cls` argument to `json.load` and
    `json.dump`. (It also supports decoding.)

    Arguments:
        high_precision (Callable[[str, float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single argument (float or str) and returns a value in a
            high-precision type (e.g. Decimal). Optional.
        high_precision_serialize (Callable[[HighPrecisionType], str]):
            A callable object that converts a high-precision numeric
            type to str.
            Optional. Defaults to HighPrecisionType.__str__.
    """

    def __init__(
            self, *args, high_precision=None, high_precision_serialize=None,
            **kwargs):
        super().__init__(*args, **kwargs)
        # Declare member attributes:
        self.high_precision_type = None
        self.high_precision_serialize = None
        # If we're in high-precision mode, learn about the
        # high-precision type:
        if high_precision is not None:
            # Infer the high-precision type being used and store it:
            self.high_precision_type = type(high_precision(0))
            # If no serialization method has been passed, try casting to float:
            # NOTE: This is a lossy conversion. Sadly, there is no
            # support in JSONEncoder for subclasses to represent
            # non-float objects numerically without casting to float.
            # The only alternative is to cast to str, which is lossless
            # but then either requires:
            #   (a) client code to know which values should be numerical
            #       and convert them from str to a high-precision type
            #       or
            #   (b) the decoder to check every str for convertability to
            #       the high-precision type.
            # On the plus side, any file that's being read will be read
            # in losslessly, so (e.g.) a manually-typed file or one
            # generated via `simplejson` with Decimal inputs will be
            # losslessly read in.
            if high_precision_serialize is None:
                def high_precision_serialize(val):
                    return float(val)
            self.high_precision_serialize = high_precision_serialize

    def default(self, o):
        """ Attempts to serialize high-precision numeric types. """
        # Serialize high-precision numbers using the custom method:
        if (
                self.high_precision_type is not None and
                isinstance(o, self.high_precision_type)):
            return self.high_precision_serialize(o)
        # Otherwise, raise an error:
        else:
            super().default(o)

class ValueReader(HighPrecisionOptional):
    """ Reads values from JSON-encoded files.

    Floating-point constants are converted to high-precision types if
    the `high_precision` argument is provided or if a `JSONDecoder`
    that supports high-precision types.

    This class provides no attributes, unless `make_attr` is set to
    True, in which case it generates an attribute for each top-level
    entry in the JSON file.

    Examples:
        settings = ValueReader(
            "filename.json",  # Read in from this file
            make_attr=True,  # Create attribute for each top-level key
            high_precision=Decimal)  # Use Decimal representation

    Arguments:
        filename (str): The filename of a JSON file to read.
            The file must be UTF-8 encoded. Optional.
        make_attr (bool): If True, each top-level entry of the JSON file
            is made an attribute of this ValueReader object, with its
            value set to the value in the JSON file.
            Optional. Defaults to False.
        encoder_cls (JSONEncoder): A custom JSONEncoder with an
            overloaded `default` method for serializing additional
            types. See documentation for the `cls` argument to
            `json.dump` for more information.
            Optional. Defaults to `HighPrecisionJSONEncoder`.
        decoder_cls (JSONDecoder): A custom JSONDecoder that supports
            reading in high-precision numeric types serialized in the
            way that `encoder_cls` emits.
            Optional. Defaults to `JSONDecoder`.
        high_precision (Callable[[float], HighPrecisionType]): A
            callable object, such as a method or class, which takes a
            single `float` argument and returns a value in a
            high-precision type (e.g. Decimal). Optional.
        high_precision_serialize (Callable[[HighPrecisionType], str]):
            A callable object that converts a high-precision numeric
            type to str.
            Optional. Defaults to HighPrecisionType.__str__.
        numeric_convert (bool): If True, any float-convertible str
            keys or values will be converted to a numeric type on read
            (int if appropriate, otherwise a high-precision type or
            float, depending on whether this instance supports
            high-precision). Optional. Defaults to True.
    """

    def __init__(
            self, filename=None, make_attr=False,
            *, encoder_cls=None, decoder_cls=None,
            high_precision=None, high_precision_serialize=None,
            numeric_convert=True):
        # Set up high-precision support:
        super().__init__(high_precision=high_precision)
        self.high_precision_serialize = high_precision_serialize

        # Set up instance attributes:
        self.make_attr = make_attr
        self.values = {}
        self.encoder_cls = encoder_cls
        self.decoder_cls = decoder_cls
        # For convenience, let users call `read` as part of init:
        if filename is not None:
            self.read(filename, numeric_convert=numeric_convert)

    # TODO: Allow this class to resolve relative paths relative to
    # the top-level `settings` folder, rather than relative to the cwd.
    # (Use `os` to determine a path to `settings/` relative to __file__)
    # Consider whether this feature should be enabled by default;
    # maybe so, but consider that an equivalent argument will be
    # provided for `write`, and maybe we don't want to be overwriting
    # files full of default values as default behaviour?

    def read(self, filename, *, numeric_convert=True):
        """ Reads in values from file "filename".

        Note that if `numeric_convert` is `True` then strings that are
        float-convertible will be converted to a numeric type. Keep this
        in mind if the JSON file has keys or values with like "inf",
        "Infinity", or "nan", which will be converted. If this is not
        desired, set `numeric_convert` to `False` and convert manually.

        Arguments:
            filename (str): The filename of a JSON file to read.
                The file must be UTF-8 encoded.
            numeric_convert (bool): If True, any float-convertible str
                keys or values will be converted to a numeric type
                (int if appropriate, otherwise a high-precision type or
                float, depending on whether this instance supports
                high-precision). Optional. Defaults to True.
        """
        # Clear all existing JSON attributes from this object:
        if self.make_attr:
            vals = tuple(self.values.keys()) # Copy keys to allow mutation
            for val in vals:
                self.remove_json_attribute(val)

        # Read in JSON values to the `values` dict:
        with open(filename, "rt", encoding="utf-8") as file:
            self.values = json.load(
                file,
                cls=self.decoder_cls, # Custom JSONDecoder
                parse_float=self._parse_float, # High-precision support
                parse_constant=self._parse_constant) # Support +/- infinity

        # Convert str-encoded numbers to numeric types:
        if numeric_convert:
            self.values = self._numeric_convert(self.values)

        if not isinstance(self.values, dict):
            raise TypeError('JSON file must provide dict of key: value pairs')

        # Expose all values as attributes if requested:
        if self.make_attr:
            for (key, val) in self.values.items():
                # Just in case we converted a top-level value to a
                # numeric type, enforce string representation here:
                if not isinstance(key, str):
                    key = str(key)
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
        inf = INFINITY
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

    def _numeric_convert(self, vals):
        """ Converts str-encoded entries in a JSON tree to numeric type.

        This method is high-precision-aware.
        """
        # JSONEncoder will emit only these types:
        #   dict
        #   list
        #   str
        #   int
        #   float
        #   True
        #   False
        #   None
        # Need to iterate over dicts and lists, attempt to convert str,
        # and for the rest: just return the raw value.

        # Attempt to convert both keys and values in a dict:
        if isinstance(vals, dict):
            return {
                self._numeric_convert(key): self._numeric_convert(val)
                for (key, val) in vals.items()}
        # Attempt to convert each item of a list:
        if isinstance(vals, list):
            return [self._numeric_convert(val) for val in vals]
        # The remaining values are either str or non-convertible.
        # Dismiss the non-convertible values first:
        if not isinstance(vals, str):
            return vals

        # Now we know we're working with a str.
        # See whether this value is numeric:
        try:
            float_val = float(vals) #@IgnoreException
        except ValueError:
            # If we can't convert to number, return the unconverted str.
            return vals

        # Now we know `vals` is a numeric-convertible str. Convert it:
        # Prefer int representation if possible:
        if float_val % 1 == 0:
            # `float_val % 1` is `NaN` for infinite or NaN values,
            # and is a non-zero number for any floating-point value.
            # Thus, if this test passes, we have an integer value.
            return int(float_val)
        # Use high-precision numeric type if supported:
        if self.high_precision is not None:
            return self.high_precision(vals)
        # Otherwise, use float:
        return float_val

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

    def write(self, filename, vals=None):
        """ Writes values to a UTF-8 encoded JSON file.

        filename (str): The filename of the JSON file to write.
        vals (dict[str, Any] | ValueReader): A mapping of str-valued
            keys to values, to be represented in JSON and retrievable by
            ValueReader. Or, alternatively, a ValueReader object; in
            this case all values in its `values` dict are encoded.
        """
        # If no values are provided, use this object's `values`:
        if vals is None:
            vals = self.values

        # Format output as follows:
        encoder_args = {
            'ensure_ascii': True, # Escape non-ASCII characters
            'allow_nan': True, # Required to support float('inf')
            'indent': 2, # Pretty-print with indenting,
            'sort_keys': True # Sort to make it easier for humans to read
        }

        # Use the custom encoder provided by client code, if any:
        cls = self.encoder_cls
        # By default, use our own high-precision-aware encoder:
        if cls is None:
            cls = HighPrecisionJSONEncoder
            # Support high precision, if applicable:
            encoder_args['high_precision'] = self.high_precision
            encoder_args['high_precision_serialize'] = (
                self.high_precision_serialize)

        # Write the serialized values to file:
        with open(filename, "w", encoding="utf-8") as file:
            json.dump(vals, file, cls=cls, **encoder_args)

""" Provides a class for reading stored values from files. """

import os
import json
from forecaster.utility.precision import HighPrecisionOptional

INFINITY = float('inf')
DIR_PATH = os.path.dirname(__file__)
DATA_PATH = os.path.join(DIR_PATH, "../data/")

def resolve_data_path(filename):
    """ Returns an absolute path to `filename`.

    If `filename` is a relative path, it is resolved to an absolute
    path with a root in this package's `forecaster/data/` directory.
    If `filename` is an absolute path, it is returned unchanged.
    """
    # If this is a bare filename, assume it's in /data
    if not os.path.isabs(filename):
        filename = os.path.join(DATA_PATH, filename)
    # Don't modify absolute paths.
    return filename

class ValueReaderAttribute(object):
    """ A descriptor for managed attributes of `ValueReader`.

    Attributes with this descriptor are get and set via the `values`
    dict (rather than `__dict__`).
    """

    def __init__(self, default=None):
        self.default = default
        self.name = None # set in __set_name__

    def __set_name__(self, owner, name):
        # Called when the class `owner` is defined, passes the name
        # of the attribute to which this descriptor is assigned.
        self.name = name

    def __get__(self, obj, objtype=None):
        # If a value hasn't been read in for this attribute, use the
        # default value if one has been provided (and if the calling
        # object has enabled this functionality via `use_defaults`):
        if (
                self.name not in obj.values and
                self.default is not None and
                hasattr(obj, 'use_defaults') and
                obj.use_defaults):
            return self.default
        # Return the value read in from file (or raise a KeyError if
        # it's missing and there's no default):
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
        numeric_convert (bool): If `high_precision_serialize` is not
            provided, the encoder will attempt to cast high-precision
            numbers losslessly to `str` if this value is True, or
            will attempt lossy conversion to `float` if this value is
            False. Optional; defaults to True.
    """

    def __init__(
            self, *args, high_precision=None, high_precision_serialize=None,
            numeric_convert=True, **kwargs):
        super().__init__(*args, **kwargs)
        # Declare member attributes:
        self.high_precision_type = None
        self.high_precision_serialize = None
        # If we're in high-precision mode, learn about the
        # high-precision type:
        if high_precision is not None:
            # Infer the high-precision type being used and store it:
            self.high_precision_type = type(high_precision(0))
            # If no serialization method has been passed, cast to
            # either float to str (depending on whether str-numeric
            # conversion is supported):
            if high_precision_serialize is None:
                # If we support conversion to str, convert to str:
                # pylint: disable=function-redefined
                # We're intentionally redefining this function.
                if numeric_convert:
                    def high_precision_serialize(val):
                        return str(val)
                # If we don't support conversion to str, convert to
                # float. NOTE: This conversion is lossy!
                else:
                    def high_precision_serialize(val):
                        return float(val)
                # pylint: enable=function-redefined
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

    Values read from the JSON file are stored in a `values` dict.
    Subclasses can expose these values as attributes by providing
    `ValueReaderAttribute` instances as class variables with the same
    name as a key in the `values` dict. For example, setting the class
    variable `attr = ValueReaderAttribute()` will result in calls to
    `ValueReader(filename).attr` to return the value associated with the
    `"attr"` key in the JSON file named by `filename` (i.e. it is
    equivalent to calling `ValueReader(filename).values['attr']`).
    See documentation for `ValueReaderAttribute` for more information.

    Relative paths in `filename` are resolved relative to
    `forecaster/data/`, not the current working directory.
    If you want to point to a file anywhere else, use an absolute path.

    Floating-point constants are converted to high-precision types if
    the `high_precision` argument or a `JSONDecoder` that supports
    high-precision types are provided.

    Examples:
        settings = ValueReader(
            "filename.json",  # Read this file in forecaster/data
            high_precision=Decimal)  # Use Decimal representation

    Arguments:
        filename (str): The filename of a JSON file to read.
            The file must be UTF-8 encoded. Optional.
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
        use_defaults (bool): If True, any `ValueReaderAttribute` which
            doesn't have a value read in from file will return its
            default value if one is provided in the class definition.
            Optional. Defaults to True.
    """

    def __init__(
            self, filename=None, *,
            encoder_cls=None, decoder_cls=None,
            high_precision=None, high_precision_serialize=None,
            numeric_convert=True, use_defaults=True):
        # Set up high-precision support:
        super().__init__(high_precision=high_precision)
        self.high_precision_serialize = high_precision_serialize

        # Set up instance attributes:
        self.values = {}
        self.encoder_cls = encoder_cls
        self.decoder_cls = decoder_cls
        self.use_defaults = use_defaults
        # For convenience, let users call `read` as part of init:
        if filename is not None:
            self.read(filename, numeric_convert=numeric_convert)

    def read(self, filename, *, numeric_convert=True):
        """ Reads in values from file "filename".

        Any existing values in `self.values` are cleared - only values
        read in from `filename` will be stored.

        Relative paths are resolved relative to `forecaster/data/`, not
        the current working directory. If you want to point to a file
        anywhere else, use an absolute path.

        Note that if `numeric_convert` is `True` then strings that are
        float-convertible will be converted to a numeric type. Keep this
        in mind if the JSON file has keys or values like "inf",
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

        Raises:
            FileNotFoundError: No such file or directory.
        """
        # Clear all existing JSON attributes from this object:
        self.values.clear()

        # If this is a bare filename, assume it's in /data
        filename = resolve_data_path(filename)

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

        filename = resolve_data_path(filename)

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

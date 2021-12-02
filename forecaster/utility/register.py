""" Provides decorators for providing classes with registrable methods. """

from functools import partial

_REGISTERED_METHOD_ATTR = '_registered_method'
_REGISTERED_METHOD_KEY = '_registered_method_key'

def registered_method_named(key):
    """ A decorator for registered methods with friendly names. """
    return partial(registered_method, key=key)

def registered_method(func, key=None):
    """ A decorator for registered methods. """
    setattr(func, _REGISTERED_METHOD_ATTR, True)
    if key is None:
        key = func.__name__
    setattr(func, _REGISTERED_METHOD_KEY, key)
    return func

class MethodRegister:
    """ A class with registered methods.

    In practice, this class is subclassed by classes that provide many
    possible, user-selectable behaviours (such as different strategies
    or sampling methods). Those classes will usually override a method
    like `__call__` or `__iter__` to wrap `call_registered_method`.

    Example:
        ```
        class Example(MethodRegister):

            @registered_method
            def a_method(self):
                print("Hello")

            @registered_method_named("name")
            def a_named_method(self):
                print("My name is")

            def __init__(self, method):
                self.method = method

        e1 = Example(Example.a_method)
        e1.call_registered_method(e1.method)  # prints "Hello!"

        e2 = Example("name")
        e2.call_registered_method(e2.method)  # prints "My name is"
        ```
    """

    def __init_subclass__(cls):
        """ Registers methods decorated by `registered_method`[`_named`]. """
        # We could declare this attr in __init__, but then it would just
        # be attached to the instance. We need to init at class
        # definition time, so declare it here (but avoid overwriting
        # it if aready declared by an earlier subclass):
        if not hasattr(cls, 'registered_methods'):
            cls.registered_methods = {}
        # Find the attributes decorated by `registered_method*`:
        for name in dir(cls):
            attr = getattr(cls, name)
            # Functions with _registered_method set to True are decorated:
            if callable(attr) and getattr(attr, _REGISTERED_METHOD_ATTR, False):
                # If a custom key has been defined for this method,
                # use that key, otherwise use the function name:
                key = getattr(attr, _REGISTERED_METHOD_KEY, name)
                cls.registered_methods[key] = attr

    def call_registered_method(self, method, *args, **kwargs):
        """ Calls `method` decorated by `registered_method`[`_named`].

        It might seem trivial to call a method, but we can identify them
        in three ways, each with a different call pattern:
            1. By key (e.g. a method decorated with
                `registered_method_named(key)`).
            2. Via a reference to an unbound (class) method.
            3. Via a reference to a bound (instance) method.

        This method identifies the correct call pattern and calls the
        method with `*args` and `**kwargs` as arguments.

        Raises:
            KeyError: `method` is not a registered method or a key for one.
        """
        # If `method` is a key, use the method that's registered to it:
        if method in self.registered_methods:
            method = self.registered_methods[method]
        # If `method` has a registered_method key, use that:
        elif hasattr(method, _REGISTERED_METHOD_KEY):
            key = getattr(method, _REGISTERED_METHOD_KEY)
            method = self.registered_methods[key]
        # Otherwise, a registered method (or its key) wasn't passed:
        else:
            # Try to get a user-friendly name for the `method` arg:
            if hasattr(method, '__name__'):
                name = method.__name__
            else:
                name = str(method)
            raise KeyError(
                "\"Parameter \"" + name +
                "\" is not a registered method or a key for one.")

        # `registered_method`-decorated methods are *unbound*, so pass
        # `self` as the first parameter (i.e. as `self`):
        return method(self, *args, **kwargs)

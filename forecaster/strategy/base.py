""" A module that provides generic Strategy infrastructure.

In particular, the modules offers a `Strategy` base class and a
complementary `@strategy_method` decorator for use by subclasses.
"""

import inspect
from forecaster.utility.precision import HighPrecisionOptional

def strategy_method(key):
    """ A decorator for strategy methods, used by Strategy subclasses

    Methods decorated with this decorator will be automatically added
    to the dict `strategies`, which is an attribute of the subclass.
    This happens at class definition time; you need to manually register
    strategy methods that are added dynamically.

    Example::

        class ExampleStrategy(Strategy):
            @strategy_method('method key')
            def _strategy_method(self):
                return

        ExampleStrategy.strategies['method key'] == \
            ExampleStrategy._strategy_method

    """
    def decorator(function):
        """ Decorator returned by strategy_method.

        Adds strategy_key attribute.
        """
        function.strategy_key = key
        return function
    return decorator


class StrategyType(type):
    """ A metaclass for Strategy classes.

    This metaclass inspects the class for any `@strategy(key)`-decorated
    methods and generates a `strategies` dict of {key, func} pairs. This
    `strategies` dict is then accessible from the class interface.

    NOTE: One side-effect of this approach is that strategy methods are
    collected only once, at definition time. If you want to add a
    strategy to a class later, you'll need to manually add it to the
    subclass's `strategies` dict.
    TODO: Add static class methods to Strategy to register/unregister
    strategy methods? (consider using signature `(func [, key])`)
    """
    def __init__(cls, *args, **kwargs):
        # First, build the class normally...
        super().__init__(*args, **kwargs)
        # ... then add a `strategies` dict by looking up every attribute
        # that has a `strategy_key` attribute of its own.
        cls.strategies = {
            s[1].strategy_key: s[1]
            for s in inspect.getmembers(
                cls, lambda x: hasattr(x, 'strategy_key')
            )
        }


# pylint: disable=too-few-public-methods
class Strategy(HighPrecisionOptional, metaclass=StrategyType):
    """ An abstract callable class for determining a strategy.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function. All functions have the same call signature and
            return value; this is the call signature of the Strategy
            object.

            See each subclass's documentation for more information on
            the call signature for the subclass.
    """

    def __init__(self, strategy, *, high_precision=None, **kwargs):
        # NOTE: `strategy` is required here, but providing a suitable
        # default value in __init__ of each subclass is recommended.

        super().__init__(high_precision=high_precision, **kwargs)

        # If the method itself was passed, translate that into the key
        if (
                not isinstance(strategy, str)
                and hasattr(strategy, 'strategy_key')):
            strategy = strategy.strategy_key
        self.strategy = strategy

        # Check types and values:
        if not isinstance(self.strategy, str):
            raise TypeError('Strategy: strategy must be a str')
        if self.strategy not in type(self).strategies:
            raise ValueError('Strategy: Unsupported strategy ' +
                             'value: ' + self.strategy)

    def __call__(self, *args, **kwargs):
        """ Makes the Strategy object callable. """
        # Call the selected strategy method.
        # The method is unbound (as it's assigned at the class level) so
        # technically it's a function. We must pass `self` explicitly.
        return type(self).strategies[self.strategy](self, *args, **kwargs)

    @staticmethod
    def _param_check(var, var_name, var_type=None):
        """ Checks that `var` is not None and is of type(s) var_type. """
        if var is None:
            raise ValueError('Strategy: ' + var_name + ' is required.')
        if var_type is not None:
            if not isinstance(var, var_type):
                raise TypeError('Strategy: ' + var_name + ' must be of ' +
                                'type(s) ' + str(var_type))

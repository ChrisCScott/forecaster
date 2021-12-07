""" A module that provides generic Strategy infrastructure.

In particular, the modules offers a `Strategy` base class and a
complementary `@strategy_method` decorator for use by subclasses.
"""

from forecaster.utility import (
    MethodRegister, registered_method_named,
    HighPrecisionHandler)

# Rename registered_method_named for convenience when subclassing.
strategy_method = registered_method_named

class Strategy(HighPrecisionHandler, MethodRegister):
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
        self.strategy = strategy

    def __call__(self, *args, **kwargs):
        """ Makes the Strategy object callable. """
        # Call the selected strategy method.
        # The method is unbound (as it's assigned at the class level) so
        # technically it's a function. We must pass `self` explicitly.
        return self.call_registered_method(self.strategy, *args, **kwargs)

    @staticmethod
    def _param_check(var, var_name, var_type=None):
        """ Checks that `var` is not None and is of type(s) var_type. """
        if var is None:
            raise ValueError('Strategy: ' + var_name + ' is required.')
        if var_type is not None:
            if not isinstance(var, var_type):
                raise TypeError('Strategy: ' + var_name + ' must be of ' +
                                'type(s) ' + str(var_type))

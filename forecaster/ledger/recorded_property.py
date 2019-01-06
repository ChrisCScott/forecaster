""" TODO """



class recorded_property(property):
    """ A decorator for properties that record their annual amounts.

    Methods decorated with this decorator (a) are decorated with the
    @property decorator, and (b) sets a recorded_property flag attribute
    on the decorated property.

    `recorded_property`-decorated properties are processed by the Ledger
    metaclass to automatically generate have a <name>_history property,
    and a _<name> dict attribute to the class.

    Example::

        class ExampleLedger(Ledger):
            @recorded_property
            def taxable_income(self):
                return <formula for taxable_income>

    """
    # This is a decorator, which mimics the naming convention followed by
    # `property` (i.e. lowercase)
    # pylint: disable=invalid-name

    def __init__(self, fget=None, doc=None):
        """ Init recorded_property.

        This wraps the getter received via the `@recorded_property`
        decoration into a method that returns a value from a dict of
        recorded values if such a value is present for the key
        `self.this_year`. If not, it calls the getter. No setter may be
        provided; this decorator automatically generates one based on
        this dict of recorded values.
        """
        self.__name__ = fget.__name__
        self.history_prop_name = self.__name__ + '_history'
        self.history_dict_name = '_' + self.history_prop_name

        # Getter returns stored value if available, otherwise generates
        # a new value (and does not cache it - we only automatically
        # store a value when next_year() is called)
        def getter(obj):
            """ Returns cached value in \\*_history dict if available. """
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year in history_dict:
                return history_dict[obj.this_year]
            else:
                return fget(obj)

        def setter(obj, val):
            """ Adds value to cache, without overwriting user input. """
            # Don't overwrite a value provided via an inputs dict:
            if not (
                self.__name__ in obj.inputs and
                obj.this_year in obj.inputs[self.__name__]
            ):
                history_dict = getattr(obj, self.history_dict_name)
                history_dict[obj.this_year] = val

        def deleter(obj):
            """ Removes a cached value, without removing user input. """
            # Don't delete a value provided via an inputs dict:
            if not (
                self.__name__ in obj.inputs and
                obj.this_year in obj.inputs[self.__name__]
            ):
                history_dict = getattr(obj, self.history_dict_name)
                if obj.this_year in history_dict:
                    del history_dict[obj.this_year]

        super().__init__(fget=getter, fset=setter, fdel=deleter, doc=doc)

        def history(obj):
            """ Returns history dict for the property. """
            # For non-cached properties, the history dict might
            # not include a property for the current year.
            # NOTE: Consider building a new dict and adding the
            # current year to that (if not already in the dict),
            # so that *_history always contains the current year
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year not in history_dict:
                history_dict = dict(history_dict)  # copy dict
                history_dict[obj.this_year] = fget(obj)  # add this year
            return history_dict

        history.__name__ = self.history_prop_name

        # Cast history_function to a property with sane docstring.
        self.history_property = property(
            fget=history,
            doc='Record of ' + self.__name__ + ' over all past years.'
        )


class recorded_property_cached(recorded_property):
    """ A recorded property that is cached by Ledger classes. """
    # This is a decorator, which mimics the naming convention followed by
    # `property` (i.e. lowercase)
    # pylint: disable=invalid-name

    # NOTE: Due to how decorators' pie-notation works, this is much
    # simpler than extending `recorded_property` to take a `cached`
    # argument (since `@recorded_property` (with no args) calls only
    # __init__ and `@recorded_property(cached=True)` calls __init__
    # with the keyword arg `cached` and then `__call__` with the
    # decorated method -- which makes `recorded_property` a much more
    # complicated subclass of `property`.)
    def __init__(self, fget=None, doc=None):
        """ Overrides the property getter to cache on first call. """

        # Wrap the getter in a method that will cache the property the
        # first time it's called each year.
        def getter(obj):
            """ Gets the property and caches it. """
            history_dict = getattr(obj, self.history_dict_name)
            val = fget(obj)
            history_dict[obj.this_year] = val
            return val

        # Property needs the original name and docstring:
        getter.__name__ = fget.__name__
        getter.__doc__ = fget.__doc__

        super().__init__(fget=getter, doc=doc)

        # Override history property with different method that adds the
        # current year's value to the cache if it isn't already there:
        def history(obj):
            """ Returns \\*_history dict (and caches this year's value). """
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year not in history_dict:
                history_dict[obj.this_year] = fget(obj)
            return history_dict

        history.__name__ = self.history_prop_name

        # This property was set by super().__init__
        self.history_property = property(
            fget=history,
            doc=self.history_property.__doc__
        )

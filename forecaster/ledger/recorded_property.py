""" Module providing property-like decorators for `Ledger` subclasses. """

from typing import Callable, Optional, Any, Dict

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
    # This is a decorator that mimics the naming convention followed by
    # `property` (i.e. lowercase)
    # pylint: disable=invalid-name

    def __init__(
            self,
            fget: Optional[Callable[[Any], Any]] = None,
            fset: Optional[Callable[[Any, Any], None]] = None,
            fdel: Optional[Callable[[Any], None]] = None,
            doc: Optional[str] = None) -> None:
        """ Init recorded_property.

        This wraps the getter received via the `@recorded_property`
        decoration into a method that returns a value from a dict of
        recorded values if such a value is present for the key
        `self.this_year`. If not, it calls the getter. No setter may be
        provided; this decorator automatically generates one based on
        this dict of recorded values.
        """
        # `property` is weird in that its init seems to be called
        # multiple times, one for each definition of `fget`, `fset`,
        # and `fdel`. Only one of those methods will have the
        # user-defined name (the others default to `getter`, `setter`,
        # and `deleter`, respectively), and none are bound at decoration
        # time! Try to determine which method has the correct name:
        if fget is not None and fget.__name__ != "getter":
            self.__name__ = fget.__name__
        elif fset is not None and fset.__name__ != "setter":
            self.__name__ = fset.__name__
        elif fdel is not None and fdel.__name__ != "deleter":
            self.__name__ = fdel.__name__
        # If no name is provided, use whatever the default name is.

        # We will name the corresponding history objects based on this
        # object's name:
        self.history_prop_name = self.__name__ + '_history'
        self.history_dict_name = '_' + self.history_prop_name

        # Getter returns stored value if available, otherwise generates
        # a new value (and does not cache it - we only automatically
        # store a value when next_year() is called)
        def getter(obj: Any) -> Any:
            """ Returns cached value in \\*_history dict if available. """
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year in history_dict:
                return history_dict[obj.this_year]
            else:
                return fget(obj)  # type: ignore[misc]

        def setter(obj: Any, val: Any) -> None:
            """ Adds value to cache, without overwriting user input. """
            # Don't overwrite a value provided via an inputs dict:
            if (
                    self.__name__ in obj.inputs and
                    obj.this_year in obj.inputs[self.__name__]):
                return
            # Otherwise, there are two possibilities. Both involve
            # checking the history dict, so get that now:
            history_dict = getattr(obj, self.history_dict_name)
            # Option one: No custom setter provided.
            if fset is None:
                # Cache the value in the history dict
                history_dict[obj.this_year] = val
            # Option two: A custom setter was provided
            else:
                # Remove any cached value and call the custom setter:
                if obj.this_year in history_dict:
                    del history_dict[obj.this_year]
                fset(obj, val)
                # NOTE: We don't update the cache here; we leave it to
                # the custom setter to ensure that subsequent calls to
                # this property's `fget` will return an appropriately
                # parsed form of `val`.
                # (We *could* invoke `fget` here and cache its result,
                # but this could lead to side-effects)

        def deleter(obj: Any) -> None:
            """ Removes a cached value, without removing user input. """
            # Don't delete a value provided via an inputs dict:
            if (
                    self.__name__ in obj.inputs and
                    obj.this_year in obj.inputs[self.__name__]):
                return
            # Otherwise, delete the entry from `history_dict` and call
            # `fdel` (if provided):
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year in history_dict:
                del history_dict[obj.this_year]
            if fdel is not None:
                fdel(obj)

        super().__init__(fget=getter, fset=setter, fdel=deleter, doc=doc)

        def history(obj: Any) -> Dict[int, Any]:
            """ Returns history dict for the property. """
            # For non-cached properties, the history dict might
            # not include a property for the current year.
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year not in history_dict:
                # Build a new dict (so as to avoid mutation of the input
                # dict) and add the current year to the new dict
                # (if not already in the dict), so that *_history always
                # contains the current year:
                history_dict = dict(history_dict)
                history_dict[obj.this_year] = fget(obj) # type: ignore[misc]
            return history_dict

        history.__name__ = self.history_prop_name

        # Cast `history` to a property with sane docstring.
        self.history_property = property(
            fget=history,
            doc='Record of ' + self.__name__ + ' over all past years.'
        )


class recorded_property_cached(recorded_property):
    """ A recorded property that is cached by Ledger classes. """
    # This is a decorator that mimics the naming convention followed by
    # `property` (i.e. lowercase)
    # pylint: disable=invalid-name

    # NOTE: Due to how decorators' pie-notation works, adding this
    # subclass is much simpler than extending `recorded_property` to
    # take a `cached` argument.
    # `@recorded_property` (with no args) calls only __init__, whereas
    # `@recorded_property(cached=True)` calls __init__ with the keyword
    # arg `cached` and then `__call__` with the decorated method --
    # which makes `recorded_property` a much more complicated subclass
    # of `property`!
    def __init__(
            self,
            fget: Optional[Callable[[Any], Any]] = None,
            fset: Optional[Callable[[Any, Any], None]] = None,
            fdel: Optional[Callable[[Any], None]] = None,
            doc: Optional[str] = None) -> None:
        """ Overrides the property getter to cache on first call. """

        # Wrap the getter in a method that will cache the property the
        # first time it's called each year.
        def getter(obj: Any) -> Any:
            """ Gets the property and caches it. """
            history_dict = getattr(obj, self.history_dict_name)
            val = fget(obj)  # type: ignore[misc]
            history_dict[obj.this_year] = val
            return val

        # The wrapping getter function should mimic the name and
        # docstring of the `fget` argument:
        if fget is not None:
            getter.__name__ = fget.__name__
            getter.__doc__ = fget.__doc__

        super().__init__(fget=getter, fset=fset, fdel=fdel, doc=doc)

        # Override history property with different method that adds the
        # current year's value to the cache if it isn't already there:
        def history(obj: Any) -> Dict[int, Any]:
            """ Returns \\*_history dict (and caches this year's value). """
            history_dict = getattr(obj, self.history_dict_name)
            if obj.this_year not in history_dict:
                history_dict[obj.this_year] = fget(obj)  # type: ignore[misc]
            return history_dict

        history.__name__ = self.history_prop_name

        # This property was set by super().__init__
        self.history_property = property(
            fget=history,
            doc=self.history_property.__doc__
        )

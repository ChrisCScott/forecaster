""" Defines basic recordkeeping classes, like `Person` and `Account`. """

import inspect
from decimal import Decimal
from moneyed import Money as PyMoney


class Money(PyMoney):
    """ Extends py-moneyed to support Decimal-like functions. """

    # We've only extending Money's magic methods for convenience, not
    # adding new public methods.
    # pylint: disable=too-few-public-methods

    default_currency = 'CAD'

    def __init__(self, amount=Decimal('0.0'), currency=None):
        """ Initializes with application-level default currency.

        Also allows for initializing from another Money object.
        """
        if isinstance(amount, Money):
            super().__init__(amount.amount, amount.currency)
        elif currency is None:
            super().__init__(amount, self.default_currency)
        else:
            super().__init__(amount, currency)

    def __round__(self, ndigits=None):
        """ Rounds to ndigits """
        return Money(round(self.amount, ndigits), self.currency)

    def __hash__(self):
        """ Allows for use in sets and as dict keys. """
        # Equality of Money objects is based on amount and currency.
        return hash(self.amount) + hash(self.currency)

    def __eq__(self, other):
        """ Extends == operator to allow comparison with Decimal.

        This allows for comparison to 0 (or other Decimal-convertible
        values), but not with other Money objects in different
        currencies.
        """
        # NOTE: If the other object is also a Money object, this
        # won't fall back to Decimal, because Decimal doesn't know how
        # to compare itself to Money. This is good, because otherwise
        # we'd be comparing face values of different currencies,
        # yielding incorrect behaviour like JPY1 == USD1.
        return super().__eq__(other) or self.amount == other

    def __lt__(self, other):
        """ Extends < operator to allow comparison with 0 """
        if other == 0:
            return self.amount < 0
        return super().__lt__(other)

    def __gt__(self, other):
        """ Extends > operator to allow comparison with 0 """
        if other == 0:
            return self.amount > 0
        return super().__gt__(other)


class recorded_property(property):
    """ A decorator for properties that record their annual amounts.

    Methods decorated with this decorator (a) are decorated with the
    @property decorator, and (b) sets a recorded_property flag attribute
    on the decorated property.

    `recorded_property`-decorated properties are processed by the Ledger
    metaclass to automatically generate have a <name>_history property,
    and a _<name> dict attribute to the class.

    Example:
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

        This wraps the getter received via the @recorded_property
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
            """ Returns cached value in *_history dict if available. """
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

        super().__init__(fget=getter, fset=setter, fdel=None, doc=doc)

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
            """ Returns *_history dict (and caches this year's value). """
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


class LedgerType(type):
    """ A metaclass for Ledger classes.

    This metaclass inspects the class for any
    @recorded_property-decorated methods and generates a corresponding
    *_history method and _* dict attribute.
    """
    def __init__(cls, *args, **kwargs):
        # First, build the class normally.
        super().__init__(*args, **kwargs)

        # Prepare to store all recorded properties for the class.
        cls._recorded_properties = set()
        cls._recorded_properties_cached = set()

        # Then identify all recorded_property attributes:
        for _, prop in inspect.getmembers(
            cls, lambda x: hasattr(x, 'history_property')
        ):
            # Store the identified recorded_property:
            # (This will help Ledger build object-specific dicts for
            # storing the values of each recorded property. We don't
            # want to do this at the class level because dicts are
            # mutable and we don't want to share the dict mutations
            # between objects.)
            cls._recorded_properties.add(prop)
            if isinstance(prop, recorded_property_cached):
                cls._recorded_properties_cached.add(prop)

            # Add the new attribute to the class.
            setattr(cls, prop.history_prop_name, prop.history_property)


class Ledger(object, metaclass=LedgerType):
    """ An object with a next_year() method that tracks the curent year.

    This object provides the basic infrastructure not only for advancing
    through a sequence of years but also for managing any
    `recorded_property`-decorated properties.

    Attributes:
        initial_year (int): The initial year for the object.
        this_year (int): The current year for the object. Incremented
            with each call to next_year()
    """

    # This class is intended for subclassing. It implements only magic
    # methods and a `next_year` method that manage recorded_property
    # members. That's all that's necessarly for this class, and it is
    # clearly behaviour that requires a class (not just a container).
    # pylint: disable=too-few-public-methods

    def __init__(self, initial_year, inputs=None):
        """ Inits IncrementableByYear.

        Behaviour when a `year` in `inputs` is equal to `initial_year`
        is undefined. Initialization is not guaranteed to respect such a
        value; if you want to set an initial-year value, it's better to
        pass it as an appropriate argument at `__init__` time.

        Args:
            initial_year (int): The initial year for the object.
            inputs (dict[str, dict[int, *]]): `{property: {year: val}}`
                pairs. Every `val` is treated as a manual entry that
                overrides any programmatic value for that year generated
                by `next_year`.
        """
        self.initial_year = int(initial_year)
        self.this_year = self.initial_year
        self.inputs = inputs if inputs is not None else {}

        # Build a history dict for each recorded_property
        # pylint: disable=no-member
        # Pylint gets confused by attributes added by metaclass.
        for prop in self._recorded_properties:
            # Use input values if available for this property:
            if prop.__name__ in self.inputs:
                setattr(self, prop.history_dict_name,
                        dict(self.inputs[prop.__name__]))
            # Otherwise, use an empty dict and leave it to __init__ and
            # next_year to fill it programmatically.
            else:
                setattr(self, prop.history_dict_name, {})

    def next_year(self):
        """ Advances to the next year. """
        # Record all recorded properties in the moment before advancing
        # to the next year:
        # pylint: disable=no-member
        # Pylint gets confused by attributes added by metaclass.
        for prop in self._recorded_properties:
            history_dict = getattr(self, prop.history_dict_name)
            # Only add a value to the history dict if one has not
            # already been added for this year:
            if self.this_year not in history_dict:
                # NOTE: We could alternatively do this via setattr
                # (which would call the setter function defined by the
                # recorded_property decorator - perhaps preferable?)
                history_dict[self.this_year] = getattr(
                    self, prop.__name__)
        # Advance to the next year after recording properties:
        self.this_year += 1


class TaxSource(Ledger):
    """ An object that can be considered when calculating taxes.

    Provides standard tax-related properties, listed below.

    Actual tax treatment will vary by subclass. Rather than override
    these properties directly, subclasses should override the methods
    _taxable_income, _tax_withheld, _tax_credit, and _tax_deduction
    (note the leading underscore).

    Attributes:
        taxable_income (Money): Taxable income arising from the
            object for the current year.
        tax_withheld (Money): Tax withheld from the object for the
            current year.
        tax_credit (Money): Taxable credits arising from the
            object for the current year.
        tax_deduction (Money): Taxable deductions arising from the
            object for the current year.
        taxable_income_history (Money): Taxable income arising from the
            object for each year thus far.
        tax_withheld_history (Money): Tax withheld from the object for
            each year thus far.
        tax_credit_history (Money): Taxable credits arising from the
            object for each year thus far.
        tax_deduction_history (Money): Taxable deductions arising from
            the object for each year thus far.
    """

    @recorded_property
    def taxable_income(self):
        """ Taxable income for the given year.

        Subclasses should override this method rather than the
        taxable_income and _taxable_income_history properties.
        """
        return Money(0)

    @recorded_property
    def tax_withheld(self):
        """ Tax withheld for the given year.

        Subclasses should override this method rather than the
        tax_withheld and _tax_withheld_history properties.
        """
        return Money(0)

    @recorded_property
    def tax_credit(self):
        """ Tax credit for the given year.

        Subclasses should override this method rather than the
        tax_credit and _tax_credit_history properties.
        """
        return Money(0)

    @recorded_property
    def tax_deduction(self):
        """ Tax deduction for the given year.

        Subclasses should override this method rather than the
        tax_deduction and _tax_deduction_history properties.
        """
        return Money(0)

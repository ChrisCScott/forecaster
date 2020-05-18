""" Module providing the Ledger base type and associated classes. """

import inspect
from typing import Type, Dict, Any, Optional, Callable
from forecaster.money import MoneyType as Money, Real
from forecaster.ledger.recorded_property import (
    recorded_property, recorded_property_cached
)

class LedgerType(type):
    """ A metaclass for Ledger classes.

    This metaclass inspects the class for any
    @recorded_property-decorated methods and generates a corresponding
    *_history method and _* dict attribute.
    """
    def __init__(cls: Type, *args: Any, **kwargs: Any) -> None:
        # First, build the class normally.
        super().__init__(*args, **kwargs)

        # Prepare to store all recorded properties for the class.
        cls._recorded_properties = set()
        cls._recorded_properties_cached = set()

        # Then identify all recorded_property attributes:
        for _, prop in inspect.getmembers(
                cls, lambda x: hasattr(x, 'history_property')):
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

    def __init__(
            self, initial_year: int,
            inputs: Optional[Dict[str, Dict[int, Any]]] = None) -> None:
        """ Inits IncrementableByYear.

        Behaviour when a `year` in `inputs` is equal to `initial_year`
        is undefined. Initialization is not guaranteed to respect such a
        value; if you want to set an initial-year value, it's better to
        pass it as an appropriate argument at `__init__` time.

        Args:
            initial_year (int): The initial year for the object.
            inputs (dict[str, dict[int, Any]]):
                `{property: {year: val}}` pairs. Every `val` is treated
                as a manual entry that overrides any programmatic value
                for that year generated by `next_year`. Optional.
        """
        self.initial_year = int(initial_year)
        self.this_year = self.initial_year
        self.inputs = inputs if inputs is not None else {}
        # Declare class properties added by LedgerType to help mypy and
        # pylint (they get confused by attributes added by metaclass)
        self._recorded_properties: set
        self._recorded_properties_cached: set

        # Build a history dict for each recorded_property
        for prop in self._recorded_properties:
            # Use input values if available for this property:
            if prop.__name__ in self.inputs:
                setattr(self, prop.history_dict_name,
                        dict(self.inputs[prop.__name__]))
            # Otherwise, use an empty dict and leave it to __init__ and
            # next_year to fill it programmatically.
            else:
                setattr(self, prop.history_dict_name, {})

    def next_year(self) -> None:
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

    def clear_cache(self) -> None:
        """ Clears all recorded_property_cached values for this year. """
        # pylint: disable=no-member
        # Pylint gets confused by attributes added by metaclass.
        for prop in self._recorded_properties_cached:
            prop.fdel(obj=self)

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
        taxable_income_history (Dict[int,Money]): Taxable income arising
            from the object for each year thus far.
        tax_withheld_history (Dict[int,Money]): Tax withheld from the
            object for each year thus far.
        tax_credit_history (Dict[int,Money]): Taxable credits arising
            from the object for each year thus far.
        tax_deduction_history (Dict[int,Money]): Taxable deductions
            arising from the object for each year thus far.
        money_factory (Callable[[Real], Money]): A callable
            object which takes a numeric value and returns a `Money`
            value. Optional; defaults to `float`.
    """

    def __init__(
            self, initial_year: int,
            inputs: Optional[Dict[str, Dict[int, Any]]] = None,
            money_factory: Callable[[Real], Money] = float) -> None:
        """ Initializes TaxSource. """
        super().__init__(initial_year, inputs)
        self.money_factory = money_factory

    @recorded_property
    def taxable_income(self) -> Money:
        """ Taxable income for the given year.

        Subclasses should override this method rather than the
        _taxable_income and _taxable_income_history properties.
        """
        return self.money_factory(0)

    @recorded_property
    def tax_withheld(self) -> Money:
        """ Tax withheld for the given year.

        Subclasses should override this method rather than the
        _tax_withheld and _tax_withheld_history properties.
        """
        return self.money_factory(0)

    @recorded_property
    def tax_credit(self) -> Money:
        """ Tax credit for the given year.

        Subclasses should override this method rather than the
        _tax_credit and _tax_credit_history properties.
        """
        return self.money_factory(0)

    @recorded_property
    def tax_deduction(self) -> Money:
        """ Tax deduction for the given year.

        Subclasses should override this method rather than the
        _tax_deduction and _tax_deduction_history properties.
        """
        return self.money_factory(0)

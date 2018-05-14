""" Provides classes for determining asset allocation. """

from collections import namedtuple
from decimal import Decimal
from forecaster.strategy.base import Strategy, strategy_method


AssetAllocation = namedtuple('AssetAllocation', 'stocks bonds other')


class RateFunction(object):
    """ A callable object with accessible state attributes. """

    # We do provide public methods, but they're overrides of magic
    # methods (init and call). Anyways, the purpose of this class is
    # to expose its state (which a method/function/lambda does not do).
    # pylint: disable=too-few-public-methods

    def __init__(self, scenario, person, allocation_strategy):
        """ Inits the RateFunction object. """
        self.scenario = scenario
        self.person = person
        self.allocation_strategy = allocation_strategy

    def __call__(self, year):
        """ Rate of return for `year` based on asset allocation.

        Args:
            year (int): The year for which the rate of return will be
                determined.

        Returns:
            Decimal: The rate of return. For example, `Decimal('0.05')`
            means a 5% return.
        """
        allocation = self.allocation_strategy(
            age=self.person.age(year),
            retirement_age=self.person.retirement_age
        )
        # Extract stocks/bonds/other returns:
        if 'stocks' in allocation:
            stocks = allocation['stocks']
        else:
            stocks = Decimal(0)
        if 'bonds' in allocation:
            bonds = allocation['bonds']
        else:
            bonds = Decimal(0)
        if 'other' in allocation:
            other = allocation['other']
        else:
            other = Decimal(0)

        # Weight the returns of the various asset classes by each
        # class's allocation:
        return (
            (
                stocks * self.scenario.stock_return[year]
                + bonds * self.scenario.bond_return[year]
                + other * self.scenario.other_return[year]
            ) / (stocks + bonds + other)
        )


class AllocationStrategy(Strategy):
    """ Generates an asset allocation for a point in time. Callable.

    Attributes:
        strategy (str, func): Either a string corresponding to a
            particular strategy or an instance of the strategy itself.
            See `strategies` for acceptable keys.
        strategies (dict): {str, func} pairs where each key identifies
            a strategy (in human-readable text) and each value is a
            function with the same arguments and return value as
            transactions(). See its documentation for more info.

            Acceptable keys include:

            * "n-age"
            * "Transition to constant"

        min_equity (Decimal): The minimum percentage of a portfolio that
            may be invested in equities. (All non-equity investments
            are included in `fixed_income`)
        max_equity (Decimal): The maximum percentage of a portfolio that
            may be invested in equities.
        target (Decimal): A target value used by strategies to affect
            their behaviour.

            For example, for the `n-age` strategy, this is the value `n`
            (e.g. `target=100` -> `100-age`).

            For the `Transition to constant` strategy, this is the
            percentage of equities to transition to (e.g. for
            `Transition to 50-50`, use `Decimal('0.5')`)
        standard_retirement_age (int): The typical retirement age used
            in retirement planning.

            This is used if `adjust_for_retirement_plan` is False,
            otherwise the actual (or estimated) retirement age for the
            person is used.
        risk_transition_period (int): The period of time over which the
            `Transition to constant` strategy transitions.

            For example, if set to 20, the strategy will transition
            from `max_equity` to `transition_strategy_target` over 20
            years, ending on the retirement date.
        adjust_for_retirement_plan (bool): If True, the allocation will
            be adjusted to increase risk for later retirement or
            decrease risk for later retirement. If False, the standard
            retirement age will be used.

    Args:
        age (int): The current age of the plannee.
        retirement_age (int): The (estimated) retirement age of the
            plannee.

    Returns:
        AssetAllocation: A `namedtuple` where each member is the
        percentage of a portfolio that is made up of the named asset
        class.

        Allocations of the members sum to 1 (e.g. `Decimal(0.03` means
        3%).
    """
    # pylint: disable=too-many-arguments
    def __init__(
        self, strategy, target, min_equity=0, max_equity=1,
        standard_retirement_age=65, risk_transition_period=20,
        adjust_for_retirement_plan=True
    ):
        """ Constructor for AllocationStrategy. """
        super().__init__(strategy)

        self.min_equity = Decimal(min_equity)
        self.max_equity = Decimal(max_equity)
        self.standard_retirement_age = int(standard_retirement_age)
        self.target = Decimal(target)
        self.risk_transition_period = int(risk_transition_period)
        self.adjust_for_retirement_plan = bool(adjust_for_retirement_plan)

        # All of the above are type-converted; no need to check types!

        if self.max_equity < self.min_equity:
            raise ValueError('AllocationStrategy: min_equity must not be ' +
                             'greater than max_equity.')

    @strategy_method('n-age')
    def strategy_n_minus_age(
        self, age, retirement_age=None, *args, **kwargs
    ):
        """ Used for 100-age, 110-age, 125-age, etc. strategies. """
        # *args and **kwargs are included for consistency between
        # methods, even though we don't use them.
        # pylint: disable=unused-argument

        # If we're adjusting for early/late retirement,
        # pretend we're a few years younger if we're retiring later
        # (or that we're older if retiring earlier)
        if self.adjust_for_retirement_plan:
            self._param_check(retirement_age, 'retirement age')
            age += self.standard_retirement_age - retirement_age
        else:
            retirement_age = self.standard_retirement_age
        # The formula for `n-age` is just that (recall that
        # n=constant_strategy_target). Insert the adjustment factor too.
        target = Decimal(self.target - age) / 100
        # Ensure that we don't move past our min/max equities
        target = min(max(target, self.min_equity), self.max_equity)
        # Bonds is simply whatever isn't in equities
        return {'stocks': target, 'bonds': 1 - target}

    @strategy_method('Transition to constant')
    def strategy_transition_to_const(
        self, age, retirement_age=None, *args, **kwargs
    ):
        """ Used for `Transition to 50-50`, `Transition to 70-30`, etc. """
        # *args and **kwargs are included for consistency between
        # methods, even though we don't use them.
        # pylint: disable=unused-argument

        # Assume we're retiring at the standard retirement age unless
        # adjust_for_retirement_plan is True
        if self.adjust_for_retirement_plan:
            self._param_check(retirement_age, 'retirement age')
        else:
            retirement_age = self.standard_retirement_age

        # If retirement is outside our risk transition window (e.g. if
        # it's more than 20 years away), maximize stock holdings.
        if age <= retirement_age - self.risk_transition_period:
            return {'stocks': self.max_equity, 'bonds': 1 - self.max_equity}
        # If we've hit retirement, keep equity allocation constant at
        # our target
        elif age >= retirement_age:
            min_equity = max(self.min_equity, self.target)
            return {'stocks': min_equity, 'bonds': 1 - min_equity}
        # Otherwise, smoothly move from max_equity to target over
        # the risk_transition_period
        target = self.target + \
            (self.max_equity - self.target) * \
            (retirement_age - age) / self.risk_transition_period
        return {'stocks': target, 'bonds': 1 - target}

    def rate_function(self, person, scenario):
        """ A rate function usable by Person or Account objects.

        Args:
            person (Person): A person. The method builds a portfolio for
                the person based on this object's allocation strategy
                (in particular, based on the person's age and/or
                projected retirement date).
            scenario (Scenario): A `Scenario` providing information on
                returns on investment for stocks, bonds, etc.

        Returns:
            An object callable with the form
            `rate_function(year) -> Decimal` that provides a rate of
            return for a given year based on the person's age and the
            investment returns for various asset classes provided by
            `scenario`.
        """
        # We need to return an object rather than a function or lambda
        # because we need Forecaster to be able to swap out any of those
        # attributes when running a forecast.
        return RateFunction(scenario, person, self)

    def __call__(self, age, retirement_age=None, *args, **kwargs):
        """ Returns a dict of {account, Money} pairs. """
        # TODO: Move min_equity and max_equity logic here to simplify
        # the logic of each strategy.
        # In the meantime, suppress Pylint's complaints about how this
        # method is useless:
        # pylint: disable=useless-super-delegation
        return super().__call__(age, retirement_age, *args, **kwargs)

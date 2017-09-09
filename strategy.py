''' This module provides the `Strategy` class and subclasses, which
define contribution and withdrawal strategies and associated flags. '''


class Strategy:
    ''' This is a wrapper class for various *Strategy classes.

    Namely, this is a wrapper for `ContributionStrategy`,
    `WithdrawalStrategy`, and `InvestmentStrategy`.
    This class contains some information relevant to each, such as the
    user's birthdates and choice of retirement age. '''

    __retirement_age = None

    class ContributionStrategy:
        ''' Defines a contribution strategy.

        Provides methods to determine the total contribution
        (gross and net of contribution reductions) for a given year. '''
        @staticmethod
        def get_contribution_rate_strategies():
            ''' Returns functions defining contribution strategies.

            Returns:
                A dict of contribution rate strategy descriptions (keys)
                and functions defining each corresponding contribution
                strategy (values).

                The functions are of the form `func(Money:value,
                Year:last_year, Year:this_year) -> Money`.
                `this_year` need not be fully initialized, but must
                provide at least gross and net income. '''
            return 1  # TODO: complete function

    def __init__(self, retirement_age=None, contribution_strategy=None,
                 withdrawal_strategy=None):
        ''' Constructor for `Strategy`. '''
        self.__retirement_age = retirement_age
        if contribution_strategy is None:
            self.__contribution_strategy = self.ContributionStrategy()
        else:
            self.__contribution_strategy = contribution_strategy

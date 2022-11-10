import abc


class HighLevelStrategy(abc.ABC):
    '''
    A strategy for the whole game, doesn't change
    '''

    def __init__(self, bot):
        self.bot = bot  # bad practice, but we're in too deep to fix stuff now

    def decide(self):
        pass

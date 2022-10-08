from gupb.controller.AlephAlephZero.strategy import Strategy
from gupb.model import characters


class ScanningStrategy(Strategy):
    def decide_and_proceed(self, knowledge, **kwargs):
        if self.turns_to_do==0:
            return None, self.proceeding_strategy
        else:
            self.turns_to_do-=1
            return characters.Action.TURN_LEFT, self

    def __init__(self, proceeding_strategy):
        self.proceeding_strategy = proceeding_strategy
        self.turns_to_do=3

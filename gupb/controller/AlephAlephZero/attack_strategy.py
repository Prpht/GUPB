from gupb.controller.AlephAlephZero.scouting_strategy import ScoutingStrategy
from gupb.controller.AlephAlephZero.strategy import Strategy
from gupb.model import characters


class AttackStrategy(Strategy):

    def decide_and_proceed(self, knowledge, **kwargs):
        return characters.Action.ATTACK, ScoutingStrategy()
from gupb.controller.aleph_aleph_zero.scouting_strategy import ScoutingStrategy
from gupb.controller.aleph_aleph_zero.strategy import Strategy
from gupb.model import characters


class AttackStrategy(Strategy):

    def decide_and_proceed(self, knowledge, **kwargs):
        return characters.Action.ATTACK, ScoutingStrategy()
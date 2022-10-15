from gupb.controller.aleph_aleph_zero.scouting_strategy import ScoutingStrategy
from gupb.controller.aleph_aleph_zero.strategy import Strategy
from gupb.model import characters


class AttackStrategy(Strategy):

    def decide_and_proceed(self, knowledge, **kwargs):
        return characters.Action.ATTACK, ScoutingStrategy()

class RunStrategy(Strategy):
    def __init__(self, prev_strategy, **kwargs):
        super().__init__(**kwargs)
        self.prev_strategy = prev_strategy

    def decide_and_proceed(self, knowledge, **kwargs):
        facing = knowledge.facing.value
        if knowledge.visible_tiles[knowledge.position + facing].type == 'land' and knowledge.visible_tiles[knowledge.position + facing].character is None:
            return characters.Action.STEP_FORWARD, self.prev_strategy
        else:
            return None, self.prev_strategy
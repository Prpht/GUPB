from typing import NamedTuple
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.strategies.explore_strategy import ExploreStrategy
from gupb.controller.lord_icon.strategies.kill_strategy import KillStrategy

from gupb.model.characters import Action


class StrategyController(NamedTuple):

    @staticmethod
    def decide(knowledge: Knowledge) -> Action:
        if (knowledge.character.weapon == 'knife' and knowledge.character.health > 4) or len(knowledge.enemies) == 0:
            return ExploreStrategy.get_action(knowledge)
        return KillStrategy.get_action(knowledge)

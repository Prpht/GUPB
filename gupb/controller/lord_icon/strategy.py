from typing import NamedTuple
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.strategies.end_game_strategy import EndGameStrategy
from gupb.controller.lord_icon.strategies.explore_strategy import ExploreStrategy
from gupb.controller.lord_icon.strategies.camp_strategy import CampStrategy

from gupb.model.characters import Action


class StrategyController(NamedTuple):

    @staticmethod
    def decide(knowledge: Knowledge) -> Action:
        # Attack if you can
        for enemy in knowledge.enemies:
            if knowledge.character.can_attack(knowledge.map, enemy.position):
                return Action.ATTACK

        if knowledge.seen_mist and knowledge.menhir is not None:
            return EndGameStrategy.get_action(knowledge)

        if knowledge.character.weapon == 'knife' and knowledge.menhir is None:
            return ExploreStrategy.get_action(knowledge)

        return CampStrategy.get_action(knowledge)

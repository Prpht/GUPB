from typing import NamedTuple
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.strategies.explore_strategy import ExploreStrategy

from gupb.model.characters import Action


class StrategyController(NamedTuple):

    @staticmethod
    def decide(knowledge: Knowledge) -> Action:
        return ExploreStrategy.get_action(knowledge)

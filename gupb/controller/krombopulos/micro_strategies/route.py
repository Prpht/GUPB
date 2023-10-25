from gupb.model import characters
from .micro_strategy import MicroStrategy, StrategyPrecedence
from ..knowledge_sources import KnowledgeSources


class RouteMicroStrat(MicroStrategy):
    def __init__(self, knowledge_sources: KnowledgeSources, precedence: StrategyPrecedence | None = None):
        super().__init__(knowledge_sources, precedence)
        if precedence is None:
            self.precedence = StrategyPrecedence.HIGH

    def decide_and_get_next(self) -> tuple[characters.Action, bool]:
        front_tile = self.knowledge_sources.get_tile_info_in_front_of()
        if front_tile.consumable:
            return characters.Action.STEP_FORWARD, True
        elif front_tile.character:
            return characters.Action.ATTACK, True
        elif front_tile.loot:
            return characters.Action.STEP_FORWARD, True

        # todo: implement routing strategy (using dynamically-created graph)
        #  it should:
        #   - explore first (look around, maybe first try to go to the center)
        #   - if menhir is found, go there are if already there, return (act, False)
        #   - escape mist if found

        return characters.Action.TURN_LEFT, False

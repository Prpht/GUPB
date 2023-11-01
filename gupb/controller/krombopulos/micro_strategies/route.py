from gupb.model import characters
from .micro_strategy import MicroStrategy, StrategyPrecedence
from ..knowledge_sources import KnowledgeSources


class RouteMicroStrat(MicroStrategy):
    def __init__(self, knowledge_sources: KnowledgeSources, precedence: StrategyPrecedence | None = None):
        super().__init__(knowledge_sources, precedence)
        if precedence is None:
            self.precedence = StrategyPrecedence.HIGH

    def decide_and_get_next(self) -> tuple[characters.Action, MicroStrategy]:
        front_tile = self.knowledge_sources.get_tile_info_in_front_of()
        if front_tile.consumable:
            return characters.Action.STEP_FORWARD, self
        elif front_tile.character:
            return characters.Action.ATTACK, self
        elif front_tile.loot:
            return characters.Action.STEP_FORWARD, self

        next_pos = self.knowledge_sources.find_next_move_on_path(tuple(self.knowledge_sources.players.own_player_pos),
                      tuple(self.knowledge_sources.map.menhir_pos + characters.Facing.random().value) or (11, 13))

        if self.knowledge_sources.players.own_player_pos + \
            self.knowledge_sources.players.own_player_facing.turn_left().value == next_pos:
            return characters.Action.TURN_LEFT, self
        elif self.knowledge_sources.players.own_player_pos + \
            self.knowledge_sources.players.own_player_facing.turn_right().value == next_pos:
            return characters.Action.TURN_RIGHT, self
        elif self.knowledge_sources.players.own_player_pos + \
            self.knowledge_sources.players.own_player_facing.value == next_pos:
            return characters.Action.STEP_FORWARD, self

        return characters.Action.TURN_LEFT, self

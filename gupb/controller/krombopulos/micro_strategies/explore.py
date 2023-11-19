import random

from gupb.model import characters
from .micro_strategy import MicroStrategy, StrategyPrecedence
from ..knowledge_sources import KnowledgeSources


class ExploreMicroStrat(MicroStrategy):
    def __init__(self, knowledge_sources: KnowledgeSources, precedence: StrategyPrecedence | None = None):
        super().__init__(knowledge_sources, precedence)
        self.queued_action: characters.Action | None = None
        if precedence is None:
            self.precedence = StrategyPrecedence.LOW

    def decide_and_get_next(self) -> tuple[characters.Action, bool]:
        # move if champion has not moved in 5 epochs
        if action := self.avoid_afk():
            return action, False
        front_tile = self.knowledge_sources.get_tile_info_in_front_of()
        actions_to_choose_from = []
        probs = []
        if front_tile.consumable:
            return characters.Action.STEP_FORWARD, True
        elif front_tile.character:
            return characters.Action.ATTACK, True
        elif front_tile.loot:
            return characters.Action.STEP_FORWARD, True

        left_tile = self.knowledge_sources.get_tile_in_direction(
            self.knowledge_sources.players.own_player_facing.turn_left())

        right_tile = self.knowledge_sources.get_tile_in_direction(
            self.knowledge_sources.players.own_player_facing.turn_right())

        # queued action
        if self.queued_action:
            temp = self.queued_action
            self.queued_action = None
            return temp, True

        # stuck in a hole
        if left_tile and left_tile.type in ('sea', 'wall') and front_tile.type in ('sea', 'wall'):
            self.queued_action = characters.Action.TURN_RIGHT
            return characters.Action.TURN_RIGHT, True
        elif right_tile and right_tile.type in ('sea', 'wall') and front_tile.type in ('sea', 'wall'):
            self.queued_action = characters.Action.TURN_LEFT
            return characters.Action.TURN_LEFT, True

        if front_tile.type in ('land', 'menhir'):
            actions_to_choose_from.append(characters.Action.STEP_FORWARD)
            probs.append(0.3)

        if left_tile and left_tile.type in ('land', 'menhir') or not left_tile:
            actions_to_choose_from.append(characters.Action.TURN_LEFT)
            probs.append(0.1)

        if right_tile and right_tile.type in ('land', 'menhir') or not right_tile:
            actions_to_choose_from.append(characters.Action.TURN_RIGHT)
            probs.append(0.1)

        actions_to_choose_from.append(characters.Action.ATTACK)
        probs.append(0.05)

        return random.choices(actions_to_choose_from, weights=probs)[0], True

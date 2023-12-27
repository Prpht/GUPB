from random import choice

from gupb.model import characters
from .micro_strategy import MicroStrategy, StrategyPrecedence
from ..knowledge_sources import KnowledgeSources


class RouteMicroStrat(MicroStrategy):
    def __init__(self, knowledge_sources: KnowledgeSources, precedence: StrategyPrecedence | None = None):
        super().__init__(knowledge_sources, precedence)
        if precedence is None:
            self.precedence = StrategyPrecedence.MEDIUM

    def decide_and_get_next(self) -> tuple[characters.Action, bool]:
        # move if champion has not moved in 5 epochs
        if action := self.avoid_afk():
            return action, False

        # decision overrides in the base class
        if action := self.decide_override():
            return action, True

        # find next move in path to menhir
        try:
            next_pos = self.knowledge_sources.find_next_move_on_path(
                start=self.knowledge_sources.players.own_player_pos,
                end=self.knowledge_sources.map.menhir_pos + characters.Facing.random().value
            )
        # if we do not know where the menhir is, move to the map center
        except TypeError:
            next_pos = self.knowledge_sources.find_next_move_on_path(self.knowledge_sources.players.own_player_pos,
                                                                     self.knowledge_sources.map.map_center) 

        chosen_action = characters.Action.DO_NOTHING

        if (self.knowledge_sources.players.own_player_pos +
                self.knowledge_sources.players.own_player_facing.turn_left().value == next_pos):
            chosen_action = characters.Action.STEP_LEFT
        elif (self.knowledge_sources.players.own_player_pos +
              self.knowledge_sources.players.own_player_facing.turn_right().value == next_pos):
            chosen_action = characters.Action.STEP_RIGHT
        elif (self.knowledge_sources.players.own_player_pos +
              self.knowledge_sources.players.own_player_facing.value == next_pos):
            chosen_action = characters.Action.STEP_FORWARD
        elif (self.knowledge_sources.players.own_player_pos -
              self.knowledge_sources.players.own_player_facing.value == next_pos):
            chosen_action = choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])

        if self.knowledge_sources.is_action_possible(chosen_action):
            return chosen_action, True
        else:
            return characters.Action.DO_NOTHING, False

        # todo: implement routing strategy (using dynamically-created graph)
        #  it should:
        #   - explore first (look around, maybe first try to go to the center)
        #   - if menhir is found, go there are if already there, return (act, False)
        #   - escape mist if found

import abc
import enum
import random

from gupb.model import characters

from ..knowledge_sources import KnowledgeSources



class StrategyPrecedence(enum.IntEnum):
    LOWEST = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    HIGHEST = 5


WEAPON_PREFERENCE = {
    'knife': 1,
    'bow_unloaded': 2,
    'bow_loaded': 3,
    'sword': 4,
    'axe': 5,
    'amulet': 6
}



class MicroStrategy(abc.ABC):
    def __init__(self, knowledge_sources: KnowledgeSources, precedence: StrategyPrecedence | None=None):
        self.knowledge_sources: KnowledgeSources = knowledge_sources
        self.precedence: StrategyPrecedence = precedence


    @abc.abstractmethod
    def decide_and_get_next(self) -> tuple[characters.Action, bool]:
        """Return a tuple: (chosen_action, continue_using_this_strategy)."""
        pass


    def avoid_afk(self) -> characters.Action | None:
        history = self.knowledge_sources.players.own_player_history
        history = sorted(history.items(), reverse=True)
        if len(history) < 10:
            return None
        history = list([el[1] for el in history[:10]])
        facings = [el[0].facing for el in history]
        coords = [el[1] for el in history]
        if all([facings[0] == facing for facing in facings]) and all([coords[0] == coord for coord in coords]):
            possible_actions = [a for a in
                                [characters.Action.STEP_FORWARD, characters.Action.STEP_LEFT,
                                 characters.Action.STEP_RIGHT, characters.Action.STEP_BACKWARD]
                                if self.knowledge_sources.is_action_possible(a)]
            if possible_actions:
                return random.choice(possible_actions)
        return None


    def decide_override(self) -> characters.Action | None:
        front_tile = self.knowledge_sources.get_tile_info_in_front_of()
        left_tile = self.knowledge_sources.get_tile_in_direction(
            self.knowledge_sources.players.own_player_facing.turn_left())
        right_tile = self.knowledge_sources.get_tile_in_direction(
            self.knowledge_sources.players.own_player_facing.turn_left())

        tiles_actions = [
            (front_tile, {'step': characters.Action.STEP_FORWARD, 'turn': characters.Action.DO_NOTHING}),
            (left_tile, {'step': characters.Action.STEP_LEFT, 'turn': characters.Action.TURN_LEFT}),
            (right_tile, {'step': characters.Action.STEP_RIGHT, 'turn': characters.Action.TURN_RIGHT})
        ]

        # yoink consumables
        for tile_info, actions_dict in tiles_actions:
            if tile_info.consumable:
                return actions_dict['step']

        # yoink loot if better than already possessed
        for tile_info, actions_dict in tiles_actions:
            if tile_info.loot and WEAPON_PREFERENCE[tile_info.loot.name] > \
                                  WEAPON_PREFERENCE[self.knowledge_sources.players.own_player_weapon]:
                return actions_dict['step']


        # attack enemies
        for champion, enemy_coords in self.knowledge_sources.players.iter_visible_players_info():
            if enemy_coords in self.knowledge_sources.iter_attacking_coords():
                return characters.Action.ATTACK

        # react to enemies
        for tile_info, actions_dict in tiles_actions:
            if tile_info.character:
                if self.knowledge_sources.players.own_player_weapon in ('bow_loaded', 'bow_unloaded', 'amulet'):
                    # gtfo
                    for a in [characters.Action.STEP_LEFT, characters.Action.STEP_RIGHT,
                              characters.Action.STEP_FORWARD, characters.Action.STEP_BACKWARD]:
                        if self.knowledge_sources.is_action_possible(a):
                            return a

                if self.knowledge_sources.players.own_player_hp < tile_info.character.health:
                    if random.random() > 0.5:
                        for a in [characters.Action.STEP_LEFT, characters.Action.STEP_RIGHT,
                                  characters.Action.STEP_FORWARD, characters.Action.STEP_BACKWARD]:
                            if self.knowledge_sources.is_action_possible(a):
                                return a
                else:
                    if self.knowledge_sources.players.own_player_hp > 1.2*tile_info.character.health:
                        return actions_dict['turn']
                    elif random.random() > 0.5:
                        return actions_dict['turn']

        return None


    def __gt__(self, other) -> bool:
        assert isinstance(other, MicroStrategy)
        return self.precedence > other.precedence


    def __eq__(self, other) -> bool:
        if not isinstance(other, MicroStrategy):
            return False
        return self.precedence == other.precedence

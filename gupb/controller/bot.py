import random
from queue import SimpleQueue
from gupb.model import weapons, coordinates, tiles
from typing import Type, Dict

import pygame

from gupb.model import arenas
from gupb.model import characters

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]

WEAPON_RANGE = {
    'bow': 50,
    'sword': 3,
    'knife': 1
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotController:
    def __init__(self):
        self.action_queue: SimpleQueue[characters.Action] = SimpleQueue()
        self.current_weapon = 'knife'
        self.facing = None  # inicjalizacja przy pierwszym decide
        self.position = None  # inicjalizacja przy pierwszym decide
        self.menhir_coord: coordinates.Coords = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.__refresh_info(knowledge)

        if self.__can_attack(knowledge.visible_tiles):
            return characters.Action.ATTACK
        return random.choice(POSSIBLE_ACTIONS)

    @property
    def name(self) -> str:
        return 'BotController'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

    def __refresh_info(self, knowledge: characters.ChampionKnowledge):
        self.position = knowledge.position
        character = knowledge.visible_tiles[self.position].character
        self.facing = character.facing
        self.current_weapon = character.weapon.name

    def __can_attack(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        try:
            if self.current_weapon == 'axe':
                centre_position = self.position + self.facing.value
                left_position = centre_position + self.facing.turn_left().value
                right_position = centre_position + self.facing.turn_right().value
                cut_positions = [left_position, centre_position, right_position]
                for cut_position in cut_positions:
                    if visible_tiles[cut_position].character:
                        return True
            elif self.current_weapon == 'amulet':
                centre_position = self.position + self.facing.value
                left_position = centre_position + self.facing.turn_left().value
                right_position = centre_position + self.facing.turn_right().value
                cut_positions = [left_position, right_position]
                for cut_position in cut_positions:
                    if visible_tiles[cut_position].character:
                        return True
            elif self.current_weapon == 'bow_unloaded' or self.current_weapon == 'bow_loaded' or self.current_weapon == 'sword' or self.current_weapon == 'knife':
                reach = WEAPON_RANGE[self.current_weapon]
                tile = self.position
                for _ in range(1, reach + 1):
                    tile = tile + self.facing.value
                    if visible_tiles[tile].character:
                        return True
        except KeyError:
            # kafelek nie byl widoczny
            return False
        return False


POTENTIAL_CONTROLLERS = [
    BotController(),
]

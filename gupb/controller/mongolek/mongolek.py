import random
from typing import Any

import numpy as np

from gupb import controller
from gupb.controller.mongolek import astar
from gupb.model import arenas, weapons, coordinates, effects
from gupb.model import characters
from gupb.model.characters import Action, CHAMPION_STARTING_HP
from gupb.model.coordinates import Coords

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]

POSSIBLE_MOVES = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
]

WEAPONS = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    # 'bow_loaded': weapons.Bow,
    # 'bow_unloaded': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}

WEAPONS_VALUE = {
    'knife': 1,
    'sword': 2,
    'amulet': 3,
    'axe': 4,
    'bow': 5,
    # 'bow_loaded': 5,
    # 'bow_unloaded': 5
}


class Mongolek(controller.Controller):
    def __init__(self, first_name: str):
        self.mist_available = None
        self.move_number = 0
        self.position = None
        self.first_name: str = first_name
        self.facing = None
        self.health = None
        self.arena = None
        self.gps = None
        self.weapon = None
        self.menhir_found = False
        self.target = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Mongolek):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> Action | None | Any:
        self.move_number += 1
        self.position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        me = knowledge.visible_tiles[self.position].character
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon

        cut = WEAPONS[self.weapon.name].cut_positions(self.arena.terrain, self.position, self.facing)
        for coord, tile in visible_tiles.items():
            if tile.character and Coords(coord[0],
                                         coord[1]) in cut and self.health > 0.3 * CHAMPION_STARTING_HP:
                return Action.ATTACK
            if effects.EffectDescription(type='mist') in tile.effects:
                self.mist_available = True
                print("tile type:", tile.type)
            if tile.consumable and self.distance(self.position, coord[0], coord[1]) <= 5:
                self.target = coordinates.Coords(coord[0], coord[1])
            if tile.type == 'menhir' and (self.mist_available or self.move_number > 40):
                self.target = coordinates.Coords(coord[0], coord[1])
            elif tile.type in list(WEAPONS.keys()) and self.distance(self.position, coord[0], coord[1]) <= 5 and WEAPONS_VALUE[self.weapon.name] < WEAPONS_VALUE[tile.loot.name]:
                self.target = coordinates.Coords(coord[0], coord[1])

        if self.target:
            if self.position == self.target:
                self.target = None
                return Action.TURN_LEFT
            else:
                return self.go_to_target(knowledge, self.target)
        else:
            next_tile = self.position + self.facing.value
            if visible_tiles[next_tile].type in ['sea', 'wall']:
                return Action.TURN_RIGHT
            possible = [1, 1, 4]
            return random.choices(POSSIBLE_MOVES, possible, k=1)[0]

    @staticmethod
    def distance(coords: coordinates.Coords, x: int, y: int):
        return np.abs(coords.x - x) + np.abs(coords.y - y)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.facing = None
        self.health = None
        self.weapon = None
        self.arena = arenas.Arena.load(arena_description.name)
        self.move_number = 0
        self.gps = astar.PathFinder(arena_description)
        self.arena = arenas.Arena.load(arena_description.name)
        self.menhir_found = False
        self.target = None

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.MONGOL

    def go_to_target(self,
                     champion_knowledge: characters.ChampionKnowledge,
                     destination_coordinates: coordinates.Coords) -> characters.Action:

        current_coordinates = champion_knowledge.position
        current_facing = champion_knowledge.visible_tiles[champion_knowledge.position].character.facing

        path = self.gps.find_path(current_coordinates, destination_coordinates)

        if current_coordinates.x + current_facing.value.x == path[0].x and current_coordinates.y + current_facing.value.y == path[0].y:
            return characters.Action.STEP_FORWARD
        if current_coordinates.x + current_facing.turn_right().value.x == path[0].x and current_coordinates.y + current_facing.turn_right().value.y == path[0].y:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT

POTENTIAL_CONTROLLERS = [
    Mongolek("Mongolek"),
]

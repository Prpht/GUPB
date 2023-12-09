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
    'bow_loaded': weapons.Bow,
    'bow_unloaded': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}

WEAPONS_VALUE = {
    'knife': 1,
    'sword': 2,
    'axe': 3,
    'amulet': 4,
    'bow': 5,
    'bow_loaded': 5,
    'bow_unloaded': 5
}


class Mongolek(controller.Controller):
    def __init__(self, first_name: str):
        self.possible_menhir_coords = []
        self.mist_available = None
        self.move_number = 0
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

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.move_number += 1
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        me = knowledge.visible_tiles[position].character
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon
        cut = WEAPONS[self.weapon.name].cut_positions(self.arena.terrain, position,
                                                      self.facing)
        for coord, tile in visible_tiles.items():
            if tile.character and Coords(coord[0],
                                         coord[1]) in cut:
                return Action.ATTACK
            if effects.EffectDescription(type='mist') in tile.effects:
                self.mist_available = True

            if tile.consumable and self.distance(position, coord[0], coord[1]) <= 5:
                self.target = coordinates.Coords(coord[0], coord[1])

            elif tile.loot is not None and WEAPONS_VALUE[self.weapon.name] < WEAPONS_VALUE[
                tile.loot.name] and self.distance(position, coord[0], coord[1]) <= 10:
                self.target = coordinates.Coords(coord[0], coord[1])

            elif tile.character and tile.character.controller_name != me.controller_name and self.health > 0.3 * CHAMPION_STARTING_HP and self.distance(position, coord[0], coord[1]) <= 3:
                for coord_cut in cut:
                    if coord_cut in self.possible_menhir_coords:
                        self.target = coordinates.Coords(coord_cut[0], coord_cut[1])
                        break
                    else:
                        self.target = coordinates.Coords(coord[0], coord[1])

            elif tile.type == 'menhir' and self.move_number > 20:
                self.target = coordinates.Coords(coord[0], coord[1])

        if self.target:
            if position == self.target:
                self.target = None
                possible = [1, 1, 4]
                return random.choices(POSSIBLE_MOVES, possible, k=1)[0]
            else:
                return self.go_to_target(knowledge, self.target)
        else:
            self.target = random.choice(self.possible_menhir_coords)
            return self.go_to_target(knowledge, self.target)

    @staticmethod
    def distance(coords: coordinates.Coords, x: int, y: int):
        return np.abs(coords.x - x) + np.abs(coords.y - y)

    def praise(self, score: int) -> None:
        raise NotImplementedError

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.facing = None
        self.health = None
        self.weapon = None
        self.arena = arenas.Arena.load(arena_description.name)
        self.move_number = 0
        self.gps = astar.PathFinder(arena_description)
        self.arena = arenas.Arena.load(arena_description.name)
        self.menhir_found = False
        self.target = None

        for coords in self.arena.terrain.keys():
            if self.arena.terrain[coords].terrain_passable():
                self.possible_menhir_coords.append(coords)

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

        if current_coordinates.x + current_facing.value.x == path[
            0].x and current_coordinates.y + current_facing.value.y == path[0].y:
            return characters.Action.STEP_FORWARD
        if current_coordinates.x + current_facing.turn_right().value.x == path[
            0].x and current_coordinates.y + current_facing.turn_right().value.y == path[0].y:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT


POTENTIAL_CONTROLLERS = [
    Mongolek("Mongolek"),
]

import random
from typing import Dict, List

from gupb.controller.bandyta.utils import POSSIBLE_ACTIONS, get_distance, get_direction, Direction, left_walk
from gupb.model import characters, tiles
from gupb.model.characters import ChampionKnowledge
from gupb.model import arenas
from gupb.model.coordinates import Coords
from gupb.controller.bandyta.bfs import find_path
from gupb.model.coordinates import sub_coords
from math import fabs

from gupb.model.weapons import WeaponDescription


class Bandyta:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.landscape_map: Dict[int, Dict[int, str]] = {}
        self.path: List[Coords] = []

    def __eq__(self, other: object):
        if isinstance(other, Bandyta):
            return self.first_name == other.first_name
        return False

    def __hash__(self):
        return hash(self.first_name)

    def attack_possible(self, my_coord: Coords, enemy_coord: Coords, weapon: WeaponDescription) -> bool:
        sub = sub_coords(my_coord, enemy_coord)
        if weapon.name == 'sword':
            return (fabs(sub.x) <= 3 and sub.y == 0) or (fabs(sub.y) <= 3 and sub.x == 0)
        elif weapon.name == 'bow':
            return (fabs(sub.x) <= 50 and sub.y == 0) or (fabs(sub.y) <= 50 and sub.x == 0)
        else:
            return (fabs(sub.x) == 1 and sub.y == 0) or (fabs(sub.y) == 1 and sub.x == 0)

    def decide(self, knowledge: ChampionKnowledge):
        try:
            self.memorize_landscape(knowledge)
            direction = get_direction(knowledge)
            player = self.find_player(knowledge.visible_tiles)
            menhir = self.find_menhir(knowledge.visible_tiles)
            if player is not None and self.attack_possible(knowledge.position, player, self.get_my_weapon(knowledge.visible_tiles)):
                self.path = []
                return characters.Action.ATTACK

            if player is not None or menhir is not None or len(self.path) != 0:
                if len(self.path) == 0:
                    if player is not None and get_distance(knowledge.position, player) < 8:
                        self.path = find_path(knowledge.position, player, self.landscape_map)
                        if len(self.path) != 0:
                            self.path.pop(0)

                    if menhir is not None and get_distance(knowledge.position, menhir) < 8:
                        self.path = find_path(knowledge.position, menhir, self.landscape_map)
                        if len(self.path) != 0:
                            self.path.pop(0)

                if len(self.path) != 0:
                    action = self.move_on_path(knowledge.position, direction)
                    return action
            return random.choice(POSSIBLE_ACTIONS)
        except Exception as e:
            print(e)
            return random.choice(POSSIBLE_ACTIONS)

    def reset(self, arena_description: arenas.ArenaDescription):
        pass

    def get_my_weapon(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for cords, tile in visible_tiles.items():
            if tile.character is not None and tile.character.controller_name == self.name:
                return tile.character.weapon

    @property
    def name(self):
        return f'Bandyta{self.first_name}'

    @property
    def preferred_tabard(self):
        return characters.Tabard.GREY

    def memorize_landscape(self, knowledge: ChampionKnowledge):
        for cords, tile in knowledge.visible_tiles.items():
            if cords[0] not in self.landscape_map:
                self.landscape_map[cords[0]] = {}
            self.landscape_map[cords[0]][cords[1]] = tile.type

    def find_player(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for cords, tile in visible_tiles.items():
            if (tile.character is not None and tile.character.controller_name != self.name): #or tile.type == 'menhir':
                return cords
        return None

    def find_menhir(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for cords, tile in visible_tiles.items():
            if tile.type == 'menhir':
                return cords
        return None

    def move_on_path(self, position: Coords, direction: Direction) -> characters.Action:
        if position + direction.value == self.path[0]:
            self.path.pop(0)
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_LEFT

import math
import random

from gupb.controller import keyboard
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import arenas
from gupb.model import weapons

from gupb.controller.dzikie_borsuki.utils import PathFinder

ACTIONS_WITH_WEIGHTS = {
    characters.Action.TURN_LEFT: 0.1,
    characters.Action.TURN_RIGHT: 0.1,
    characters.Action.STEP_FORWARD: 0.8,
}

WEAPON_DICT = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}

# ranking do ustalenia
WEAPON_RANKING = {
    'knife': 1,
    'amulet': 2,
    'sword': 3,
    'bow': 4,
    'axe': 5
}

TABARD_ASSIGNMENT = {
    "dzikie_borsuki": characters.Tabard.VIOLET
}


class RunawayStrategy:
    pass


class AggressiveStrategy:
    pass


POSSIBLE_STRATEGY = {
    'runaway': RunawayStrategy,
    'aggressive': AggressiveStrategy,
}


class DzikieBorsuki:
    def __init__(self, first_name: str):
        self.gps = None
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DzikieBorsuki):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_coords = None
        self.gps = PathFinder(arena_description)
        self.path = []
        """self.menhir_coords = None
        self.weapon = "knife"
        self.better_weapon_cords = None"""

    def calculate_distance(self, self_position: coordinates.Coords, other_position: coordinates.Coords) -> int:
        distance = math.sqrt((self_position[0] - other_position[0]) ** 2 + (self_position[1] - other_position[1]) ** 2)
        return int(round(distance))

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles
        nearest_enemy_distance = 35000

        """
        for visible_position in visible_tiles.keys():
            if visible_tiles[visible_position].character is not None \
                    and visible_tiles[visible_position].character.controller_name != self.first_name:
                nearest_enemy_distance = min(nearest_enemy_distance,
                                             self.calculate_distance(position, visible_position))

                print("Wróg w odległości ", nearest_enemy_distance)"""
        for visible_position in visible_tiles.keys():
            if self.menhir_coords is None and visible_tiles[visible_position].type == 'menhir':
                self.menhir_coords = visible_position
            """
            if self.weapon == "knife" and self.better_weapon_cords is None \
                    and visible_tiles[visible_position].loot is not None:
                if visible_tiles[visible_position].loot.name == "sword":
                    self.better_weapon_cords = visible_position """
        self_description = visible_tiles[position].character
        if self.menhir_coords is not None:
            path_to_menhir = self.gps.find_path(position, coordinates.Coords(self.menhir_coords[0],\
                                                                              self.menhir_coords[1]))
            self.path = path_to_menhir
        if self_description is not None:
            health = self_description.health
            facing = self_description.facing
            tile_in_front_coords = facing.value + position
            tile_in_front = visible_tiles[tile_in_front_coords]
            if health >= characters.CHAMPION_STARTING_HP * 0.25 and tile_in_front.character is not None:
                return characters.Action.ATTACK
            if visible_tiles[position].type == "menhir":
                return characters.Action.TURN_RIGHT
            type_of_tile = tile_in_front.type
            if type_of_tile in ["sea", "wall"]:
                return random.choice([characters.Action.TURN_RIGHT, characters.Action.TURN_LEFT])
            elif type_of_tile == "menhir":
                return characters.Action.STEP_FORWARD
        return random.choices(population=list(ACTIONS_WITH_WEIGHTS.keys()),
                              weights=list(ACTIONS_WITH_WEIGHTS.values()),
                              k=1)[0]

    @property
    def name(self) -> str:
        return f'RandomController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


POTENTIAL_CONTROLLERS = [
    DzikieBorsuki("Borsuk"),
]

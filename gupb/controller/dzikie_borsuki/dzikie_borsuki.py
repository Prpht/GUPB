import math
import random

from gupb.controller import keyboard
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import arenas
from gupb.model import weapons

from gupb.controller.dzikie_borsuki import utils

ACTIONS_WITH_WEIGHTS = {
    characters.Action.TURN_LEFT: 0.1,
    characters.Action.TURN_RIGHT: 0.1,
    characters.Action.STEP_FORWARD: 0.8,
}

# ranking do ustalenia
WEAPON_RANKING = {
    'knife': 1,
    'amulet': 5,
    'sword': 4,
    'bow_unloaded': 2,
    'bow_loaded': 2,
    'axe': 3
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
        self.better_weapon_coords = None
        self.gps = utils.PathFinder(arena_description)
        self.arena = arenas.Arena.load(arena_description.name)
        self.path = []
        self.weapon = 'knife'

    def calculate_distance(self, self_position: coordinates.Coords, other_position: coordinates.Coords) -> int:
        distance = math.sqrt((self_position[0] - other_position[0]) ** 2 + (self_position[1] - other_position[1]) ** 2)
        return int(round(distance))

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles
        nearest_enemy_distance = 35000

        for visible_position in visible_tiles.keys():
            # Szukamy menhira
            if self.menhir_coords is None and visible_tiles[visible_position].type == 'menhir':
                self.menhir_coords = visible_position
                
            # Szukamy lepszej broni
            if visible_tiles[visible_position].loot is not None:
                my_weapon = WEAPON_RANKING[knowledge.visible_tiles[knowledge.position].character.weapon.name]
                other_weapon = WEAPON_RANKING[visible_tiles[visible_position].loot.name]
                if other_weapon > my_weapon:
                    self.better_weapon_coords = visible_position
                    
            # Jesli podnieslismy lepsza bron to juz nas nie interesuje 
            if self.better_weapon_coords == position:
                self.better_weapon_coords = None
                
        self_description = visible_tiles[position].character
        # Jesli menhir jest znaleziony to idziemy do niego
        if self.menhir_coords is not None and len(self.path) == 0:
            path_to_menhir = self.gps.find_path(position, coordinates.Coords(self.menhir_coords[0],\
                                                                              self.menhir_coords[1]))
            self.path = path_to_menhir
        
        # Ale jesli widzimy lepsza bron to idziemy po nia najpierw
        if self.better_weapon_coords is not None and len(self.path) == 0:
            path_to_weapon = self.gps.find_path(position, coordinates.Coords(self.better_weapon_coords[0],\
                                                                             self.better_weapon_coords[1]))
            self.path = path_to_weapon
            
        if self_description is not None:
            health = self_description.health
            facing = self_description.facing
            tile_in_front_coords = facing.value + position
            tile_in_front = visible_tiles[tile_in_front_coords]
            weaponable_tiles = utils.get_weaponable_tiles(self.arena, position, facing, self.weapon)
            
            if health >= characters.CHAMPION_STARTING_HP * 0.25:
                for tile_coords in weaponable_tiles:
                    if visible_tiles[tile_coords].character is not None:
                        return characters.Action.ATTACK
            
            if visible_tiles[position].type == "menhir":
                return characters.Action.TURN_RIGHT
            if len(self.path) != 0:
                if position == self.path[0]:
                    self.path.pop(0)
                next_action = utils.next_step(position, coordinates.Coords(*self.path[0]), facing)
                return next_action

            #jeśli napiszemy iście do celu i jakieś startegie odkrywania mapy, to ten kawałek kodu nie będzie potrzebny
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
        return f'DzikiController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


POTENTIAL_CONTROLLERS = [
    DzikieBorsuki("Borsuk"),
]
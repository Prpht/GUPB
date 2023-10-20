# meaningful commit
import math
import random

from gupb.controller import keyboard
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import arenas
from gupb.model import weapons
from gupb.model import tiles
from gupb.model import effects

from gupb.controller.dzikie_borsuki import utils

ACTIONS_WITH_WEIGHTS = {
    characters.Action.TURN_LEFT: 0.1,
    characters.Action.TURN_RIGHT: 0.1,
    characters.Action.STEP_FORWARD: 0.8,
}

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
        self.possible_menhir_coords = []

        self.weapon = 'knife'
        self.better_weapon = 'knife'
        self.better_weapon_coords = None

        self.nearest_potion_coords = None

        self.gps = utils.PathFinder(arena_description)
        self.arena = arenas.Arena.load(arena_description.name)
        self.path = []
        self.dangerous_tiles = []

        for coords in self.arena.terrain.keys():
            if self.arena.terrain[coords].passable:
                self.possible_menhir_coords.append(coords)

    def calculate_distance(self, self_position: coordinates.Coords, other_position: coordinates.Coords) -> int:
        distance = math.sqrt((self_position[0] - other_position[0]) ** 2 + (self_position[1] - other_position[1]) ** 2)
        return int(round(distance))

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles
        nearest_enemy_distance = 35000
        self_description = visible_tiles[position].character
        self.weapon = self_description.weapon.name
        self.dangerous_tiles = []

        if len(self.path) != 0:
            if position == self.path[0]:
                self.path.pop(0)

        if self.nearest_potion_coords is not None and self.nearest_potion_coords in visible_tiles.keys():
            if visible_tiles[self.nearest_potion_coords].consumable is None:
                self.nearest_potion_coords = None

        if self.nearest_potion_coords is None:
            current_dist_to_potion = 3500
        else:
            current_dist_to_potion = len(self.gps.find_path(position, coordinates.Coords(self.nearest_potion_coords[0], \
                                                                                     self.nearest_potion_coords[1])))

        # Badanie pola widzenia
        for visible_position in visible_tiles.keys():
            # Jesli nie mamy menhira, ale go widzimy
            if self.menhir_coords is None and visible_tiles[visible_position].type == 'menhir':
                self.menhir_coords = visible_position

            # Jesli widzimy jakas bron
            if visible_tiles[visible_position].loot is not None:
                other_weapon = visible_tiles[visible_position].loot.name
                # Jesli jest lepsza od naszej obecnej
                if WEAPON_RANKING[other_weapon] > WEAPON_RANKING[self.weapon]:
                    # I do tego jest lepsza niz to co widzielismy wczesniej
                    if WEAPON_RANKING[other_weapon] > WEAPON_RANKING[self.better_weapon]:
                        # To ja sobie zapisujemy
                        self.better_weapon_coords = visible_position
                        self.better_weapon = other_weapon

            # Zbieranie info o tym ktore pola atakuje przeciwnik
            if visible_tiles[visible_position].character is not None and visible_position != position:
                enemy = visible_tiles[visible_position].character
                enemy_weapon = enemy.weapon.name
                danger_zone = utils.get_weaponable_tiles(self.arena, visible_position, enemy.facing, enemy_weapon)
                self.dangerous_tiles += danger_zone

            if visible_tiles[visible_position].consumable is not None and visible_position not in self.dangerous_tiles:
                new_dist_to_potion = len(self.gps.find_path(position, visible_position))
                if new_dist_to_potion < min(5, current_dist_to_potion):
                    self.nearest_potion_coords = visible_position

        # Odrzucamy "zobaczone" pola z listy do odkrycia
        self.possible_menhir_coords = [coord for coord in self.possible_menhir_coords if
                                       coord not in visible_tiles.keys()]

        if self.better_weapon_coords == position:
            self.better_weapon_coords = None

        if self_description is not None:
            health = self_description.health
            facing = self_description.facing
            tile_in_front_coords = facing.value + position
            tile_in_front = visible_tiles[tile_in_front_coords]
            weaponable_tiles = utils.get_weaponable_tiles(self.arena, position, facing, self.weapon)

            if self.weapon == 'bow_unloaded':
                return characters.Action.ATTACK

            # Tutaj w zaawansowanej wersji musimy decydowac czy walczymy czy uciekamy
            for tile_coords in weaponable_tiles:
                if tile_coords in visible_tiles.keys():
                    if visible_tiles[tile_coords].character is not None:
                        return characters.Action.ATTACK

            if position in self.dangerous_tiles:
                if position + facing.value not in self.dangerous_tiles and self.arena.terrain[
                    position + facing.value].passable:
                    return characters.Action.STEP_FORWARD
                safe_spot = utils.find_safe_spot(position, self.dangerous_tiles, self.arena)
                if safe_spot is not None:
                    self.path = self.gps.find_path(position, safe_spot)
                    next_action = utils.next_step(position, coordinates.Coords(*self.path[0]), facing)
                    return next_action

            if self.nearest_potion_coords is not None:
                if len(self.path) == 0 or self.path[-1] != self.nearest_potion_coords:
                    path_to_potion = self.gps.find_path(position, coordinates.Coords(self.nearest_potion_coords[0], \
                                                                                         self.nearest_potion_coords[1]))
                    self.path = path_to_potion

            if visible_tiles[position].type == "menhir" and self.weapon != "knife":
                return characters.Action.TURN_RIGHT

            if len(self.path) == 0:
                if self.menhir_coords is not None and self.weapon != "knife":
                    path_to_menhir = self.gps.find_path(position, coordinates.Coords(self.menhir_coords[0], \
                                                                                     self.menhir_coords[1]))
                    self.path = path_to_menhir

                elif self.better_weapon_coords is not None:
                    path_to_weapon = self.gps.find_path(position, coordinates.Coords(self.better_weapon_coords[0], \
                                                                                     self.better_weapon_coords[1]))
                    self.path = path_to_weapon

                else:
                    random_destination = random.choice(self.possible_menhir_coords)
                    path_to_destination = self.gps.find_path(position, random_destination)
                    self.path = path_to_destination

            next_action = utils.next_step(position, coordinates.Coords(*self.path[0]), facing)
            if next_action == characters.Action.STEP_FORWARD:
                if (position + facing.value) in self.dangerous_tiles \
                        or visible_tiles[(position + facing.value)].character is not None:
                    safe_spot = utils.find_safe_spot(position, self.dangerous_tiles, self.arena)
                    if safe_spot is not None:
                        self.path = self.gps.find_path(position, safe_spot)
                        next_action = utils.next_step(position, coordinates.Coords(*self.path[0]), facing)
            return next_action

            # jeśli napiszemy iście do celu i jakieś startegie odkrywania mapy, to ten kawałek kodu nie będzie potrzebny
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

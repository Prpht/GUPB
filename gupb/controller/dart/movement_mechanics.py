import math
from typing import Dict, List, Optional
from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from gupb.model.arenas import FIXED_MENHIRS, Arena, ArenaDescription
from gupb.model.consumables import Consumable
from gupb.model.coordinates import Coords
from gupb.model.characters import Action, ChampionDescription, ChampionKnowledge, Facing
from gupb.model.tiles import TileDescription
from gupb.model.weapons import Weapon
import numpy as np

ArenaMatrix = List[List[bool]]

TURN_ACTIONS = {
    (Facing.UP, Facing.RIGHT): Action.TURN_RIGHT,
    (Facing.UP, Facing.DOWN): Action.TURN_RIGHT,
    (Facing.UP, Facing.LEFT): Action.TURN_LEFT,
    (Facing.RIGHT, Facing.UP): Action.TURN_LEFT,
    (Facing.RIGHT, Facing.DOWN): Action.TURN_RIGHT,
    (Facing.RIGHT, Facing.LEFT): Action.TURN_RIGHT,
    (Facing.DOWN, Facing.UP): Action.TURN_LEFT,
    (Facing.DOWN, Facing.RIGHT): Action.TURN_LEFT,
    (Facing.DOWN, Facing.LEFT): Action.TURN_RIGHT,
    (Facing.LEFT, Facing.UP): Action.TURN_RIGHT,
    (Facing.LEFT, Facing.RIGHT): Action.TURN_RIGHT,
    (Facing.LEFT, Facing.DOWN): Action.TURN_LEFT
}


class MapKnowledge():
    def __init__(self, arena_description: ArenaDescription):
        self.arena = Arena.load(arena_description.name)
        self.arena_matrix = self._create_arena_matrix()
        self.arena_menhir = None
        self.weapons: Dict[Coords, str] = dict()
        self.initialize_weapons_positions()
        self.closest_mist_coords: Optional[Coords] = None
        self.mist_coords: List[Coords] = []
        self.mists = set()
        self.opponents: Dict[str, Coords] = dict()
        self.consumables: Dict[Coords, str] = dict()

    def _create_arena_matrix(self) -> ArenaMatrix:
        arena_matrix = [[1 for _ in range(self.arena.size[0])] for _ in range(self.arena.size[1])]
        for cords, tile in self.arena.terrain.items():
            arena_matrix[cords.y][cords.x] = 0 if tile.description().type in ['wall', 'sea'] else 1
        return arena_matrix

    def find_menhir(self) -> Coords:
        if self.arena.name in FIXED_MENHIRS:
            return FIXED_MENHIRS[self.arena.name]
        if self.arena_menhir:
            return self.arena_menhir
        if len(self.mists) > 3:
            try:
                return self.calculate_menhir_center()
            except:
                pass
        y = self.arena.size[0]//2
        for i in range(self.arena.size[0]//2):
            x = self.arena.size[0]//2 + i
            if self.arena_matrix[y][x]:
                return Coords(x, y)

    def find_path(self, start: Coords, end: Coords) -> List[Coords]:
        grid = Grid(matrix=self.arena_matrix)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        start = grid.node(start.x, start.y)
        end = grid.node(end.x, end.y)
        path, _ = finder.find_path(start, end, grid)
        return path[1:]

    def initialize_weapons_positions(self) -> None:
        self.weapons = {coords: tile.loot.description().name
                        for coords, tile in self.arena.terrain.items() if tile.loot is not None}

    def get_closest_weapon_path(self, current_position: Coords, *weapon_types: str) -> List[Coords]:
        weapons_coords = [coords for coords, type in self.weapons.items() if type.startswith(weapon_types)]
        if not weapons_coords:
            return []
        return self.find_shortest_path(current_position, weapons_coords)

    def get_closest_consumable_path(self, current_position: Coords, *consumable_types: str) -> List[Coords]:
        consumables_coords = [coords for coords, type in self.consumables.items() if type.startswith(consumable_types)]
        if not consumables_coords:
            return []
        return self.find_shortest_path(current_position, consumables_coords)

    def find_shortest_path(self, current_position: Coords, destinations: List[Coords]) -> List[Coords]:
        paths = [self.find_path(current_position, dest) for dest in destinations]
        return min(paths, key=lambda p: len(p) if p else float("inf"))

    def find_closest_coords(self, current_position: Coords, destinations: List[Coords]) -> Coords:
        return min(destinations, key=lambda dest: len(self.find_path(current_position, dest)))

    def is_land(self, coords: Coords) -> bool:
        return self.arena_matrix[coords.y][coords.x]

    def check_if_tile_is_mist_free(self, knowledge: ChampionKnowledge, coord):
        if coord in knowledge.visible_tiles:
            for effect_desc in knowledge.visible_tiles[coord].effects:
                if effect_desc.type == "mist":
                    return False
            return True
        return False

    def get_visible_mist(self, knowledge: ChampionKnowledge, coords, tile):
        if coords in self.mists:
            self.mists.remove(coords)
        if is_mist(tile):
            for i in (-1, 1):
                adj_coord_x = Coords(*coords) + Coords(i, 0)
                adj_coord_y = Coords(*coords) + Coords(0, i)
                if self.check_if_tile_is_mist_free(knowledge, adj_coord_x) or \
                        self.check_if_tile_is_mist_free(knowledge, adj_coord_y):
                    self.mists.add(coords)

    def update_map_knowledge(self, knowledge: ChampionKnowledge) -> None:
        self.opponents = dict()
        for coords, tile in knowledge.visible_tiles.items():
            if is_weapon(tile.loot):
                self.weapons[Coords(*coords)] = tile.loot.name
            if is_mist(tile):
                self.mist_coords.append(Coords(*coords))
            if is_opponent(tile.character):
                self.opponents[tile.character.controller_name] = Coords(*coords)
            if is_menhir(tile):
                self.arena_menhir = Coords(*coords)
            if is_consumable(tile.consumable):
                self.consumables[Coords(*coords)] = tile.consumable.name
            if coords in self.consumables and not is_consumable(tile.consumable):
                del self.consumables[Coords(*coords)]
            self.get_visible_mist(knowledge, coords, tile)
        mist_coords_and_distances = [(coords, euclidean_distance(knowledge.position, coords))
                                     for coords in self.mist_coords]
        self.closest_mist_coords = min(mist_coords_and_distances, key=lambda x: x[1])[0] \
            if mist_coords_and_distances else None

    def calculate_menhir_center(self):
        from scipy import optimize
        mist_x = np.array([coord[0] for coord in self.mists])
        mist_y = np.array([coord[1] for coord in self.mists])

        x_m = np.mean(mist_x)
        y_m = np.mean(mist_y)

        def calc_R(xc, yc):
            return np.sqrt((mist_x - xc) ** 2 + (mist_y - yc) ** 2)

        def f_2(c):
            Ri = calc_R(*c)
            return Ri - Ri.mean()

        center_estimate = x_m, y_m
        center_2, ier = optimize.leastsq(f_2, center_estimate)

        xc_2, yc_2 = center_2
        Ri_2 = calc_R(*center_2)
        R_2 = Ri_2.mean()

        x = max(0, min(self.arena.size[0] - 1, round(xc_2)))
        y = max(0, min(self.arena.size[1] - 1, round(yc_2)))
        for i in range(self.arena.size[0]):
            for sign_x, sign_y in [(1, 1), (-1, 1), (1, -1), (-1, -1)]:
                new_x = min(self.arena.size[0] - 1, max(0, x + i * sign_x))
                new_y = min(self.arena.size[1] - 1, max(0, y + i * sign_y))
                menhir = Coords(new_x, new_y)
                if self.is_land(menhir):
                    return menhir
        raise RuntimeError("Could not find run destination")


def follow_path(path: List[Coords], knowledge: ChampionKnowledge) -> Action:
    next_position = Coords(*path[0])
    current_facing = get_facing(knowledge)
    desired_facing = get_desired_facing(knowledge.position, next_position)
    return determine_rotation_action(current_facing, desired_facing)


def get_facing(knowledge: ChampionKnowledge) -> Facing:
    tile = knowledge.visible_tiles.get(knowledge.position)
    return tile.character.facing


def get_desired_facing(current_position: Coords, desired_position: Coords) -> Facing:
    desired_facing_coordinates = desired_position - current_position
    return Facing(desired_facing_coordinates)


def determine_rotation_action(current_facing: Facing, desired_facing: Facing) -> Action:
    if current_facing == desired_facing:
        return Action.STEP_FORWARD
    return TURN_ACTIONS[(current_facing, desired_facing)]


def is_opponent_at_coords(opponent_position: Coords, visible_tiles: Dict[Coords, TileDescription]) -> bool:
    if opponent_position not in visible_tiles:
        return False
    opponent = visible_tiles[opponent_position].character
    return is_opponent(opponent)


def is_potion_at_coords(potion_position: Coords, visible_tiles: Dict[Coords, TileDescription]) -> bool:
    if potion_position not in visible_tiles:
        return False
    consumable = visible_tiles[potion_position].consumable
    return is_consumable(consumable)


def is_opponent(character: Optional[ChampionDescription]) -> bool:
    return not (character is None or character.controller_name.startswith("DartController"))


def is_mist(tile: TileDescription) -> bool:
    return "mist" in [e.type for e in tile.effects]


def is_menhir(tile: TileDescription) -> bool:
    return "menhir" == tile.type


def is_weapon(loot: Optional[Weapon]):
    return loot is not None


def is_consumable(consumable: Optional[Consumable]):
    return consumable is not None


def euclidean_distance(c1: Coords, c2: Coords) -> float:
    return math.sqrt((c1.x - c2.x)**2 + (c1.y - c2.y)**2)


def manhattan_distance(c1: Coords, c2: Coords) -> float:
    return abs(c1.x - c2.x) + abs(c1.y - c2.y)

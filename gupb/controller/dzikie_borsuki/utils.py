import pathfinding as pth
import numpy as np
from typing import List
import random
from numpy import linspace, digitize

from gupb.model.coordinates import Coords
from gupb.model import arenas
from gupb.model import characters
from gupb.model import weapons
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder


WEAPON_DICT = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}

class PathFinder():
    def __init__(self, arena_description: arenas.ArenaDescription):
        self.arena = arenas.Arena.load(arena_description.name)
        self.arena_matrix = self.create_arena_matrix()

    def create_arena_matrix(self):
        matrix = [[0 for x in range(self.arena.size[0])] for y in range(self.arena.size[1])]
        for coords, tile in self.arena.terrain.items():
            if tile.description().type in ["land", "menhir"]:
                matrix[coords[1]][coords[0]] = 1
            else:
                matrix[coords[1]][coords[0]] = 0
        return matrix

    def find_path(self, current_position: Coords, destination: Coords) -> List[Coords]:
        grid = Grid(matrix=self.arena_matrix)
        start = grid.node(current_position[0], current_position[1])
        end = grid.node(destination[0], destination[1])
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        path, _ = finder.find_path(start,end, grid)
        return path[1:]


def calculate_distance(self, self_position: Coords, other_position: Coords) -> int:
    distance = math.sqrt((self_position[0] - other_position[0]) ** 2 + (self_position[1] - other_position[1]) ** 2)
    return int(round(distance))

def next_step(current_position: Coords, next_position: Coords, facing: characters.Facing) -> characters.Action:
    if (current_position + facing.value == next_position):
        return characters.Action.STEP_FORWARD
    if (current_position + facing.turn_left().value == next_position):
        return characters.Action.TURN_LEFT
    return characters.Action.TURN_RIGHT

def get_weaponable_tiles(arena: arenas.Arena, pos: Coords, facing: characters.Facing, \
                         weapon: weapons.Weapon) -> List[Coords]:
    pos = Coords(x=pos[0], y=pos[1])
    if weapon == 'knife':
        weaponable_tiles = weapons.Knife.cut_positions(arena.terrain, pos, facing)
    elif weapon == 'sword':
        weaponable_tiles = weapons.Sword.cut_positions(arena.terrain, pos, facing)
    elif weapon == 'bow_loaded':
        weaponable_tiles = weapons.Bow.cut_positions(arena.terrain, pos, facing)
    elif weapon == 'amulet':
        weaponable_tiles = weapons.Amulet.cut_positions(arena.terrain, pos, facing)
    else:
        weaponable_tiles = weapons.Axe.cut_positions(arena.terrain, pos, facing)
    return weaponable_tiles

def set_random_destination(current_position, map_size, passable_tiles):
    half_x = int(map_size[0] / 2)
    half_y = int(map_size[1] / 2)
    if current_position[0] <= half_x:
        if current_position[1] <= half_y:
            tiles_to_choose = list(filter(lambda t: t[0] > half_x or t[1] > half_y, passable_tiles))
        else:
            tiles_to_choose = list(filter(lambda t: t[0] > half_x or t[1] <= half_y, passable_tiles))
    else:
        if current_position[1] <= half_y:
            tiles_to_choose = list(filter(lambda t: t[0] <= half_x or t[1] > half_y, passable_tiles))
        else:
            tiles_to_choose = list(filter(lambda t: t[0] <= half_x or t[1] <= half_y, passable_tiles))
    return random.choice(tiles_to_choose)

def find_safe_spot(current_position, dangerous_tiles, arena):
    possible_spots = [current_position + Coords(1, 0), current_position + Coords(0, -1),
                      current_position + Coords(0, 1), current_position + Coords(-1, 0)]
    for spot in possible_spots:
        if spot not in dangerous_tiles and arena.terrain[spot].passable:
            return spot
    return None

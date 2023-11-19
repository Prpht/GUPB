from typing import List
from gupb.model.coordinates import Coords
from gupb.model import arenas
from gupb.model import characters
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
import random
class PathFinder:
    def __init__(self, arena_description: arenas.ArenaDescription):
        self.arena = arenas.Arena.load(arena_description.name)
        self.arena_matrix = self.create_arena()

    def create_arena(self):
        matrix = [[0 for _ in range(self.arena.size[0])] for _ in range(self.arena.size[1])]
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

def next_move(current_position: Coords, next_position: Coords, facing: characters.Facing) -> characters.Action:
    if current_position + facing.value == next_position:
        return characters.Action.STEP_FORWARD
    if current_position + facing.turn_left().value == next_position:
        return characters.Action.TURN_LEFT
    return characters.Action.TURN_RIGHT

def find_safe_spot(current_position, dangerous_tiles, arena):
    possible_spots = [current_position + Coords(1, 0), current_position + Coords(0, -1),
                      current_position + Coords(0, 1), current_position + Coords(-1, 0)]
    for spot in possible_spots:
        if spot not in dangerous_tiles and arena.terrain[spot].passable:
            return spot
    return None

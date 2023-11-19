from typing import List

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.model import arenas
from gupb.model.coordinates import Coords


class PathFinder:
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

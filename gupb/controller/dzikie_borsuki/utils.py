import pathfinding as pth
import numpy as np

from gupb.model.coordinates import Coords
from gupb.model import arenas
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder


def say_hi() -> None:
    print("hi")

class PathFinder():
    def __init__(self, arena_description: arenas.ArenaDescription):
        self.arena = arenas.Arena.load(arena_description.name)
        self.arena_matrix = self.create_arena_matrix()

    def create_arena_matrix(self):
        matrix = np.zeros(self.arena.size)
        for coords, tile in self.arena.terrain.items():
            if tile.description().type in ["land", "menhir"]:
                matrix[coords] = 1
        return matrix

    def find_path(self, current_position: Coords, destination: Coords) -> [Coords]:
        grid = Grid(matrix=self.arena_matrix)
        start = grid.node(current_position.x, current_position.y)
        end = grid.node(destination.x, destination.y)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        path = finder.find_path(start,end, grid)[0]
        return path
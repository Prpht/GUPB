from gupb.model.coordinates import Coords
from gupb.model.tiles import Tile
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from .utils import map_terrain, map_path_to_actions, follow_path, manhattan_distance
from gupb.model.characters import Facing, Action
import numpy as np

grid_cache = {}


def map_tile(tile: Tile):
    if tile.terrain_passable():
        return 0
    else:
        return 1


class WorldService:
    def __init__(self, state):
        self.state = state
        self.finder = AStarFinder(diagonal_movement=DiagonalMovement.never)

        if state.arena_name not in grid_cache:
            grid_cache[state.arena_name] = map_terrain(self.state.arena_name)

        self.grid = Grid(matrix=grid_cache[state.arena_name])

    def find_path(self, coord: Coords):
        pos_x, pos_y = self.state.position
        facing = self.state.facing

        target_x, target_y = coord

        self.grid = Grid(matrix=grid_cache[self.state.arena_name])
        start = self.grid.node(pos_x, pos_y)
        end = self.grid.node(target_x, target_y)

        self.finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        path, runs = self.finder.find_path(start, end, self.grid)

        actions = follow_path(self.state.position, facing, path)

        return actions

    def find_centered_points(self):
        binary_matrix = grid_cache[self.state.arena_name]

        height, width = binary_matrix.shape
        half_height = height // 2
        half_width = width // 2

        center_points = []

        # Iterate over the four quarters
        for i in range(2):
            for j in range(2):
                quarter = binary_matrix[i * half_height:(i + 1) * half_height, j * half_width:(j + 1) * half_width]

                # Find walkable cells in the quarter
                walkable_cells = np.argwhere(quarter == 1)

                min_distance = float('inf')
                centered_point = None

                # Calculate the minimum distance for each walkable cell
                for cell in walkable_cells:
                    distance_sum = np.sum([manhattan_distance(cell, other) for other in walkable_cells])
                    if distance_sum < min_distance:
                        min_distance = distance_sum
                        centered_point = cell

                center_points.append(centered_point + [i * half_height, j * half_width])

        return center_points

    @staticmethod
    def explore():
        return [Action.TURN_LEFT]*4
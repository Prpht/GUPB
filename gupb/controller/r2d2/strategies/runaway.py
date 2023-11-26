import numpy as np
from gupb.controller.r2d2.navigation import get_move_towards_target
from gupb.controller.r2d2.strategies import Strategy
from gupb.model.characters import Action
from gupb.controller.r2d2.knowledge import R2D2Knowledge, get_all_enemies, get_cut_positions, get_threating_enemies_map
from gupb.controller.r2d2.r2d2_state_machine import R2D2StateMachine
from gupb.model.coordinates import Coords

class Runaway(Strategy):
    """
    This strategy is used to run away from the enemy.
    """
    def __init__(self):
        pass 

    def decide(self, knowledge: R2D2Knowledge, state_machine: R2D2StateMachine) -> Action:
        self.dangerous_enemies = get_threating_enemies_map(knowledge)
        danger_coords = [coords for coords, enemy in self.dangerous_enemies]
        # for each coords add its closest neighbours 
        danger_coords = np.array(danger_coords)
        danger_coords = np.concatenate((danger_coords, danger_coords + (0, 1), danger_coords + (1, 0), danger_coords + (0, -1), danger_coords + (-1, 0)))
        danger_coords = np.unique(danger_coords, axis=0)
        danger_coords = danger_coords.tolist()

        self.all_enemies = get_all_enemies(knowledge)

        cut_positions = set()
        for coords, enemy in self.all_enemies:
            cuts = get_cut_positions(coords, enemy, knowledge)
            cut_positions.update({(y, x) for y, x in cuts})

        matrix_walkable = knowledge.world_state.matrix_walkable.copy()
        matrix_walkable[[(y, x) for x, y in cut_positions]] = 0
        matrix_walkable[[(y, x) for x, y in danger_coords]] = 0


        next_coords = self._find_closest_safe_coordinate(knowledge, matrix_walkable)
        allow_moonwalk = True#knowledge.champion_knowledge.position in cut_positions

        action, already_there = get_move_towards_target(knowledge.champion_knowledge.position, next_coords, knowledge, allow_moonwalk)
        facing = knowledge.champion_knowledge.visible_tiles[knowledge.champion_knowledge.position].character.facing
        return action
        
    def _find_closest_safe_coordinate(self, knowledge: R2D2Knowledge, safety_matrix: np.ndarray) -> Coords:
        """
        Find closest coordinates to us that are not in cut_positions.
        """
        curr_pos = knowledge.champion_knowledge.position
        # convert matrix to list of coordinates 
        distances = bfs_paths(knowledge.world_state.matrix_walkable, (curr_pos.y, curr_pos.x))

        # assert that distances to all non-walkable tiles are inf
        distances[curr_pos.y, curr_pos.x] = np.inf

        distances[np.logical_not(safety_matrix)] = np.inf
        y, x = np.unravel_index(np.argmin(distances, axis=None), distances.shape)
        return Coords(int(x), int(y))
    

def bfs_paths(grid: np.ndarray, start_coord: tuple[int, int]) -> np.ndarray:
    """
    Return a matrix of distances from the starting point.
    """
    def get_neighbours(grid, curr):
        neighbours = []
        for delta in [(0, 1), (1, 0), (0, -1), (-1, 0)]:
            neighbour = (curr[0] + delta[0], curr[1] + delta[1])
            if (0 <= neighbour[0] < grid.shape[0]) and (0 <= neighbour[1] < grid.shape[1]) and grid[neighbour[0], neighbour[1]] == 1:
                neighbours.append(neighbour)
        return neighbours

    matrix = np.full(grid.shape, np.inf)
    matrix[start_coord[0], start_coord[1]] = 0
    queue = [start_coord]
    while queue:
        curr = queue.pop(0)
        for neighbour in get_neighbours(grid, curr):
            if matrix[neighbour[0], neighbour[1]] == np.inf:
                matrix[neighbour[0], neighbour[1]] = matrix[curr[0], curr[1]] + 1
                queue.append(neighbour)
    return matrix


import numpy as np
from gupb.controller.r2d2.knowledge import R2D2Knowledge, WorldState
from gupb.model import characters
from gupb.model.coordinates import Coords
from pathfinding.core.grid import Grid
from pathfinding.finder.bi_a_star import BiAStarFinder
from pathfinding.finder.dijkstra import DijkstraFinder
from pathfinding.core.diagonal_movement import DiagonalMovement

    
    # Rest of the code...
def get_move_towards_target(
    current_position: Coords, 
    target_coords: Coords, 
    knowledge: R2D2Knowledge,
    allow_moonwalk: bool = False,
) -> tuple[characters.Action, bool]:
    "Returns the next action to move to the target_coords and a flag indicating if the target was reached"
    
    # If already in 
    if current_position == target_coords:
        return characters.Action.TURN_LEFT, True   # Always better turn than do nothing
        
    facing = knowledge.champion_knowledge.visible_tiles[current_position].character.facing
    action = _try_to_find_path(current_position, target_coords, knowledge.world_state.matrix_walkable, facing, allow_moonwalk)
    if action is None:
        action = _try_to_find_path(current_position, target_coords, knowledge.world_state.matrix_walkable_no_enymy, facing, allow_moonwalk) 
    if action is None:
        action = characters.Action.TURN_RIGHT
    return action, False

def _try_to_find_path(start_coords: Coords, target_coords: Coords, matrix_walkable: np.ndarray, facing: characters.Facing, allow_moonwalk: bool) -> characters.Action | None:
        grid = Grid(matrix=matrix_walkable)
        start = grid.node(*start_coords)
        end = grid.node(*target_coords)

        # - Find the path
        finder = BiAStarFinder(diagonal_movement=DiagonalMovement.never)
        path, _ = finder.find_path(start, end, grid)
        if len(path) == 0:  # No path is possible, attack
            return characters.Action.TURN_RIGHT
        next_tile_coords = Coords(path[1].x, path[1].y)

        # - Move to the next tile
        delta = next_tile_coords - start_coords
        if allow_moonwalk:
            # print("delta, facing: ", delta, facing)
            if facing.value == characters.Facing.UP.value:
                if delta == characters.Facing.UP.value:
                    action = characters.Action.STEP_FORWARD
                if delta == characters.Facing.LEFT.value:
                    action = characters.Action.STEP_LEFT
                if delta == characters.Facing.RIGHT.value:
                    action = characters.Action.STEP_RIGHT
                if delta == characters.Facing.DOWN.value:
                    action = characters.Action.STEP_BACKWARD
            elif facing.value == characters.Facing.RIGHT.value:
                if delta == characters.Facing.UP.value:
                    action = characters.Action.STEP_LEFT
                if delta == characters.Facing.LEFT.value:
                    action = characters.Action.STEP_BACKWARD
                if delta == characters.Facing.RIGHT.value:
                    action = characters.Action.STEP_FORWARD
                if delta == characters.Facing.DOWN.value:
                    action = characters.Action.STEP_RIGHT
            elif facing.value == characters.Facing.DOWN.value:
                if delta == characters.Facing.UP.value:
                    action = characters.Action.STEP_BACKWARD
                if delta == characters.Facing.LEFT.value:
                    action = characters.Action.STEP_RIGHT
                if delta == characters.Facing.RIGHT.value:
                    action = characters.Action.STEP_LEFT
                if delta == characters.Facing.DOWN.value:
                    action = characters.Action.STEP_FORWARD
            elif facing.value == characters.Facing.LEFT.value:
                if delta == characters.Facing.UP.value:
                    action = characters.Action.STEP_RIGHT
                if delta == characters.Facing.LEFT.value:
                    action = characters.Action.STEP_FORWARD
                if delta == characters.Facing.RIGHT.value:
                    action = characters.Action.STEP_BACKWARD
                if delta == characters.Facing.DOWN.value:
                    action = characters.Action.STEP_LEFT
            return action 

        if facing.value == characters.Facing.UP.value:
            if delta == characters.Facing.UP.value:
                return characters.Action.STEP_FORWARD
            if delta == characters.Facing.LEFT.value:
                return characters.Action.TURN_LEFT
            return characters.Action.TURN_RIGHT
        
        if facing.value == characters.Facing.RIGHT.value:
            if delta == characters.Facing.RIGHT.value:
                return characters.Action.STEP_FORWARD
            if delta == characters.Facing.UP.value:
                return characters.Action.TURN_LEFT
            return characters.Action.TURN_RIGHT
        
        if facing.value == characters.Facing.DOWN.value:
            if delta == characters.Facing.DOWN.value:
                return characters.Action.STEP_FORWARD
            if delta == characters.Facing.RIGHT.value:
                return characters.Action.TURN_LEFT
            return characters.Action.TURN_RIGHT
        
        if facing.value == characters.Facing.LEFT.value:
            if delta == characters.Facing.LEFT.value:
                return characters.Action.STEP_FORWARD
            if delta == characters.Facing.DOWN.value:
                return characters.Action.TURN_LEFT
            return characters.Action.TURN_RIGHT
        
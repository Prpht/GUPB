from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.controller.botelka_ml.wisdom import State
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import sub_coords, Coords


def go_to_menhir(grid: Grid, state: State) -> Action:
    return _go_to_coords(grid, state.bot_coords, state.facing, state.menhir_coords)


def _go_to_coords(grid: Grid, bot_coords: Coords, bot_facing: Facing, destination_coords: Coords) -> Action:
    finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
    grid.cleanup()

    start = grid.node(bot_coords.x, bot_coords.y)
    end = grid.node(destination_coords.x, destination_coords.y)

    path, _ = finder.find_path(start, end, grid)

    if not path:
        return Action.DO_NOTHING

    current_cords, next_coords = path[0], path[1]
    desired_facing = Facing(sub_coords(next_coords, current_cords))

    return Action.STEP_FORWARD if bot_facing == desired_facing else _choose_rotation(bot_facing, desired_facing)


def _choose_rotation(current_facing: Facing, desired_facing: Facing) -> Action:
    current_facing_cpy = current_facing
    left_rotations, right_rotations = 0, 0

    while current_facing != desired_facing:
        current_facing = current_facing.turn_left()
        left_rotations += 1

    current_facing = current_facing_cpy
    while current_facing != desired_facing:
        current_facing = current_facing.turn_right()
        right_rotations += 1

    # Any other case
    return Action.TURN_LEFT if left_rotations < right_rotations else Action.TURN_RIGHT

import numpy as np

from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model.coordinates import Coords


def circle_from_points(p1, p2, p3):
    # Convert points to numpy arrays
    A = np.array([
        [p1[0], p1[1], 1],
        [p2[0], p2[1], 1],
        [p3[0], p3[1], 1]
    ])

    B = np.array([
        -(p1[0] ** 2 + p1[1] ** 2),
        -(p2[0] ** 2 + p2[1] ** 2),
        -(p3[0] ** 2 + p3[1] ** 2)
    ])

    # Solve using least squares (to be safe in degenerate cases)
    X = np.linalg.lstsq(A, B, rcond=None)[0]

    # Circle center coordinates
    cx = -0.5 * X[0]
    cy = -0.5 * X[1]

    return cx, cy


def position_change_to_move(curr_pos: tuple, new_pos: tuple, facing: Facing):
    move = Coords(
        curr_pos[1] - new_pos[1],
        (curr_pos[0] - new_pos[0])
    )

    if facing.value == move:
        return characters.Action.STEP_FORWARD
    elif facing.opposite().value == move:
        return characters.Action.STEP_BACKWARD
    elif facing.turn_left().value == move:
        return characters.Action.STEP_LEFT
    elif facing.turn_right().value == move:
        return characters.Action.STEP_RIGHT

    return characters.Action.DO_NOTHING

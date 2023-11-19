import os

import numpy as np

from gupb.model import characters, coordinates
from gupb.model.arenas import ArenaDescription


def init_grid(arena_description: ArenaDescription) -> np.ndarray:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))),
        'resources', 'arenas', f'{arena_description.name}.gupb'
    )

    with open(path, 'r') as f:
        arena = f.readlines()

    arena = map(lambda x: list(x.strip()), arena)
    arena = map(lambda x: list(map(lambda y: y not in '#=', x)), arena)
    arena = np.array(list(arena), dtype=np.int8)

    return arena


def next_pos_to_action(next_x: int, next_y: int, facing: characters.Facing, position: coordinates.Coords) -> characters.Action:
    if next_x > position.x:
        if facing == characters.Facing.RIGHT:
            return characters.Action.STEP_FORWARD
        elif facing == characters.Facing.UP or facing == characters.Facing.LEFT:
            return characters.Action.TURN_RIGHT
        elif facing == characters.Facing.DOWN:
            return characters.Action.TURN_LEFT
    elif next_x < position.x:
        if facing == characters.Facing.LEFT:
            return characters.Action.STEP_FORWARD
        elif facing == characters.Facing.UP or facing == characters.Facing.RIGHT:
            return characters.Action.TURN_LEFT
        elif facing == characters.Facing.DOWN:
            return characters.Action.TURN_RIGHT
    elif next_y > position.y:
        if facing == characters.Facing.DOWN:
            return characters.Action.STEP_FORWARD
        elif facing == characters.Facing.LEFT or facing == characters.Facing.UP:
            return characters.Action.TURN_LEFT
        elif facing == characters.Facing.RIGHT:
            return characters.Action.TURN_RIGHT
    elif next_y < position.y:
        if facing == characters.Facing.UP:
            return characters.Action.STEP_FORWARD
        elif facing == characters.Facing.LEFT or facing == characters.Facing.DOWN:
            return characters.Action.TURN_RIGHT
        elif facing == characters.Facing.RIGHT:
            return characters.Action.TURN_LEFT
    else:
        return characters.Action.DO_NOTHING


def next_facing(facing: characters.Facing, action: characters.Action) -> characters.Facing:
    if facing == characters.Facing.UP:
        if action == characters.Action.TURN_LEFT:
            return characters.Facing.LEFT
        elif action == characters.Action.TURN_RIGHT:
            return characters.Facing.RIGHT
        else:
            return facing
    elif facing == characters.Facing.RIGHT:
        if action == characters.Action.TURN_LEFT:
            return characters.Facing.UP
        elif action == characters.Action.TURN_RIGHT:
            return characters.Facing.DOWN
        else:
            return facing
    elif facing == characters.Facing.DOWN:
        if action == characters.Action.TURN_LEFT:
            return characters.Facing.RIGHT
        elif action == characters.Action.TURN_RIGHT:
            return characters.Facing.LEFT
        else:
            return facing
    elif facing == characters.Facing.LEFT:
        if action == characters.Action.TURN_LEFT:
            return characters.Facing.DOWN
        elif action == characters.Action.TURN_RIGHT:
            return characters.Facing.UP
        else:
            return facing

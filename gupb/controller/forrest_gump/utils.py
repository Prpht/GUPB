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


def next_pos_to_action(
        next_x: int,
        next_y: int,
        facing: characters.Facing,
        position: coordinates.Coords,
        fast: bool
) -> characters.Action:
    if next_x > position.x:
        if facing == characters.Facing.RIGHT:
            return characters.Action.STEP_FORWARD
        elif facing == characters.Facing.UP:
            return characters.Action.STEP_RIGHT if fast else characters.Action.TURN_RIGHT
        elif facing == characters.Facing.LEFT:
            return characters.Action.STEP_BACKWARD if fast else characters.Action.TURN_RIGHT
        elif facing == characters.Facing.DOWN:
            return characters.Action.STEP_LEFT if fast else characters.Action.TURN_LEFT
    elif next_x < position.x:
        if facing == characters.Facing.LEFT:
            return characters.Action.STEP_FORWARD
        elif facing == characters.Facing.UP:
            return characters.Action.STEP_LEFT if fast else characters.Action.TURN_LEFT
        elif facing == characters.Facing.RIGHT:
            return characters.Action.STEP_BACKWARD if fast else characters.Action.TURN_LEFT
        elif facing == characters.Facing.DOWN:
            return characters.Action.STEP_RIGHT if fast else characters.Action.TURN_RIGHT
    elif next_y > position.y:
        if facing == characters.Facing.DOWN:
            return characters.Action.STEP_FORWARD
        elif facing == characters.Facing.LEFT:
            return characters.Action.STEP_LEFT if fast else characters.Action.TURN_LEFT
        elif facing == characters.Facing.UP:
            return characters.Action.STEP_BACKWARD if fast else characters.Action.TURN_LEFT
        elif facing == characters.Facing.RIGHT:
            return characters.Action.STEP_RIGHT if fast else characters.Action.TURN_RIGHT
    elif next_y < position.y:
        if facing == characters.Facing.UP:
            return characters.Action.STEP_FORWARD
        elif facing == characters.Facing.LEFT:
            return characters.Action.STEP_RIGHT if fast else characters.Action.TURN_RIGHT
        elif facing == characters.Facing.DOWN:
            return characters.Action.STEP_BACKWARD if fast else characters.Action.TURN_RIGHT
        elif facing == characters.Facing.RIGHT:
            return characters.Action.STEP_LEFT if fast else characters.Action.TURN_LEFT
    else:
        return characters.Action.ATTACK


def is_facing(my_position: coordinates.Coords, other_position: coordinates.Coords, other_facing: characters.Facing):
    if (my_position.x >= other_position.x and my_position.y >= other_position.y and
            (other_facing == characters.Facing.DOWN or other_facing == characters.Facing.RIGHT)):
        return True
    elif (my_position.x >= other_position.x and my_position.y <= other_position.y and
          (other_facing == characters.Facing.UP or other_facing == characters.Facing.RIGHT)):
        return True
    elif (my_position.x <= other_position.x and my_position.y >= other_position.y and
          (other_facing == characters.Facing.DOWN or other_facing == characters.Facing.LEFT)):
        return True
    elif (my_position.x <= other_position.x and my_position.y <= other_position.y and
          (other_facing == characters.Facing.UP or other_facing == characters.Facing.LEFT)):
        return True
    else:
        return False


def closest_opposite(fields: list, position: coordinates.Coords, destination: coordinates.Coords) -> list:
    dx, dy = position.x - destination.x, position.y - destination.y
    new_position = np.array([[position.x + dx, position.y + dy]])

    fields_copy = fields.copy()
    fields_copy.remove([position.x, position.y])
    fields_copy = np.array(fields_copy)
    closest = np.argmin(np.abs(fields_copy - new_position).sum(axis=1))

    return fields_copy[closest].tolist()

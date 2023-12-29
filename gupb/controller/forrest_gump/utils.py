import os
from collections import namedtuple

import numpy as np
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder

from gupb.model import characters, coordinates
from gupb.model.arenas import ArenaDescription


class CharacterInfo(namedtuple('CharacterInfo', ['position', 'facing', 'weapon', 'health', 'menhir', 'no_alive', 'step'])):
    pass


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


def find_path(matrix: np.ndarray, position: coordinates.Coords, destination: coordinates.Coords) -> list:
    finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
    grid = Grid(matrix=matrix)

    start = grid.node(position.x, position.y)
    finish = grid.node(destination.x, destination.y)

    return finder.find_path(start, finish, grid)[0]


def distance_to(matrix: np.ndarray, position: coordinates.Coords, coords: coordinates.Coords) -> int:
    return len(find_path(matrix, position, coords)) - 1


def manhattan_distance_to(position: coordinates.Coords, coords: coordinates.Coords) -> int:
    return abs(position.x - coords.x) + abs(position.y - coords.y)


def closest_opposite(fields: list, position: coordinates.Coords, destination: coordinates.Coords) -> list:
    dx, dy = position.x - destination.x, position.y - destination.y
    new_position = np.array([[position.x + dx, position.y + dy]])

    fields_copy = fields.copy()
    fields_copy.remove([position.x, position.y])
    fields_copy = np.array(fields_copy)
    closest = np.argmin(np.abs(fields_copy - new_position).sum(axis=1))

    return fields_copy[closest].tolist()


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


def next_facing(facing: characters.Facing, action: characters.Action) -> characters.Facing:
    if action == characters.Action.TURN_LEFT:
        if facing == characters.Facing.UP:
            return characters.Facing.LEFT
        elif facing == characters.Facing.LEFT:
            return characters.Facing.DOWN
        elif facing == characters.Facing.DOWN:
            return characters.Facing.RIGHT
        elif facing == characters.Facing.RIGHT:
            return characters.Facing.UP
    elif action == characters.Action.TURN_RIGHT:
        if facing == characters.Facing.UP:
            return characters.Facing.RIGHT
        elif facing == characters.Facing.RIGHT:
            return characters.Facing.DOWN
        elif facing == characters.Facing.DOWN:
            return characters.Facing.LEFT
        elif facing == characters.Facing.LEFT:
            return characters.Facing.UP
    else:
        return facing


def next_step(position: coordinates.Coords, facing: characters.Facing, action: characters.Action) -> coordinates.Coords:
    if action == characters.Action.STEP_FORWARD:
        if facing == characters.Facing.UP:
            return coordinates.Coords(position.x, position.y - 1)
        elif facing == characters.Facing.RIGHT:
            return coordinates.Coords(position.x + 1, position.y)
        elif facing == characters.Facing.DOWN:
            return coordinates.Coords(position.x, position.y + 1)
        elif facing == characters.Facing.LEFT:
            return coordinates.Coords(position.x - 1, position.y)
    elif action == characters.Action.STEP_BACKWARD:
        if facing == characters.Facing.UP:
            return coordinates.Coords(position.x, position.y + 1)
        elif facing == characters.Facing.RIGHT:
            return coordinates.Coords(position.x - 1, position.y)
        elif facing == characters.Facing.DOWN:
            return coordinates.Coords(position.x, position.y - 1)
        elif facing == characters.Facing.LEFT:
            return coordinates.Coords(position.x + 1, position.y)
    elif action == characters.Action.STEP_LEFT:
        if facing == characters.Facing.UP:
            return coordinates.Coords(position.x - 1, position.y)
        elif facing == characters.Facing.RIGHT:
            return coordinates.Coords(position.x, position.y - 1)
        elif facing == characters.Facing.DOWN:
            return coordinates.Coords(position.x + 1, position.y)
        elif facing == characters.Facing.LEFT:
            return coordinates.Coords(position.x, position.y + 1)
    elif action == characters.Action.STEP_RIGHT:
        if facing == characters.Facing.UP:
            return coordinates.Coords(position.x + 1, position.y)
        elif facing == characters.Facing.RIGHT:
            return coordinates.Coords(position.x, position.y + 1)
        elif facing == characters.Facing.DOWN:
            return coordinates.Coords(position.x - 1, position.y)
        elif facing == characters.Facing.LEFT:
            return coordinates.Coords(position.x, position.y - 1)
    else:
        return position

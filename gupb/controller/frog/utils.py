import os
from typing import Any, List
import numpy as np
from numpy import ndarray, dtype
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords
from collections import deque


def map_terrain(arena_name) -> ndarray[Any, dtype[Any]]:
    path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))),
        'resources', 'arenas', f'{arena_name}.gupb'
    )

    with open(path, 'r') as file:
        lines = file.readlines()

    char_to_value = {
        '=': 0,  # Obstacle
        '.': 1,  # Passable land
        '#': 0,  # Obstacle
        'A': 1,  # Passable land
        'S': 1,  # Passable land
        'M': 1,  # Passable land
        'B': 1,  # Passable land
    }

    rows, cols = len(lines), len(lines[0].strip())
    matrix = np.zeros((rows, cols), dtype=int)

    for i in range(rows):
        for j in range(cols):
            matrix[i, j] = char_to_value[lines[i][j]]

    return matrix


def manhattan_distance(point1: Coords, point2: Coords):
    x1, y1 = point1
    x2, y2 = point2
    return abs(x1 - x2) + abs(y1 - y2)


def map_path_to_actions(path, character_facing: Facing, character_position: Coords) -> [Action]:
    actions = []

    # Convert initial facing to a Coords object
    current_direction = character_facing.value

    for node in path:
        # Calculate the difference between the current position and the target node
        dx = node.x - character_position.x
        dy = node.y - character_position.y

        # Determine the required actions to move to the target node
        while dx != 0 or dy != 0:
            # Determine the next action to take based on the current direction
            if dx > 0:
                if current_direction == (1, 0):
                    actions.append(Action.STEP_FORWARD)
                elif current_direction == (0, -1):
                    actions.extend([Action.TURN_RIGHT, Action.STEP_FORWARD])
                elif current_direction == (0, 1):
                    actions.extend([Action.TURN_LEFT, Action.STEP_FORWARD])
                current_direction = (1, 0)
                dx -= 1
            elif dx < 0:
                if current_direction == (-1, 0):
                    actions.append(Action.STEP_FORWARD)
                elif current_direction == (0, -1):
                    actions.extend([Action.TURN_LEFT, Action.STEP_FORWARD])
                elif current_direction == (0, 1):
                    actions.extend([Action.TURN_RIGHT, Action.STEP_FORWARD])
                current_direction = (-1, 0)
                dx += 1
            elif dy > 0:
                if current_direction == (0, 1):
                    actions.append(Action.STEP_FORWARD)
                elif current_direction == (-1, 0):
                    actions.extend([Action.TURN_LEFT, Action.STEP_FORWARD])
                elif current_direction == (1, 0):
                    actions.extend([Action.TURN_RIGHT, Action.STEP_FORWARD])
                current_direction = (0, 1)
                dy -= 1
            elif dy < 0:
                if current_direction == (0, -1):
                    actions.append(Action.STEP_FORWARD)
                elif current_direction == (-1, 0):
                    actions.extend([Action.TURN_RIGHT, Action.STEP_FORWARD])
                elif current_direction == (1, 0):
                    actions.extend([Action.TURN_LEFT, Action.STEP_FORWARD])
                current_direction = (0, -1)
                dy += 1

        # Update the initial position to the current node
        character_position = node

    return actions


def follow_path(initial_position, initial_facing, path):
    actions = []
    current_position = initial_position
    current_facing = initial_facing
    path = list(path)  # Creating a copy so we can modify it

    while len(path) > 0:
        next_node = path.pop(0)
        next_facing = get_facing(current_position, next_node)

        while current_facing != next_facing:
            if current_facing == Facing.UP:
                if next_facing == Facing.RIGHT:
                    actions.append(Action.TURN_RIGHT)
                    current_facing = Facing.RIGHT
                else:
                    actions.append(Action.TURN_LEFT)
                    current_facing = Facing.LEFT
            elif current_facing == Facing.RIGHT:
                if next_facing == Facing.DOWN:
                    actions.append(Action.TURN_RIGHT)
                    current_facing = Facing.DOWN
                else:
                    actions.append(Action.TURN_LEFT)
                    current_facing = Facing.UP
            elif current_facing == Facing.DOWN:
                if next_facing == Facing.LEFT:
                    actions.append(Action.TURN_RIGHT)
                    current_facing = Facing.LEFT
                else:
                    actions.append(Action.TURN_LEFT)
                    current_facing = Facing.RIGHT
            else:  # current_facing == Facing.LEFT
                if next_facing == Facing.UP:
                    actions.append(Action.TURN_RIGHT)
                    current_facing = Facing.UP
                else:
                    actions.append(Action.TURN_LEFT)
                    current_facing = Facing.DOWN

        for _ in range(manhattan_distance(current_position, next_node)):
            actions.append(Action.STEP_FORWARD)
        current_position = next_node

    return actions


def get_facing(current_position, next_position):
    dx = next_position.x - current_position.x
    dy = next_position.y - current_position.y

    if dx > 0:  # if we move right
        return Facing.RIGHT
    elif dx < 0:  # if we move left
        return Facing.LEFT
    elif dy > 0:  # if we move down
        return Facing.DOWN
    else:  # if we move up
        return Facing.UP

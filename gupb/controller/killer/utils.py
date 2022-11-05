from enum import Enum
from math import acos
from typing import List, Tuple
import numpy as np
from gupb.model.characters import Action
from .structures import Tree

# Available directions
_DIR = [[0, 1], [0, -1], [1, 0], [-1, 0]]


# Land descriptions
class PathConstants(Enum):
    WALL = 0
    WALKABLE = 1


class KillerInterest(Enum):
    POINT_ON_MAP = 2
    ITEM = 3
    KILLING = 4
    MENHIR = 5


def find_paths(arr: np.ndarray, curr_pos: tuple) -> Tree:
    x_bound, y_bound = np.shape(arr)
    visited = np.zeros_like(arr)

    visited[curr_pos[0]][curr_pos[1]] = 1
    queue = [curr_pos]
    paths = Tree(root_node=curr_pos)

    while len(queue) > 0:
        node = queue.pop(0)
        for i in range(4):
            x = node[0] + _DIR[i][0]
            y = node[1] + _DIR[i][1]

            if (x >= 0 and y >= 0) and \
                    (x < x_bound and y < y_bound) and \
                    (not visited[x][y]):

                visited[x][y] = 1
                pos_value = arr[x][y]
                if pos_value >= PathConstants.WALKABLE.value:
                    queue.append((x, y))
                    paths.append(node_from=node, node_to=(x, y))
                    if pos_value >= KillerInterest.POINT_ON_MAP.value:
                        paths.mark_node(node=(x, y), value=pos_value)
    return paths


def path_to_actions(initial_direction: tuple, path: List[Tuple]) -> List[Action]:
    actions = []
    curr_d = initial_direction
    for i in range(len(path) - 1):
        d = path[i + 1][0] - path[i][0], path[i + 1][1] - path[i][1]
        sign = d[1] * curr_d[0] - d[0] * curr_d[1]
        angle = acos(d[0] * curr_d[0] + d[1] * curr_d[1])
        if 1. <= angle <= 2.5:
            if sign < 0:
                actions.append(Action.TURN_RIGHT)
            else:
                actions.append(Action.TURN_LEFT)
        if 2.5 <= angle:
            # print(d)
            # print(curr_d)
            actions.append(Action.TURN_RIGHT)
            actions.append(Action.TURN_RIGHT)
        actions.append(Action.STEP_FORWARD)
        curr_d = d
    return actions

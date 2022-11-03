import numpy as np
from gupb.model.characters import Action
from gupb.controller.spejson.utils import facings, forwards


def find_path(adjacency_dict, c_from, c_to):
    accessed_from = np.zeros(len(adjacency_dict), dtype=np.int32)
    accessed_from[c_from - 1] = -1
    stack = [c_from]

    while stack:
        node_from = stack.pop(0)
        for node_to in adjacency_dict[node_from]:
            if accessed_from[node_to - 1] == 0:
                accessed_from[node_to - 1] = node_from
                stack.append(node_to)

    path = []
    step = c_to
    while step != -1:
        path.append(step)
        step = accessed_from[path[-1] - 1]

    return path[::-1]


def pathfinding_next_move(position, facing, next_cluster, clusters):
    stack = [(position, facing)]
    visited = {stack[0]: None}
    is_found = False
    pos_found = None

    while stack and not is_found:
        pos, face = stack.pop(0)

        for new_pos, new_face in list(zip([pos, pos], facings[face])) + [(tuple(forwards[face] + pos), face)]:

            if clusters[new_pos] and (new_pos, new_face) not in visited:
                visited[(new_pos, new_face)] = (pos, face)
                stack.append((new_pos, new_face))

                if clusters[new_pos] == next_cluster:
                    is_found = True
                    pos_found = (new_pos, new_face)

    path = []
    step = pos_found
    while step is not None:
        path.append(step)
        step = visited[path[-1]]

    path = path[::-1]
    if len(path) < 2:
        return None

    f_0 = path[0][1]
    f_1 = path[1][1]

    if f_0 == f_1:
        return Action.STEP_FORWARD
    elif f_1 == facings[facing][0]:
        return Action.TURN_LEFT
    elif f_1 == facings[facing][1]:
        return Action.TURN_RIGHT


def pathfinding_next_move_in_cluster(position, facing, target_pos, clusters):
    stack = [(position, facing)]
    visited = {stack[0]: None}
    is_found = False
    pos_found = None

    while stack and not is_found:
        pos, face = stack.pop(0)

        for new_pos, new_face in list(zip([pos, pos], facings[face])) + [(tuple(forwards[face] + pos), face)]:

            if clusters[new_pos] and (new_pos, new_face) not in visited:
                visited[(new_pos, new_face)] = (pos, face)
                stack.append((new_pos, new_face))

                if new_pos == target_pos:
                    is_found = True
                    pos_found = (new_pos, new_face)

    path = []
    step = pos_found
    while step is not None:
        path.append(step)
        step = visited[path[-1]]

    path = path[::-1]
    if len(path) < 2:
        return None

    f_0 = path[0][1]
    f_1 = path[1][1]

    if f_0 == f_1:
        return Action.STEP_FORWARD
    elif f_1 == facings[facing][0]:
        return Action.TURN_LEFT
    elif f_1 == facings[facing][1]:
        return Action.TURN_RIGHT

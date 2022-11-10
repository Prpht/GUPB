import numpy as np
from gupb.model.characters import Action
from gupb.controller.spejson.utils import facings, forwards


# # # Cluster-based path-finding # # #

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


# # # Field-based path-finding # # #

def calculate_dists(position, facing, traversable):
    """
    Calculate the matrix of distances from a given position and the backtracking data.
    """
    inf = -1
    stack = [(position, facing, 0)]
    visited = {(stack[0][0], stack[0][1]): None}
    distances = inf * np.ones_like(traversable)

    while stack:
        pos, face, dist = stack.pop(0)

        for new_pos, new_face in list(zip([pos, pos], facings[face])) + [(tuple(forwards[face] + pos), face)]:

            if traversable[new_pos] and (new_pos, new_face) not in visited:
                visited[(new_pos, new_face)] = (pos, face)
                stack.append((new_pos, new_face, dist + 1))
                if distances[new_pos] == inf:
                    distances[new_pos] = dist + 1

    return distances, visited


def propose_next_move(visited_from, target_pos):
    """
    Find the best greedy move towards the target point and return its length.
    """
    def backtrack_path(pos_and_facing):
        path = []
        step = pos_and_facing

        while step is not None:
            path.append(step)
            step = visited_from[path[-1]]

        return path[::-1]

    best_path = None

    for facing in ["L", "R", "U", "D"]:
        if (target_pos, facing) in visited_from:
            path = backtrack_path((target_pos, facing))

            if best_path is None or len(path) < len(best_path):
                best_path = path

    if best_path is None or len(best_path) < 2:
        return None, 0

    f_0 = best_path[0][1]
    f_1 = best_path[1][1]

    if f_0 == f_1:
        return Action.STEP_FORWARD, len(best_path) - 1
    elif f_1 == facings[f_0][0]:
        return Action.TURN_LEFT, len(best_path) - 1
    elif f_1 == facings[f_0][1]:
        return Action.TURN_RIGHT, len(best_path) - 1


def proposed_moves_to_keypoints(distances, visited_from, menhir_pos, weapons_knowledge):
    """
    Obtain the current recommendations of moves towards given keypoints.
    """
    closest_weapons = {
        weapon_letter: (sorted([
            (pos, distances[pos])
            for pos, weapon in weapons_knowledge.items()
            if weapon == weapon_letter
        ], key=lambda x: x[1])[:1] + [(None, None)])[0][0]
        for weapon_letter in ["A", "B", "S", "M"]
    }
    keypoints = {
        'menhir': menhir_pos,
        **closest_weapons,
    }
    recommendations = {
        target:
            (None, 0) if pos is None
            else propose_next_move(visited_from, pos)
        for target, pos in keypoints.items()
    }
    return recommendations

from __future__ import annotations

from typing import List, Dict

from gupb.controller.bandyta.utils import Direction, DirectedCoords, rotate_cw, rotate_cw_dc, rotate_ccw_dc, \
    step_forward
from gupb.model.coordinates import Coords


def find_path(start: DirectedCoords, end: DirectedCoords, grid: Dict[int, Dict[int, str]]) -> List[DirectedCoords]:
    queue: List[DirectedCoords] = [start]
    return_path: Dict[DirectedCoords, DirectedCoords | None] = {start: None}
    visited_list: List[DirectedCoords] = []
    directed_end: DirectedCoords | None = None

    mark_visited(start, visited_list)
    steps = 0
    while len(queue) > 0:
        steps += 1
        node = queue.pop(0)

        if (end.direction is not None and node == end) or \
                (end.direction is None and node.coords == end.coords):
            directed_end = node
            break

        explore_neighbors(node, grid, visited_list, queue, return_path)

    return reconstruct_path(start, directed_end, return_path)


def mark_visited(node: DirectedCoords, visited_list: List[DirectedCoords]):
    if node not in visited_list:
        visited_list.append(node)


def explore_neighbors(parent_node: DirectedCoords,
                      grid: Dict[int, Dict[int, str]],
                      visited_list: List[DirectedCoords],
                      queue: List[DirectedCoords],
                      return_path: Dict[DirectedCoords, DirectedCoords]):

    possible_nodes: List[DirectedCoords] = [
        step_forward(parent_node),
        rotate_cw_dc(parent_node),
        rotate_ccw_dc(parent_node),
    ]

    for node in possible_nodes:
        if node.coords[0] in grid and \
                node.coords[1] in grid[node.coords[0]] and \
                grid[node.coords[0]][node.coords[1]] in ['land', 'menhir'] and \
                node not in visited_list:
            queue.append(node)
            mark_visited(node, visited_list)
            return_path[node] = parent_node


def reconstruct_path(
        start: DirectedCoords,
        end: DirectedCoords,
        return_path: Dict[DirectedCoords, DirectedCoords | None]):

    if end is None:
        return []

    path: List[DirectedCoords] = []
    iterator = end

    while iterator is not None:
        path.append(iterator)

        if iterator not in return_path.keys():
            break

        iterator = return_path[iterator]

    path.reverse()

    if path[0] is start:
        path.pop(0)
        return path

    return []

from __future__ import annotations

from typing import List, Dict

from gupb.controller.bandyta.utils import Direction
from gupb.model.coordinates import Coords


def find_path(start: Coords, end: Coords, grid: Dict[int, Dict[int, str]]):
    queue: List[Coords] = [start]
    return_path: Dict[Coords, Coords | None] = {start: None}
    visited_list: List[Coords] = []

    mark_visited(start, visited_list)
    while len(queue) > 0:
        node = queue.pop(0)

        if node == end:
            break

        explore_neighbors(node, grid, visited_list, queue, return_path)

    return reconstruct_path(start, end, return_path)


def mark_visited(node: Coords, visited_list: List[Coords]):
    if node not in visited_list:
        visited_list.append(node)


def explore_neighbors(parent_node: Coords,
                      grid: Dict[int, Dict[int, str]],
                      visited_list: List[Coords],
                      queue: List[Coords],
                      return_path: Dict[Coords, Coords]):
    for direction in Direction:
        node = parent_node + direction.value
        if node[0] in grid and \
                node[1] in grid[node[0]] and \
                grid[node[0]][node[1]] == 'land' and \
                node not in visited_list:
            queue.append(node)
            mark_visited(node, visited_list)
            return_path[node] = parent_node


def reconstruct_path(start: Coords, end: Coords, return_path: Dict[Coords, Coords | None]):
    path: List[Coords] = []
    iterator = end

    while iterator is not None:
        path.append(iterator)
        iterator = return_path[iterator]

    path.reverse()
    return path if path[0] is start else None


from typing import List, Dict
from gupb.model.coordinates import Coords


def find_path(start: Coords, end: Coords, grid: Dict[int, Dict[int, str]]):
    queue = [(start, [])]  # start point, empty path
    #queue: Dict[Coords, List[Coords]] = {start: []}
    visited_list: List[Coords] = []

    while len(queue) > 0:
        if len(queue) > 1000:
            return []

        node, path = queue.pop(0)
        path.append(node)
        mark_visited(node, visited_list)

        if node == end:
            return path

        adj_nodes = get_neighbors(node, grid, visited_list)
        for item in adj_nodes:
            queue.append((item, path[:]))

    return []


def mark_visited(node: Coords, visited_list: List[Coords]) -> None:
    if node not in visited_list:
        visited_list.append(node)


def get_neighbors(node: Coords, grid: Dict[int, Dict[int, str]], visited_list: List[Coords]) -> List[Coords]:
    neighbors: List[Coords] = []
    append_neighbor(Coords(node[0] + 1, node[1]), grid, neighbors, visited_list)
    append_neighbor(Coords(node[0] - 1, node[1]), grid, neighbors, visited_list)
    append_neighbor(Coords(node[0], node[1] + 1), grid, neighbors, visited_list)
    append_neighbor(Coords(node[0], node[1] - 1), grid, neighbors, visited_list)
    return neighbors


def append_neighbor(
        node: Coords,
        grid: Dict[int, Dict[int, str]],
        neighbor_list: List[Coords],
        visited_list: List[Coords]) -> None:
    if node[0] in grid and \
            node[1] in grid[node[0]] and \
            grid[node[0]][node[1]] == 'land' and \
            node not in visited_list:
        neighbor_list.append(node)

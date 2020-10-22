from __future__ import annotations

import random
from dataclasses import dataclass, field
from queue import PriorityQueue
from typing import Dict, List, Type, Tuple

from gupb.model.coordinates import Coords
from gupb.model.weapons import Weapon
from ..model import SeenTile

INF = 100000000000000


@dataclass(order=True)
class Vertex:
    coords: Coords = field(compare=False)
    tile_type: SeenTile = field(compare=False)
    dist: int = INF
    prev: Vertex = field(compare=False, default=None)
    neighbours: List[Vertex] = field(compare=False, default_factory=list)

    def __str__(self) -> str:
        return self.__repr__()

    def __repr__(self) -> str:
        prev = f"({self.prev.coords})" if self.prev is not None else "N/A"
        return f"<Vertex({self.coords}, {self.tile_type}, {self.dist}, {prev})>"


def determine_path_bot(
    terrain: Dict[Coords, SeenTile],
    start: Coords,
    weapons_to_take: List[Type[Weapon]],
    menhir_position: Coords,
    dist: int = 0,
    strict: bool = True
) -> List[Coords]:
    graph = construct_graph(terrain=terrain, menhir_position=menhir_position)
    graph = dijkstra_search(graph, start, weapons_to_take)
    weapons = [
        (k, v) for k, v in graph.items() if v.tile_type.loot_type() in weapons_to_take
    ]
    weapons.sort(key=lambda e: e[1].dist)
    target_position = graph[menhir_position]
    target_position = target_position
    if not strict:
        for i in range(dist):
            ns = [n for n in target_position.neighbours if n.coords != menhir_position]
            if len(ns) == 0:
                break
            target_position = random.choice(ns)
    path = []
    if len(weapons) > 0:
        path.extend(
            get_path(graph, weapons[0][0])
        )
        graph = construct_graph(terrain=terrain, menhir_position=menhir_position)
        graph = dijkstra_search(graph, weapons[0][0], weapons_to_take)

    pm = get_path(graph, target_position.coords)
    if start and dist > 0:
        pm = pm[:-min(dist, len(pm))]
    path.extend(pm)
    return path


def dijkstra_search(
    graph: Dict[Coords, Vertex],
    start: Coords,
    weapons_to_take: List[Type[Weapon]]
) -> Dict[Coords, Vertex]:
    graph[start].dist = 0
    graph[start].prev = graph[start]
    q = PriorityQueue()
    for v in graph.values():
        q.put(v)
    checked = set()
    while not q.empty():
        u = q.get()
        if u.coords in checked:
            continue
        checked.add(u.coords)
        for v in u.neighbours:
            if v.dist > u.dist + weight(u, v, weapons_to_take):
                v.dist = u.dist + weight(u, v, weapons_to_take)
                v.prev = u
                q.put(v)
    return graph


def construct_graph(
    terrain: Dict[Coords, SeenTile],
    menhir_position: Coords
) -> Dict[Coords, Vertex]:
    vertices = {
        c: Vertex(coords=c, tile_type=v)
        for c, v in terrain.items()
        if v.terrain_passable() or c == menhir_position
    }
    for (x, y), vertex in vertices.items():
        to_check = [
            (x, max(0, y - 1)),
            (x, y + 1),
            (x - 1, y),
            (x + 1, y),
        ]
        for el in to_check:
            if el not in vertices:
                continue
            vertex.neighbours.append(vertices[el])
    return vertices


def weight(u: Vertex, v: Vertex, weapons_to_take: List[Type[Weapon]]) -> int:
    if u == v or v.tile_type.loot_type() in weapons_to_take:
        return 0
    elif v.tile_type.passable:
        return 1
    else:
        return 1000


def get_path(
    graph: Dict[Coords, Vertex],
    target: Tuple[Coords]
) -> List[Coords]:
    if graph[target].prev is None:
        return []
    reversed_path = [target]
    cycle_checker = {target}
    v, u = graph[target], graph[target].prev
    while v.coords != u.coords:
        if u.coords in cycle_checker:
            return []
        cycle_checker.add(v.coords)
        reversed_path.append(v.coords)
        v, u = u, u.prev
    return reversed_path[::-1]

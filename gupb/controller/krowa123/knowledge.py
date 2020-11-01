from __future__ import annotations

import os
import pickle
from typing import Dict, Optional, List, Type, Tuple

from gupb.model import effects
from gupb.model.arenas import Arena, ArenaDescription, Terrain
from gupb.model.characters import ChampionKnowledge, Facing, ChampionDescription
from gupb.model.coordinates import Coords
from gupb.model.games import MIST_TTH
from gupb.model.tiles import Menhir
from gupb.model.weapons import Weapon
from . import utils
from .model import SeenTile
from .pathfinding import astar_search, determine_path_bot

__all__ = ["Knowledge"]


FloydDistances = Dict[Coords, Dict[Coords, int]]
FloydNext = Dict[Coords, Dict[Coords, Coords]]
FloydResults = Tuple[FloydDistances, FloydNext]

FLOYD_DIR = os.path.join(
    os.path.dirname(__file__), "pathfinding", "data"
)


def load_floyd_results(arena_name: str) -> Optional[FloydResults]:
    target_path = os.path.join(FLOYD_DIR, f"{arena_name}.p")
    if not os.path.exists(target_path):
        return None
    with open(target_path, "rb") as f:
        return pickle.load(f)


SNEAKY_POINTS = {
    "archipelago": [
        Coords(4, 15), Coords(4, 38), Coords(29, 8), Coords(40, 6),
        Coords(45, 18), Coords(38, 24), Coords(27, 42), Coords(27, 33),
        Coords(15, 25), Coords(9, 2), Coords(21, 25), Coords(18, 23),
        Coords(26, 13)
    ],
    "dungeon": [
        Coords(2, 29), Coords(12, 29), Coords(1, 44), Coords(8, 27),
        Coords(1, 16), Coords(12, 16), Coords(12, 5), Coords(18, 10),
        Coords(29, 10), Coords(36, 11), Coords(24, 37), Coords(20, 32),
        Coords(36, 44), Coords(48, 44), Coords(39, 25), Coords(47, 25)
    ],
    "wasteland": [
        Coords(1, 41), Coords(1, 1), Coords(18, 2), Coords(29, 12),
        Coords(47, 17), Coords(32, 24), Coords(32, 26), Coords(12, 24),
        Coords(17, 40), Coords(15, 40), Coords(37, 40), Coords(21, 22),
        Coords(12, 22)
    ],
    "fisher_island": [
        Coords(19, 1), Coords(9, 7), Coords(13, 12), Coords(8, 15),
        Coords(39, 8), Coords(40, 16), Coords(14, 15), Coords(27, 22),
        Coords(20, 26), Coords(8, 24), Coords(11, 26), Coords(11, 40),
        Coords(18, 40), Coords(23, 34), Coords(30, 45), Coords(38, 44),
        Coords(39, 26)
    ]
}


def rank_points(
    points: List[Coords],
    position: Coords,
    distances: FloydDistances,
    closer_better: bool = True
) -> List[Coords]:
    points_distances = [
        (distances[x][position], x) for x in points
    ]
    if closer_better:
        points_distances = sorted(points_distances, key=lambda e: e[0])
    else:
        points_distances = reversed(sorted(points_distances, key=lambda e: e[0]))
    return [e[1] for e in points_distances]


def determine_priority_points(
    points: List[Coords],
    menhir_position: Coords,
    distances: FloydDistances
) -> List[Dict]:
    first_points = rank_points(
        points,
        menhir_position,
        distances=distances,
        closer_better=False
    )
    return [first_points[0]] + first_points[-6:-4] + [first_points[-2]]


class Knowledge:
    terrain: Dict[Coords, SeenTile]
    menhir_position: Coords
    position: Coords
    health: int
    weapon_type: Type[Weapon]
    facing: Facing

    def __init__(self, arena_description: ArenaDescription):
        arena = Arena.load(arena_description.name)
        self.terrain = {k: SeenTile(v.description()) for k, v in arena.terrain.items()}
        self.menhir_position = arena_description.menhir_position
        self.terrain[self.menhir_position] = SeenTile(Menhir().description())
        self.mist_radius = arena.mist_radius
        self.time = 0
        self.floyd_results = load_floyd_results(arena_name=arena_description.name)
        self.sneaky_points = SNEAKY_POINTS.get(arena_description.name)

    # noinspection PyDefaultArgument
    def loot(self, filter: Optional[List[str]] = None, filter_out: Optional[List[str]] = None) -> Dict[Coords, utils.W]:
        return {coord: seen_tile.loot for coord, seen_tile in self.terrain.items()
                if seen_tile.loot
                and (not filter or seen_tile.loot.name in filter)
                and (not filter_out or seen_tile.loot.name not in filter_out)}

    def check_loot(self, coord: Coords, is_type: Optional[Type[utils.W]]):
        return self.terrain[coord].loot and (not is_type or self.terrain[coord].loot_type() == is_type)

    def tile(self, coord: Coords):
        return self.terrain[coord]

    def visible_terrain(self) -> Terrain:
        return {coord: seen_tile for coord, seen_tile in self.terrain.items() if seen_tile.seen == self.time}

    def update(self, champion_knowledge: ChampionKnowledge):
        self.time += 1
        self.position = champion_knowledge.position
        _, self.health, weapon, self.facing = champion_knowledge.visible_tiles[self.position].character
        self.weapon_type = utils.weapons_dict[weapon.name]
        if self.time % MIST_TTH == 0:
            self._increase_mist()
        for coord, tile_desc in champion_knowledge.visible_tiles.items():
            self.terrain[coord].update(tile_desc, self.time)

    def find_path(self, start: Coords, end: Coords, avoid_loot: bool = True) -> Optional[List[Coords]]:
        return astar_search(self.terrain, start, end, avoid_loot)

    def find_dijkstra_path(
        self,
        weapons_to_take: List[Type[Weapon]],
        dist: int = 0,
        strict: bool = True
    ) -> List[Coords]:
        return determine_path_bot(
            terrain=self.terrain,
            start=self.position,
            weapons_to_take=weapons_to_take,
            menhir_position=self.menhir_position,
            dist=dist,
            strict=strict
        )

    def find_sneaky_path(self) -> Optional[List[Coords]]:
        if self.floyd_results is None or self.sneaky_points is None:
            return None
        try:
            priority_points = determine_priority_points(
                points=self.sneaky_points,
                menhir_position=self.menhir_position,
                distances=self.floyd_results[0]
            )
            return self.__build_sneaky_path(priority_points=priority_points)
        except Exception:
            return None

    def champions_to_attack(self) -> List[Coords, ChampionDescription]:
        return utils.get_champion_positions(
            self.visible_terrain(),
            self.weapon_type.cut_positions(self.visible_terrain(), self.position, self.facing)
        )

    def _increase_mist(self) -> None:
        self.mist_radius -= 1 if self.mist_radius > 0 else self.mist_radius
        if self.mist_radius:
            for coords in self.terrain:
                distance = utils.distance(coords, self.menhir_position)
                if distance == self.mist_radius:
                    self.terrain[coords].tile.effects.append(effects.Mist().description())

    def __build_sneaky_path(self, priority_points: List[Coords]) -> List[Coords]:
        result = [self.position]
        for i, point in enumerate(priority_points):
            pos = result[-1]
            while pos != point:
                pos = self.floyd_results[1][pos][point]
                result.append(pos)
            if len(priority_points) - (i + 1) < 2:
                idle = 20
            else:
                idle = 0
            for _ in range(idle):
                result.append(pos)
        return result

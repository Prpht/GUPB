from __future__ import annotations

from typing import Dict, Optional, List, Type

from gupb.model import effects
from gupb.model.arenas import Arena, ArenaDescription, Terrain
from gupb.model.characters import ChampionKnowledge, Facing, ChampionDescription
from gupb.model.coordinates import Coords
from gupb.model.games import MIST_TTH
from gupb.model.weapons import Weapon
from . import utils
from .model import SeenTile
from .pathfinding import astar_search, determine_path_bot

__all__ = ["Knowledge"]


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
        self.mist_radius = arena.mist_radius
        self.time = 0

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

from __future__ import annotations

from typing import Dict, Optional, List, Type

from gupb.controller.krowa123 import pathfinding, utils
from gupb.controller.krowa123.model import SeenTile
from gupb.model import weapons, effects
from gupb.model.arenas import Arena, ArenaDescription, Terrain
from gupb.model.characters import ChampionKnowledge, Facing, ChampionDescription
from gupb.model.coordinates import Coords
from gupb.model.games import MIST_TTH

__all__ = ["Knowledge"]

from gupb.model.weapons import Weapon


class Knowledge:
    terrain: Dict[Coords, SeenTile]
    menhir_position: Coords
    position: Coords
    health: int
    weapon_type: Type[weapons.Weapon]
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
        return pathfinding.astar_search(self.terrain, start, end, avoid_loot)

    def champions_to_attack(self) -> List[Coords, ChampionDescription]:
        return utils.get_champion_positions(
            self.visible_terrain(),
            self.weapon_type.cut_positions(self.visible_terrain(), self.position, self.facing)
        )

    def _increase_mist(self) -> None:
        self.mist_radius -= 1 if self.mist_radius > 0 else self.mist_radius
        if self.mist_radius:
            for coords in self.terrain:
                distance = int(((coords.x - self.menhir_position.x) ** 2 +
                                (coords.y - self.menhir_position.y) ** 2) ** 0.5)
                if distance == self.mist_radius:
                    self.terrain[coords].tile.effects.append(effects.Mist().description())

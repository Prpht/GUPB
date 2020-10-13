from __future__ import annotations

import inspect
from typing import Dict, Optional, List, Type

from gupb.controller.krowa123 import pathfinding, utils
from gupb.controller.krowa123.model import SeenTile
from gupb.model import weapons
from gupb.model.arenas import Arena, ArenaDescription, Terrain
from gupb.model.characters import ChampionKnowledge, Facing, ChampionDescription
from gupb.model.coordinates import Coords

__all__ = ["Knowledge"]


class Knowledge:
    terrain: Dict[Coords, SeenTile]
    menhir_position: Coords
    position: Coords
    health: int
    weapon_type: Type[weapons.Weapon]
    facing: Facing

    def __init__(self, arena_description: ArenaDescription):
        self.terrain = {k: SeenTile(v) for k, v in Arena.load(arena_description.name).terrain.items()}
        self.menhir_position = arena_description.menhir_position
        self.time = -1

    def visible_terrain(self) -> Terrain:
        return {coord: seen_tile.tile for coord, seen_tile in self.terrain.items() if seen_tile.seen == self.time}

    def update(self, champion_knowledge: ChampionKnowledge):
        self.time += 1
        self.position = champion_knowledge.position
        _, self.health, weapon, self.facing = champion_knowledge.visible_tiles[self.position].character
        self.weapon_type = weapons_dict[weapon.name]
        for coord, tile_desc in champion_knowledge.visible_tiles.items():
            self.terrain[coord].update(tile_desc, self.time)

    def find_path(self, start: Coords, end: Coords) -> Optional[List[Coords]]:
        return pathfinding.astar_search(self.terrain, start, end)

    def champions_to_attack(self) -> List[Coords, ChampionDescription]:
        return utils.get_champion_positions(
            self.visible_terrain(),
            self.weapon_type.cut_positions(self.visible_terrain(), self.position, self.facing)
        )


weapons_dict = {name.lower(): clazz for name, clazz in
                inspect.getmembers(weapons, lambda o: inspect.isclass(o) and issubclass(o, weapons.Weapon) and not inspect.isabstract(o))}

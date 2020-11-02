from dataclasses import dataclass
from typing import Type, Optional

from . import utils
from gupb.model.tiles import Tile, TileDescription
from gupb.model.weapons import Weapon


@dataclass
class SeenTile(Tile):
    """
    Use carefully as, the tile is a fake Tile and will be updated with descriptions and not proper classes
    """
    tile: TileDescription
    seen: int = 0

    def update(self, tile_desc: TileDescription, time: int):
        self.seen = time
        self.tile = tile_desc

    def type(self) -> Type[Tile]:
        return utils.tiles_dict[self.tile.type]

    def loot_type(self) -> Optional[Type[Weapon]]:
        return utils.weapons_dict[self.loot.name] if self.loot else None

    def mist(self) -> bool:
        return any([e.type == "mist" for e in self.tile.effects])

    @property
    def loot(self):
        return self.tile.loot

    @property
    def character(self):
        return self.tile.character

    @property
    def effects(self):
        return self.tile.effects

    def terrain_passable(self) -> bool:
        return self.type().terrain_passable()

    def terrain_transparent(self) -> bool:
        return self.type().terrain_transparent()

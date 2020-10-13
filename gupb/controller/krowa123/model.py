from dataclasses import dataclass

from gupb.model.tiles import Tile, TileDescription


@dataclass
class SeenTile:
    """
    Use carefully as, the tile is a fake Tile and will be updated with descriptions and not proper classes
    """
    tile: Tile
    seen: int = -1

    def update(self, tile_desc: TileDescription, time: int):
        self.seen = time
        _, self.tile.lost, self.tile.character, self.tile.effects = tile_desc

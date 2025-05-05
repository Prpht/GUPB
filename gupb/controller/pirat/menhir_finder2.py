from gupb.model import coordinates
from typing import Dict, Tuple
from gupb.model import tiles
from math import sqrt, ceil, isqrt
from collections import defaultdict
from gupb.model.arenas import Arena


class MenhirFinder2():
    def __init__(self, region_size: int = 5, arena: Arena = None) -> None:
        self.menhir = None
        self.is_menhir_found = False
        self.pos_wthout_menhir: set[coordinates.Coords] = set()
        self.region_size = region_size
        self.arena_size: tuple[int,int] = arena.size
        self.init_regions()
        self.get_info_about_map(arena)
        self.i = True


    def init_regions(self) -> None:
        self.all_pos = { coordinates.Coords(x, y) for x in range(self.arena_size[0]) for y in range(self.arena_size[1]) }
        self.checked_regions = defaultdict(int)

        for coord in self.all_pos:
            region = self.get_region(coord)
            self.checked_regions[region] = 0

    def get_info_about_map(self, arena: Arena) -> None:
        for coord in arena.terrain:
            tile = arena.terrain[coord]
            description = tile.description()
            if description.type == "menhir":
                self.menhir = coord
                continue

            if not tile.passable or tile.character or tile.consumable or tile.loot:
                self.pos_wthout_menhir.add(coord)
                self.checked_regions[self.get_region(coord)] += 1


    def look_for_menhir(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> None:
        for coord, tile in visible_tiles.items():
            if tile.type == "menhir":
                self.menhir = coord                
                break
            else:
                if coord not in self.pos_wthout_menhir:
                    self.pos_wthout_menhir.add(coord)
                    region = self.get_region(coord)
                    self.checked_regions[region] += 1


    def get_region(self, coord: coordinates.Coords) -> Tuple[int, int]:
        x_region = coord[0] // self.region_size
        y_region = coord[1] // self.region_size
        return (x_region, y_region)
    
    def get_region_probability(self, region: Tuple[int, int]) -> float:
        checked = self.checked_regions.get(region, 0)
        region_size = self.region_size * self.region_size
        is_different_size_on_x = isqrt(self.arena_size[0]) < ceil(sqrt((region[0] + 1) * (region[0] + 1)))
        is_different_size_on_y = isqrt(self.arena_size[1]) < ceil(sqrt((region[1] + 1) * (region[1] + 1)))
        if is_different_size_on_x or is_different_size_on_y:
            region_size = (self.region_size-1) * (self.region_size-1)
        return (region_size - checked) / region_size
    
    def get_max_probability_region(self) -> Tuple[int, int]:
        max_region = max(self.checked_regions.keys(), key=lambda region: self.get_region_probability(region))
        return max_region
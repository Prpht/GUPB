from typing import Optional, Tuple, Union
from gupb.model import coordinates
from gupb.model.tiles import TileDescription

def ensure_coords(pos: Union[coordinates.Coords, Tuple[int, int]]) -> coordinates.Coords:
    if isinstance(pos, coordinates.Coords):
        return pos
    
    return coordinates.Coords(pos[0], pos[1])

def manhattan_distance(pos1: Union[coordinates.Coords, Tuple[int,int]], pos2: Union[coordinates.Coords, Tuple[int,int]]) -> int:
    _pos1_x = pos1.x if hasattr(pos1, 'x') else pos1[0]
    _pos1_y = pos1.y if hasattr(pos1, 'y') else pos1[1]
    _pos2_x = pos2.x if hasattr(pos2, 'x') else pos2[0]
    _pos2_y = pos2.y if hasattr(pos2, 'y') else pos2[1]
    return abs(_pos1_x - _pos2_x) + abs(_pos1_y - _pos2_y)

def is_tile_safe(tile_desc: Optional[TileDescription], consider_mist: bool = True, allow_potion: bool = False) -> bool:
    if not tile_desc:
        return False
    if tile_desc.type in ['wall', 'sea']:
        return False
    if tile_desc.character:
        return False
    if consider_mist and tile_desc.effects and any(eff.type == 'mist' for eff in tile_desc.effects):
        return False
    return True

from typing import List, Optional, Tuple, Dict

from gupb.model import tiles, coordinates
from gupb.model.arenas import Terrain
from gupb.model.characters import Facing
from gupb.model.coordinates import Coords


def get_weapon_cut_positions(seen_tiles: Dict[coordinates.Coords, Tuple[tiles.TileDescription, int]],
                             terrain: Optional[Terrain],
                             character_position: Coords,
                             name: str,
                             initial_facing: Optional[Facing] = None) -> List[Coords]:
    if initial_facing is None:
        initial_facing = seen_tiles[character_position][0].character.facing
    if name == 'knife':
        return get_line_cut_positions(terrain, initial_facing, character_position, 1)
    elif name == 'sword':
        return get_line_cut_positions(terrain, initial_facing, character_position, 3)
    elif name == 'bow_unloaded' or name == 'bow_loaded':
        return get_line_cut_positions(terrain, initial_facing, character_position, 50)
    elif name == 'axe':
        centre_position = character_position + initial_facing.value
        left_position = centre_position + initial_facing.turn_left().value
        right_position = centre_position + initial_facing.turn_right().value
        return [left_position, centre_position, right_position]
    elif name == 'amulet':
        position = character_position
        return [
            Coords(*position + (1, 1)),
            Coords(*position + (-1, 1)),
            Coords(*position + (1, -1)),
            Coords(*position + (-1, -1)),
            Coords(*position + (2, 2)),
            Coords(*position + (-2, 2)),
            Coords(*position + (2, -2)),
            Coords(*position + (-2, -2)),
        ]
    else:
        return []


def get_line_cut_positions(terrain, initial_facing, character_position, reach):
    cut_positions = []
    cut_position = character_position
    for _ in range(reach):
        cut_position += initial_facing.value
        if cut_position not in terrain:
            break
        cut_positions.append(cut_position)
    return cut_positions



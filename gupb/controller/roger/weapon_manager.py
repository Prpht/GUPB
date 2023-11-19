from typing import List

from gupb.controller.roger.map_manager import MapManager
from gupb.model.coordinates import Coords


class WeaponManager:
    def __init__(self):
        pass

    def get_weapon_cut_positions(self, arena: MapManager, character_position: Coords, name: str) -> List[Coords]:
        initial_facing = arena.seen_tiles[character_position][0].character.facing
        if name == 'knife':
            return self.get_line_cut_positions(arena, initial_facing, character_position, 1)
        elif name == 'sword':
            return self.get_line_cut_positions(arena, initial_facing, character_position, 3)
        elif name == 'bow_unloaded' or name == 'bow_loaded':
            return self.get_line_cut_positions(arena, initial_facing, character_position, 50)
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

    def get_line_cut_positions(self, arena, initial_facing, character_position, reach):
        cut_positions = []
        cut_position = character_position
        for _ in range(reach):
            cut_position += initial_facing.value
            if cut_position not in arena.terrain:
                break
            cut_positions.append(cut_position)
        return cut_positions



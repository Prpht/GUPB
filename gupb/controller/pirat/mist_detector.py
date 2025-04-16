import collections
from typing import Optional, Set, List

from gupb.model import arenas, characters, coordinates
from gupb.model.effects import EffectDescription
from gupb.model.tiles import TileDescription
import math

from gupb.controller.pirat.pathfinding import PathFinder
from gupb.model.coordinates import Coords

class MistDetector:
    def __init__(self, arena: arenas.Arena, min_escape_distance: int = 2) -> None:
        self.arena = arena
        self.path_finder = PathFinder(arena)
        self.min_escape_distance = min_escape_distance
        self.escape_target: Optional[coordinates.Coords] = None
        self.mist_visible_nearby: bool = False
        self.standing_on_mist: bool = False

    def update(self, knowledge: characters.ChampionKnowledge) -> Optional[List[coordinates.Coords]]:
        self.escape_target = None
        self.mist_visible_nearby = False
        self.standing_on_mist = False

        if not knowledge.visible_tiles:
            return None

        champion_pos = knowledge.position
        visible_tiles = knowledge.visible_tiles

        current_tile = visible_tiles.get(champion_pos)
        if current_tile:
            self.standing_on_mist = any(self._is_mist(effect) for effect in current_tile.effects)

        visible_mist_coords: Set[coordinates.Coords] = set()
        for pos, tile in visible_tiles.items():
             if any(self._is_mist(effect) for effect in tile.effects):
                visible_mist_coords.add(pos)

        self.mist_visible_nearby = bool(visible_mist_coords)

        if not self.standing_on_mist and not self.mist_visible_nearby:
            return None

        self.escape_target = self._find_best_escape_tile(champion_pos, visible_mist_coords)

        if self.escape_target:
            path = self.path_finder.find_the_shortest_path(champion_pos, self.escape_target)
            return path if path else None
        else:
            return None

    def _is_mist(self, effect: EffectDescription) -> bool:
        return effect.type == 'mist'

    def _manhattan_distance(self, pos1: Coords, pos2: Coords) -> int:
        return abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y)

    def _find_best_escape_tile(self, start_pos: coordinates.Coords, visible_mist_coords: Set[coordinates.Coords]) -> Optional[coordinates.Coords]:
        queue = collections.deque([start_pos])
        visited = {start_pos}
        best_escape_tile: Optional[coordinates.Coords] = None
        max_min_mist_dist = -1

        effective_mist_coords = visible_mist_coords.copy()
        if self.standing_on_mist:
             effective_mist_coords.add(start_pos)

        if not effective_mist_coords:
             pass

        while queue:
            current_pos = queue.popleft()

            is_valid_tile = self.path_finder.is_valid(current_pos.x, current_pos.y)
            is_mist = current_pos in effective_mist_coords
            distance_from_start = self._manhattan_distance(start_pos, current_pos)

            if is_valid_tile and not is_mist and distance_from_start >= self.min_escape_distance:
                min_dist_to_mist = float('inf')
                if effective_mist_coords:
                     for mist_coord in effective_mist_coords:
                         dist = self._manhattan_distance(Coords(current_pos[0], current_pos[1]), Coords(mist_coord[0], mist_coord[1]))
                         min_dist_to_mist = min(min_dist_to_mist, dist)
                else:
                     min_dist_to_mist = float('inf')

                if min_dist_to_mist > max_min_mist_dist:
                    max_min_mist_dist = min_dist_to_mist
                    best_escape_tile = current_pos
                elif min_dist_to_mist == max_min_mist_dist:
                     pass

            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                next_coord = coordinates.Coords(current_pos.x + dx, current_pos.y + dy)

                if next_coord not in visited and self.path_finder.is_valid(next_coord.x, next_coord.y):
                    visited.add(next_coord)
                    queue.append(next_coord)

        return best_escape_tile

    def get_escape_target(self) -> Optional[coordinates.Coords]:
        return self.escape_target

    def is_mist_visible_nearby(self) -> bool:
        return self.mist_visible_nearby

    def is_standing_on_mist(self) -> bool:
        return self.standing_on_mist

from gupb.controller.norgul.arena_knowledge import ArenaKnowledge

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

from dataclasses import dataclass, field
from typing import Any, Set


# --------------------------------------
# Exploration knowledge - helper defines
# --------------------------------------

# Area class - represents a (at most) 3x3 area of map
# - Can be created using any contained tile in init() method
# - Serves as a hash index for ExplorationKnowledge table
# - TODO: Refactor to allow different area sizes (instead of hardcoded size = 3)
class Area:

    def __init__(self, sample_sq: coordinates.Coords):
        x, y = sample_sq

        # Calculate middle
        self.center = coordinates.Coords(x - x % 3 + 1, y - y % 3 + 1)
    
    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Area):
            return self.center == other.center
        return False
    
    def __hash__(self) -> int:
        return hash(self.center)
    
    def __contains__(self, sq: coordinates.Coords) -> bool:
        return abs(self.center[0] - sq[0]) <= 1 and abs(self.center[1] - sq[1]) <= 1

    # Returns an effective size of the area with respect to arena bounds
    # - Anti-pattern, but should do the job for now
    def size(self, arena: ArenaKnowledge) -> int:
        return max(0, min(3, arena.width - self.center[0] + 1)) * max(0, min(3, arena.height - self.center[1] + 1))

# Area exploration data tuple
# - explor_time: last time area was explored (at least 4 tiles seen)
# - tiles_saw: tiles which have been already seen - cleared every time an area is explored
@dataclass
class AreaExplorData:
    explor_time: float
    tiles_saw: Set


# ---------------------------
# Exploration knowledge class
# ---------------------------

# Exploration dynamic data structures 
class ExplorationKnowledge:

    def __init__(self):
        # Main data container - a dictionary for 3x3 area data
        self.areas : dict[Area, AreaExplorData] = {}

    # --------------------------------------
    # Exploration knowledge - static loading
    # --------------------------------------

    def load(self, arena: ArenaKnowledge) -> None:
        ''' Prepares self.areas dict by inserting all the keys depending on arena size '''

        # Reset previous state
        self.areas.clear()

        # Initialize counters and sets for every area (except those, which are cut-off and very small)
        for i in range(0, arena.width, 3):
            for j in range(0, arena.height, 3):
                area = Area(coordinates.Coords(i, j))

                accessable_tiles = 0
                for k in range(3):
                    for l in range(3):
                        sq = coordinates.Coords(i + k, j + l)
                        if sq in arena and arena[sq].type != "wall" and arena[sq].type != "sea":
                            accessable_tiles += 1

                if area.size(arena) >= 6 and accessable_tiles >= 3:
                    self.areas[area] = AreaExplorData(0, set())
    
    # ---------------------------------------
    # Exploration knowledge - dynamic loading
    # ---------------------------------------

    def update(self, knowledge: characters.ChampionKnowledge, time: int) -> None:
        ''' Updates area counters based on recently observed tiles'''

        # An extra set to save explored ares and reset their data later, after checking all visible tiles
        # - Prevents weird behavior which would occur if data was reset inside visible tiles loop
        explored = set()

        # We don't need any extra info about tiles, just the fact that they were observed
        for coord, tile_info in knowledge.visible_tiles.items():
            area = Area(coord)

            if ("mist",) in tile_info.effects and area in self.areas:
                self.areas.pop(area)
                if area in explored:
                    explored.remove(area)

            if area in self.areas:
                if area == Area(knowledge.position):
                    explored.add(area)
                else:
                    self.areas[area].tiles_saw.add(coord)
                    if len(self.areas[area].tiles_saw) >= 3:    # TODO: use the appropriate hyperparameter from config file
                        explored.add(area)
        
        # Now we can safely update data for the explored areas
        for area in explored:
            self.areas[area].explor_time = time
            self.areas[area].tiles_saw.clear()

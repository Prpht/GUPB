from gupb.controller.norgul.exploration_knowledge import ExplorationKnowledge, Area
from gupb.controller.norgul.memory import Memory
from gupb.controller.norgul.misc import manhattan_dist
from gupb.controller.norgul.config import EXPLORATION_MAX_TIME_DIFF, EXPLORATION_TIME_FACTOR, EXPLORATION_DISTANCE_FACTOR

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

from collections import namedtuple
from typing import Any


# ----------------
# Explorator class
# ----------------

# Represents an exploration module which constantly picks an area to explore
class Explorator:

    def __init__(self, memory: Memory):
        self.memory = memory
        self.explor_knowledge = memory.exploration

    # ----------------------------
    # Explorator - decision making
    # ----------------------------

    # Pick an area to explore
    def pick_area(self) -> coordinates.Coords:
        ''' Returns the center of most appealing area to explor '''

        # Iterate over all unexplored areas and find the most appealing one. Key rules:
        # - The earlier an area was visited, the greater priority it has (exponential relationship)
        # - The further an area is from the bot, the lower priority it has (exponential relationship)
        max_priority = 0.0
        best_area = None

        for area, explor_data in self.explor_knowledge.areas.items():
            # Calculate time difference since last exploration of an area
            # - Limit time_diff to prevent overflow
            time_diff = self.memory.time - explor_data.explor_time
            time_diff = min(time_diff, EXPLORATION_MAX_TIME_DIFF)

            # Calculate distance between areas
            # - In this case, distance unit is an area (distance in tiles divided by 3)
            curr_area = Area(self.memory.pos)
            dist = max(1, manhattan_dist(curr_area.center, area.center) // 3)

            # Final formula for priority
            priority = EXPLORATION_TIME_FACTOR ** time_diff * EXPLORATION_DISTANCE_FACTOR ** dist

            if priority > max_priority:
                max_priority = priority
                best_area = area
        
        return best_area.center if best_area is not None else None
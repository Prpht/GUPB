from gupb.controller.tuptus.pathfinder import Pathfinder
# from gupb.controller.tuptus.tuptus import WEAPON_TIERS
from gupb.controller.tuptus.map import Map
from gupb.model.coordinates import Coords
from gupb.model.characters import Facing
from typing import Optional, List
import numpy as np

WEAPON_TIERS = {
    1: "sword",
    2: "axe",
    3: "amulet",
    4: "bow_unloaded",
    5: "bow_loaded",
    6: "knife"
}



class BaseStrategy():

    def __init__(self, game_map: Map, weapon_tier: int, position: Optional[Coords], facing: Optional[Facing]):
        self.pathfinder: Pathfinder = Pathfinder(game_map)
        self.map: Map = game_map
        self.weapon_tier: int = weapon_tier
        self.position: Optional[Coords] = position
        self.facing: Optional[Facing] = facing

    def explore(self) -> List:
        """
            Fancy name for wandering around...

            Store information about seen parts of the map and go towards the unexplored?
        """
        height, width = self.map.known_map.shape

        least_explored_quadron = np.argwhere(self.map.quadron_exploration() == np.min(self.map.quadron_exploration()))[0]

        h_min = least_explored_quadron[0] * height//2
        h_max = (least_explored_quadron[0]+1) * height//2 - 1
        w_min = least_explored_quadron[1] * width//2
        w_max = (least_explored_quadron[1]+1) * width//2 - 1 


        # Find a random pair of coordinates to go to and check if it is possible 
        h = np.random.randint(h_min, h_max)
        w = np.random.randint(w_min, w_max)        
        while self.map.tuptable_map[h, w]:
            h = np.random.randint(h_min, h_max)
            w = np.random.randint(w_min, w_max)

        raw_path = self.pathfinder.astar(self.position, (h, w))
          
        return self.pathfinder.plan_path(raw_path, self.facing) if raw_path else []

    def go_to_menhir(self) -> List:
        """
            Go to menhir when the mist is approaching
        """

        if self.map.menhir_position:
            raw_path = self.pathfinder.astar(self.position, self.map.menhir_position)
            return self.pathfinder.plan_path(raw_path, self.facing) if raw_path else []
        else:
            return self.explore()

    def find_weapon(self) -> Optional[List]:
        """
            If possible find the better weapon
        """
        
        weapon_path = None

        for tier, name in WEAPON_TIERS.items():
            
            # Hypothetical weapon is worse than what Tuptus currently has
            if tier >= self.weapon_tier:
                continue
            
            # Tuptus knows the position of the better weapon
            if name in self.map.weapons_position.keys():
                weapon_coords = self.map.weapons_position[name]
                raw_path = self.pathfinder.astar(self.position, weapon_coords)
                weapon_path = self.pathfinder.plan_path(raw_path, self.facing) if raw_path else []

                # No reason to continue looking for a different weapon
                break
        
        return weapon_path



    
class PassiveStrategy(BaseStrategy):
    
    def hide(self):
        """
            Analyze the map for safe spots and go to the nearest one 
        """


class AggresiveStrategy(BaseStrategy):

    def fight(self):
        """
            Find the target and eliminate it (or run if will die)
        """
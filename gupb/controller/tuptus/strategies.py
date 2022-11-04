from gupb.controller.tuptus.pathfinder import Pathfinder
from gupb.controller.tuptus.tuptus import WEAPON_TIERS
from gupb.controller.tuptus.map import Map
from gupb.model.coordinates import Coords
from gupb.model.characters import Facing
from typing import Optional, List
import numpy as np

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
        
        least_explored_quadron = np.argmin(self.map.quadron_exploration, keepdims=True)
        print("EXPLORE DIDNT BREAK !")

        

        return []

    def go_to_menhir(self) -> List:
        """
            Go to menhir when the mist is approaching
        """

        if self.map.menhir_position:
            raw_path = self.pathfinder.astar(self.position, self.map.menhir_position)
            return self.pathfinder.plan_path(raw_path, self.facing)
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
                weapon_path = self.pathfinder.plan_path(raw_path, self.facing)

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
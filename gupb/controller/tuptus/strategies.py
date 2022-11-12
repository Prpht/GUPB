from gupb.controller.tuptus.map import Map
from gupb.model.arenas import Arena, ArenaDescription
from gupb.model import characters, effects, weapons
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
    6: "knife",
}
WEAPON_CLASSES = {
    "sword": weapons.Sword(),
    "axe": weapons.Axe(),
    "amulet": weapons.Amulet(),
    "bow_loaded": weapons.Bow(),
    "bow_unloaded": weapons.Bow(),
    "knife": weapons.Knife(),
}


class BaseStrategy:
    def __init__(
        self,
        game_map: Map,
        weapon_tier: int,
        position: Optional[Coords],
        facing: Optional[Facing],
    ):
        self.pathfinder: Pathfinder = Pathfinder(game_map)
        self.map: Map = game_map
        self.weapon_tier: int = weapon_tier
        self.position: Optional[Coords] = position
        self.facing: Optional[Facing] = facing
        self.closest_opponent: tuple = (None, None)
        self.arena_description: Arena

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
    def fight(self, knowledge):
        """
        Find the target and eliminate it (or run if will die)
        """
        if self.find_opponent(knowledge):
            shortest_path = -1
            good_spots = self.find_good_attacking_spot(knowledge)
            if len(good_spots) == 0:
                return None
            for idx, good_spot in enumerate(good_spots):
                if self.pathfinder.astar(knowledge.position, good_spot)!=0:
                    path = self.pathfinder.plan_path(
                        self.pathfinder.astar(knowledge.position, good_spot), self.facing
                    )
                    if len(path) < shortest_path or shortest_path==-1:
                        shortest_path = len(path)
                        chosen_path = path
                if shortest_path == -1:
                    return [characters.Action.TURN_LEFT]
            return chosen_path+[characters.Action.ATTACK]
        return None

    def find_opponent(self, knowledge):
        """
        Find the closest opponent
        """
        shortest_path = -1
        opponent = None
        for coords, tile in knowledge.visible_tiles.items():
            if tile.character and coords != knowledge.position:
                if self.pathfinder.astar(knowledge.position, coords)!= 0:
                    path = self.pathfinder.plan_path(
                        self.pathfinder.astar(knowledge.position, coords), self.facing
                    )
                    if shortest_path == -1 or len(path) < shortest_path:
                        shortest_path = len(path)
                        opponent = (coords, tile)
        if opponent:
            self.closest_opponent = opponent
            return True
        return False

    def find_good_attacking_spot(self, knowledge):
        tup_weapon = WEAPON_TIERS[self.weapon_tier]
        opponent_range = WEAPON_CLASSES[
            self.closest_opponent[1].character.weapon.name
        ].cut_positions(
            self.arena_description.terrain,
            (Coords(self.closest_opponent[0][0], self.closest_opponent[0][1])),
            self.closest_opponent[1].character.facing,
        )
        if tup_weapon in ["knife", "sword", "bow_unloaded", "bow_loaded"]:
            tup_range = WEAPON_CLASSES[
                knowledge.visible_tiles[knowledge.position].character.weapon.name
            ].reach()
            good_attacking_spots = [
                tuple(map(sum, zip(self.closest_opponent[0], (0, tup_range)))),
                tuple(map(sum, zip(self.closest_opponent[0], (0, -tup_range)))),
                tuple(map(sum, zip(self.closest_opponent[0], (-tup_range, 0)))),
                tuple(map(sum, zip(self.closest_opponent[0], (tup_range, 0)))),
            ]
        elif tup_weapon == "axe":
            good_attacking_spots = [
                tuple(map(sum, zip(self.closest_opponent[0], (1, -1)))),
                tuple(map(sum, zip(self.closest_opponent[0], (-1, 1)))),
                tuple(map(sum, zip(self.closest_opponent[0], (-1, -1)))),
                tuple(map(sum, zip(self.closest_opponent[0], (1, 1)))),
                tuple(map(sum, zip(self.closest_opponent[0], (0, 1)))),
                tuple(map(sum, zip(self.closest_opponent[0], (0, -1)))),
                tuple(map(sum, zip(self.closest_opponent[0], (-1, 0)))),
                tuple(map(sum, zip(self.closest_opponent[0], (1, 0)))),
            ]
        elif tup_weapon == "amulet":
            good_attacking_spots = [
                tuple(map(sum, zip(self.closest_opponent[0], (2, -2)))),
                tuple(map(sum, zip(self.closest_opponent[0], (-2, 2)))),
                tuple(map(sum, zip(self.closest_opponent[0], (-2, -2)))),
                tuple(map(sum, zip(self.closest_opponent[0], (2, 2)))),
            ]
        good_attacking_spots = [
            x for x in good_attacking_spots if x not in opponent_range
        ]
        return good_attacking_spots

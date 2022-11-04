from gupb.controller.tuptus.map import Map
from gupb.controller.tuptus.pathfinder import Pathfinder
from gupb.model.arenas import Arena, ArenaDescription
from gupb.model import characters, effects, weapons
from typing import Optional, List


class BaseStrategy:
    def __init__(self):
        self.pathfinder: Pathfinder = Pathfinder(self.map)
        self.map: Map = Map()
        self.facing: Optional[characters.Facing] = None
        self.closest_opponent: tuple = (None, None)
        self.arena_description: ArenaDescription
        self.weapon_tier: int

    def explore(self):
        """
        Fancy name for wandering around...

        Store information about seen parts of the map and go towards the unexplored?
        """
        pass

    def go_to_menhir(self):
        """
        Go to menhir when the mist is approaching
        """


class PassiveStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()

    def hide(self):
        """
        Analyze the map for safe spots and go to the nearest one
        """


class AggresiveStrategy(BaseStrategy):
    def __init__(self):
        super().__init__()

    def fight(self, knowledge):
        """
        Find the target and eliminate it (or run if will die)
        """
        if self.find_opponent(knowledge):
            good_spots = self.find_good_attacking_spot(knowledge)
            if len(good_spots) == 0:
                return None
            for idx, good_spot in enumerate(good_spots):
                path = self.pathfinder.plan_path(
                    self.pathfinder.astar(knowledge.position, good_spot), self.facing
                )
                if idx == 0:
                    shortest_path = len(path)
                    chosen_path = path
                elif len(path) < shortest_path:
                    shortest_path = len(path)
                    chosen_path = path
        return chosen_path

    def find_opponent(self, knowledge):
        """
        Find the closest opponent
        """
        shortest_path = -1
        opponent = None
        for coords, tile in knowledge.visible_tiles.items:
            if tile.character and coords != knowledge.position:
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
        tup_weapon = WEAPON_TIER[self.weapon_tier]
        opponent_range = self.closest_opponent[1].weapon.cut_postions(
            self.arena_description.terrain,
            self.closest_opponent[1].position,
            self.closest_opponent[1].facing,
        )
        if tup_weapon in ["knife", "sword", "bow"]:
            tup_range = knowledge.visible_tiles[knowledge.position][1].weapon.range
            good_attacking_spots = [
                self.closest_opponent[0] + (0, tup_range),
                self.closest_opponent[0] + (0, -tup_range),
                self.closest_opponent[0] + (-tup_range, 0),
                self.closest_opponent[0] + (tup_range, 0),
            ]
        elif tup_weapon == "axe":
            good_attacking_spots = [
                self.closest_opponent[0] + (1, -1),
                self.closest_opponent[0] + (-1, 1),
                self.closest_opponent[0] + (-1, -1),
                self.closest_opponent[0] + (1, 1),
                self.closest_opponent[0] + (0, 1),
                self.closest_opponent[0] + (0, -1),
                self.closest_opponent[0] + (-1, 0),
                self.closest_opponent[0] + (1, 0),
            ]
        elif tup_weapon == "amulet":
            good_attacking_spots = [
                self.closest_opponent[0] + (2, -2),
                self.closest_opponent[0] + (-2, 2),
                self.closest_opponent[0] + (-2, -2),
                self.closest_opponent[0] + (2, 2),
            ]
        good_attacking_spots = [
            x for x in good_attacking_spots if x not in opponent_range
        ]
        return good_attacking_spots

from gupb.model.arenas import Arena
from gupb.model import coordinates
from gupb.controller.pirat.pathfinding import PathFinder
from typing import Optional
import math

weapons = {"sword", "axe", "amulet", "bow_unloaded", "scroll"}

class WeaponDecider:
    def __init__(self, arena: Arena, max_tiles_for_weapon: dict[str, int] = None):
        self.weapons : dict[str, coordinates.Coords] = {weapon: [] for weapon in weapons}

        self.actualize_weapons(arena)
        self.max_tiles_for_weapon = max_tiles_for_weapon
        if max_tiles_for_weapon is None:
            self.max_tiles_for_weapon = {"sword": 4, "axe": 6, "amulet": 6, "bow_unloaded": 0 , "scroll": 6}

    def actualize_weapons(self, arena: Arena):
        for coord in arena.terrain:
            tile = arena.terrain[coord]
            loot = tile.loot
            if loot is not None:
                self.weapons[loot.description().name] += [coord]

    def check_if_need_to_go(self, start, path_finder: PathFinder) -> [coordinates]: 
        best_route = []
        for weapon in self.weapons:
            for coord in self.weapons[weapon]:
                path = path_finder.find_the_shortest_path(start, coord)
                len_of_path = len(path)
                if len_of_path <= self.max_tiles_for_weapon[weapon] and (len_of_path < len(best_route) or len(best_route) == 0):
                    best_route = path

        return best_route
    

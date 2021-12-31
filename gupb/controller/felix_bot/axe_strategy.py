import random
import math
import time
from gupb.model import coordinates, tiles
from typing import Dict
from .astar import Astar
from gupb.model.coordinates import Coords
from gupb.model.tiles import TileDescription
import random
from gupb.model.weapons import WeaponDescription

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from .strategy import Strategy


class AxeStrategy(Strategy):
    def __init__(self):
        super().__init__()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.refresh_info(knowledge)

        if self.can_attack(knowledge.visible_tiles) or self.should_reload():
            return characters.Action.ATTACK

        if len(self.action_queue) == 0:
            if self.current_weapon not in ['axe']:
                weapon_coord = self.get_weapon_coordinate(['axe'])
                if weapon_coord is not None and weapon_coord not in self.banned_coords:
                    path = Astar.astar(self.grid, self.position, weapon_coord)
                    if path is not None:
                        self.action_queue = self.generate_queue_from_path(
                            path)
                        if len(self.action_queue) > 0:
                            return self.action_queue.pop(0)
                        else:
                            return self.random_action_choice()
                    else:
                        self.banned_coords.append(weapon_coord)

            if self.menhir_coord is None or (self.current_weapon not in ['axe'] and not self.is_mist_coming):
                random_coord = self.get_random_passable_coord()
                path = Astar.astar(self.grid, self.position, random_coord)
                if path is not None:
                    self.action_queue = self.generate_queue_from_path(
                        path)
            elif self.is_mist_coming and self.menhir_coord is not None:
                target_coord = self.get_coord_near_tile(self.menhir_coord)
                path = Astar.astar(self.grid, self.position, target_coord)
                if path is not None:
                    self.action_queue = self.generate_queue_from_path(
                        path)
            elif self.safe_place is None:
                self.safe_place = self.get_safe_place()
                path = Astar.astar(self.grid, self.position, self.safe_place)
                if path is not None:
                    self.action_queue = self.generate_queue_from_path(
                        path)

        self.validate_action_queue()

        if len(self.action_queue) > 0:
            return self.action_queue.pop(0)
        elif self.position == self.safe_place:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_LEFT

    def get_coord_near_tile(self, tile_coord):
        coords = []
        try:
            new_coord = coordinates.add_coords(tile_coord, Coords(1, 1))
            if self.grid[new_coord].type == 'land':
                coords.append(new_coord)
        except KeyError:
            pass
        try:
            new_coord = coordinates.add_coords(tile_coord, Coords(1, -1))
            if self.grid[new_coord].type == 'land':
                coords.append(new_coord)
        except KeyError:
            pass
        try:
            new_coord = coordinates.add_coords(tile_coord, Coords(-1, 1))
            if self.grid[new_coord].type == 'land':
                coords.append(new_coord)
        except KeyError:
            pass
        try:
            new_coord = coordinates.add_coords(tile_coord, Coords(-1, -1))
            if self.grid[new_coord].type == 'land':
                coords.append(new_coord)
        except KeyError:
            pass

        smallest_distance = 1000
        for coord in coords:
            distance = self.get_distance(coord)
            if distance < smallest_distance:
                smallest_distance = distance
                tile_coord = coord
        return tile_coord




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


class SwordStrategy(Strategy):
    def __init__(self):
        super().__init__()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.refresh_info(knowledge)

        if self.can_attack(knowledge.visible_tiles) or self.should_reload():
            return characters.Action.ATTACK

        if len(self.action_queue) == 0:
            if self.current_weapon not in ['sword']:
                weapon_coord = self.get_weapon_coordinate(['sword'])
                if weapon_coord is not None and weapon_coord not in self.banned_coords:
                    path = Astar.astar(self.grid, self.position, weapon_coord)
                    if path is not None:
                        self.path = path
                        self.action_queue = self.generate_queue_from_path(
                            path)
                        if len(self.action_queue) > 0:
                            return self.action_queue.pop(0)
                        else:
                            return self.random_action_choice()
                    else:
                        self.banned_coords.append(weapon_coord)

            if self.menhir_coord is None or (self.current_weapon not in ['sword'] and not self.is_mist_coming):
                self.random_coord = self.get_random_passable_coord()
                path = Astar.astar(self.grid, self.position, self.random_coord)
                if path is not None:
                    self.path = path
                    self.action_queue = self.generate_queue_from_path(
                        path)
            elif self.is_mist_coming and self.menhir_coord is not None:
                target_coord = self.get_far_coord_orthogonal_to_tile(self.menhir_coord, 4)
                path = Astar.astar(self.grid, self.position, target_coord, avoid_enemies=False)
                if path is not None:
                    self.path = path
                    self.action_queue = self.generate_queue_from_path(
                        path)
            elif self.safe_place is None:
                self.safe_place = self.get_safe_place()
                path = Astar.astar(self.grid, self.position, self.safe_place)
                if path is not None:
                    self.path = path
                    self.action_queue = self.generate_queue_from_path(
                        path)

        self.validate_action_queue()

        if len(self.action_queue) > 0:
            return self.action_queue.pop(0)
        else:
            return characters.Action.TURN_LEFT

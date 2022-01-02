import random

from typing import Tuple, Optional, Dict

from .outer_utils import *
from gupb.model import characters
from gupb.model import coordinates
from gupb.model.tiles import TileDescription


class Strategy:
    """ Base class for future strategies """
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.value = 0.0
        self.n = 0
        self.current_mode = None
        self.watch_back = False

    def proceed(self, knowledge):
        """ Picks an action for the controller or changes some of its variables """
        pass

    def update_value(self, reward):
        """ Update the value of the strategy """
        self.n += 1
        self.value += (reward - self.value) / self.n

    def reset_mode(self):
        self.watch_back = False

    """ Utils """
    def check_if_mist_visible(self, visible_tiles: Dict[coordinates.Coords, TileDescription]):
        for coord, tile in visible_tiles.items():
            for e in tile.effects:
                if e.type == 'mist':
                    return True
        return False

    def get_area_of_attack(self, position, direction):
        aoa = []
        if self.controller.hold_weapon in ["knife", "sword", "bow_loaded"]:
            for i in range(LINE_WEAPONS_REACH[self.controller.hold_weapon]):
                attack_coords = position + direction.value * (i + 1)
                aoa.append(attack_coords)
        else:
            attack_coords = position + direction.value
            if self.controller.hold_weapon == "axe":
                aoa.append(attack_coords)
            for turn in [self.controller.direction.turn_left().value, self.controller.direction.turn_right().value]:
                aoa.append(attack_coords + turn)
        return aoa

    def enemy_in_reach(self, knowledge: characters.ChampionKnowledge):
        """Bot checks whether the enemy is in potential area of attack"""
        area_of_attack = self.get_area_of_attack(knowledge.position, self.controller.direction)
        # getting coordinates for visible tiles that bot can attack
        area_of_attack = list(set(area_of_attack) & set(knowledge.visible_tiles.keys()))
        for coords in area_of_attack:
            current_tile = knowledge.visible_tiles[coords]
            if current_tile.character is not None:
                return True
        return False

    def bfs_shortest_path(self, start, goal):
        """For given vertex return shortest path"""
        explored, queue = [], [[start]]
        if start == goal:
            return [start]
        while queue:
            path = queue.pop(0)
            node = path[-1]
            if node not in explored:
                neighbours = self.controller.current_graph[node]
                for neighbour in neighbours:
                    new_path = list(path)
                    new_path.append(neighbour)
                    queue.append(new_path)
                    if neighbour == goal:
                        return new_path
                explored.append(node)

    def move_to_next_step(self, start, end):
        diff = end - start
        if diff == self.controller.direction.value:
            return forward_action(self.controller, start)
        elif diff == self.controller.direction.turn_left().value:
            return left_action(self.controller)
        else:
            return right_action(self.controller)

    def move(self, position):
        if position == coordinates.Coords(*self.controller.current_path[0]):
            self.controller.current_path.pop(0)
        if len(self.controller.current_path) == 0:
            self.controller.destination = None
            return None
        next_step = coordinates.Coords(*self.controller.current_path[0])
        return self.move_to_next_step(position, next_step)

    def get_menhir_position(self):
        for coords in self.controller.tiles_memory:
            if self.controller.tiles_memory[coords].type == 'menhir':
                self.controller.destination = coords
                return True
        return False

    def return_good_weapon_coords(self, knowledge):
        for coord, tile in knowledge.visible_tiles.items():
            if (tile.loot is not None) and (WEAPONS_PRIORITIES[tile.loot.name] > WEAPONS_PRIORITIES[self.controller.hold_weapon])\
                    and (coord != knowledge.position) and ("mist" not in tile.effects):
                return coord
        return None

    def get_random_land_position(self):
        land_tiles = [coords for coords in self.controller.tiles_memory if
                      (self.controller.tiles_memory[coords].type in ["land", "menhir"]) and
                      (self.controller.tiles_memory[coords].loot is None) and
                      ("mist" not in self.controller.tiles_memory[coords].effects)]
        return random.choice(land_tiles)

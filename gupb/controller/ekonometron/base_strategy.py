import random

from typing import Tuple, Optional, Dict

from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription


class Strategy:
    """ Base class for future strategies """
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.value = 0.0
        self.n = 0

    def proceed(self, knowledge):
        """ Picks an action for the controller or changes some of its variables """
        pass

    def update_value(self, reward):
        """ Update the value of the strategy """
        self.n += 1
        self.value += (reward - self.value) / self.n

    """ Utils """
    def forward_action(self, position: coordinates.Coords, action=characters.Action.STEP_FORWARD):
        if action == characters.Action.STEP_FORWARD and self.controller.direction is not None:
            front_coords = position + self.controller.direction.value
            front_tile = self.controller.tiles_memory[front_coords]
            if front_tile.loot is not None:
                self.controller.hold_weapon = front_tile.loot.name
        return action

    def check_if_mist_visible(self, visible_tiles: Dict[coordinates.Coords, TileDescription]):
        for coord, tile in visible_tiles.items():
            for e in tile.effects:
                if e.type == 'mist':
                    return True
        return False

    def get_area_of_attack(self, position, direction):
        aoa = []
        if self.controller.hold_weapon in ["knife", "sword", "bow_loaded"]:
            for i in range(self.controller.line_weapons_reach[self.controller.hold_weapon]):
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
            return self.forward_action(start)
        elif diff == self.controller.direction.turn_left().value:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT

    def move(self, position):
        if position == coordinates.Coords(*self.controller.actual_path[0]):
            self.controller.actual_path.pop(0)
        next_step = coordinates.Coords(*self.controller.actual_path[0])
        return self.move_to_next_step(position, next_step)

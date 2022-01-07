import random

from typing import Tuple, Optional, Dict

from .base_strategy import Strategy
from .outer_utils import *
from gupb.model import characters
from gupb.model import coordinates


class TryingMyBest(Strategy):
    """ Default strategy; bot wanders over map without a goal; picks up potential weapons and attacks enemies on sight;
     if notices a mist, it goes to the menhir (if it was found earlier) """
    MODES_LIST = ["Casual", "Go to menhir"]

    def __init__(self, controller):
        super().__init__(controller, "trying_my_best")
        self.current_mode = "Casual"

    def reset_mode(self):
        super().reset_mode()
        self.current_mode = "Casual"

    def proceed(self, knowledge):
        # identify visible enemies
        if self.enemy_in_reach(knowledge):
            if self.controller.hold_weapon == "bow_loaded":
                self.controller.hold_weapon = "bow_unloaded"
            return characters.Action.ATTACK
        # if moving to menhir
        if self.current_mode == "Go to menhir":
            if self.controller.camp_init:
                return right_action(self.controller)
            if self.watch_back:
                self.watch_back = False
                return left_action(self.controller)
            if random.random() <= 0.1:
                self.watch_back = True
                return left_action(self.controller)
            next_step = self.move(knowledge.position)
            if next_step is not None:
                return next_step
            else:
                self.controller.camp_init = True
                return right_action(self.controller)
        # if we are casually 'exploring'
        else:
            # draw a path to the menhir if mist visible
            if self.check_if_mist_visible(knowledge.visible_tiles):
                menhir_found = self.get_menhir_position()
                if menhir_found:
                    self.controller.current_path = self.bfs_shortest_path(knowledge.position, self.controller.destination)
                    self.current_mode = "Go to menhir"
                    return right_action(self.controller)
            # react to a weapon on the ground
            if self.weapon_in_reach(knowledge.position):
                action = self.react_to_weapon(knowledge.position)
                if action != characters.Action.DO_NOTHING:
                    return action
            # turn if there is an obstacle in front
            if self.obstacle_in_front(knowledge.position):
                return self.take_a_turn(knowledge.position)
            # if there is nothing interesting going on, bot will move forward
            rand_gen = random.random()
            if rand_gen <= 0.9:
                return forward_action(self.controller, knowledge.position)
            else:
                return self.take_a_turn(knowledge.position)

    def weapon_in_reach(self, position: coordinates.Coords):
        """Bot checks if it is next to a potential weapon it can reach"""
        front_coords = position + self.controller.direction.value
        left_coords = position + self.controller.direction.turn_left().value
        right_coords = position + self.controller.direction.turn_right().value
        # front tile had to be inspected independently to right and left tiles because bot doesn't need to know
        # neither right or left tile to pick up a weapon that is right in front of it
        front_tile = self.controller.tiles_memory[front_coords]
        if front_tile.loot is not None:
            return True
        try:
            left_tile = self.controller.tiles_memory[left_coords]
            right_tile = self.controller.tiles_memory[right_coords]
        except KeyError:
            return False
        else:
            if left_tile.loot is not None or right_tile.loot is not None:
                return True
            return False

    def react_to_weapon(self, position: coordinates.Coords):
        """Bot picks a proper action to a weapon laying on the ground"""
        front_coords = position + self.controller.direction.value
        left_coords = position + self.controller.direction.turn_left().value
        right_coords = position + self.controller.direction.turn_right().value
        front_tile = self.controller.tiles_memory[front_coords]
        # front tile had to be inspected independently to right and left tiles because bot doesn't need to know
        # neither right or left tile to pick up a weapon that is right in front of it;
        if front_tile.loot is not None:
            if WEAPONS_PRIORITIES[front_tile.loot.name] > WEAPONS_PRIORITIES[self.controller.hold_weapon]:
                return forward_action(self.controller, position)
            else:
                if random.random() <= 0.2:
                    return forward_action(self.controller, position)
                return self.take_a_turn(position)
        try:
            left_tile = self.controller.tiles_memory[left_coords]
            right_tile = self.controller.tiles_memory[right_coords]
        except KeyError:
            return forward_action(self.controller, position)
        if left_tile.loot is not None:
            if WEAPONS_PRIORITIES[left_tile.loot.name] > WEAPONS_PRIORITIES[self.controller.hold_weapon]:
                return left_action(self.controller)
        if right_tile.loot is not None:
            if WEAPONS_PRIORITIES[right_tile.loot.name] > WEAPONS_PRIORITIES[self.controller.hold_weapon]:
                return right_action(self.controller)
        return characters.Action.DO_NOTHING

    def obstacle_in_front(self, position: coordinates.Coords):
        """Bots identifies the tile right in front of it"""
        coords_in_front = position + self.controller.direction.value
        tile_in_front = self.controller.tiles_memory[coords_in_front]
        if tile_in_front.type not in ["land", "menhir"]:
            return True
        return False

    def rand_turn(self):
        rand_gen = random.random()
        if rand_gen <= 0.5:
            return left_action(self.controller)
        else:
            return right_action(self.controller)

    def take_a_turn(self, position: coordinates.Coords):
        """Bot chooses, whether to turn left or right"""
        left_coords = position + self.controller.direction.turn_left().value
        right_coords = position + self.controller.direction.turn_right().value
        try:
            left_tile = self.controller.tiles_memory[left_coords]
            right_tile = self.controller.tiles_memory[right_coords]
        except KeyError:
            return self.rand_turn()
        else:
            if left_tile.type not in ["land", "menhir"] and right_tile.type in ["land", "menhir"]:
                return right_action(self.controller)
            elif right_tile.type not in ["land", "menhir"] and left_tile.type in ["land", "menhir"]:
                return left_action(self.controller)
            else:
                return self.rand_turn()


class LetsHide(Strategy):
    """ Defensive strategy; bot explores the map and tries to avoid conflicts; it likes to hide in specific places;
     if it has no choice, it attacks; goes to menhir when the mist is noticed """
    MODES_LIST = ["Explore", "Hide", "Go to menhir"]

    def __init__(self, controller):
        super().__init__(controller, "lets_hide")
        self.current_mode = "Explore"
        self.camping_countdown = 0

    def reset_mode(self):
        super().reset_mode()
        self.current_mode = "Explore"
        self.camping_countdown = 0

    def proceed(self, knowledge):
        # identify visible enemies
        if self.enemy_in_reach(knowledge):
            if self.controller.hold_weapon == "bow_loaded":
                self.controller.hold_weapon = "bow_unloaded"
            return characters.Action.ATTACK
        # if moving to menhir
        if self.current_mode == "Go to menhir":
            if self.controller.camp_init:
                return right_action(self.controller)
            if self.watch_back:
                self.watch_back = False
                return left_action(self.controller)
            if random.random() <= 0.1:
                self.watch_back = True
                return left_action(self.controller)
            next_step = self.move(knowledge.position)
            if next_step is not None:
                return next_step
            else:
                self.controller.camp_init = True
                return right_action(self.controller)
        elif self.current_mode == "Hide":
            # draw a path to the menhir if mist visible
            if self.check_if_mist_visible(knowledge.visible_tiles):
                menhir_found = self.get_menhir_position()
                if menhir_found:
                    self.controller.camp_init = False
                    self.controller.current_path = self.bfs_shortest_path(knowledge.position,
                                                                          self.controller.destination)
                    self.current_mode = "Go to menhir"
                    return right_action(self.controller)
            # if bot is camping
            if self.controller.camp_init:
                self.camping_countdown -= 1
                if self.camping_countdown == 0:
                    self.controller.camp_init = False
                    self.current_mode = "Explore"
                return right_action(self.controller)
            # follow the path to the camping spot
            next_step = self.move(knowledge.position)
            if next_step is not None:
                return next_step
            else:
                self.controller.camp_init = True
                self.camping_countdown = 20
                return right_action(self.controller)
        else:
            # draw a path to the menhir if mist visible
            if self.check_if_mist_visible(knowledge.visible_tiles):
                menhir_found = self.get_menhir_position()
                if menhir_found:
                    self.controller.current_path = self.bfs_shortest_path(knowledge.position, self.controller.destination)
                    self.current_mode = "Go to menhir"
                    return right_action(self.controller)
            # draw a path to the potential camping spot after seeing an enemy
            if self.check_if_enemy_in_sight(knowledge.visible_tiles):
                self.controller.destination = self.find_hiding_spot()
                self.current_mode = "Hide"
                self.controller.current_path = self.bfs_shortest_path(knowledge.position, self.controller.destination)
                return right_action(self.controller)
            else:
                if self.controller.destination is None:
                    weapon_coords = self.return_good_weapon_coords(knowledge)
                    if weapon_coords is not None:
                        self.controller.destination = weapon_coords
                    else:
                        self.controller.destination = self.get_random_land_position()
                    self.controller.current_path = self.bfs_shortest_path(knowledge.position, self.controller.destination)
                    return left_action(self.controller)
                else:
                    next_step = self.move(knowledge.position)
                    if next_step is not None:
                        return next_step
                    else:
                        return right_action(self.controller)

    def check_if_enemy_in_sight(self, visible_tiles):
        for coord, tile in visible_tiles.items():
            if (tile.character is not None) and (tile.character.controller_name != self.controller.name) and \
                    ("mist" not in tile.effects):
                return True
        return False

    def find_hiding_spot(self):
        land_tiles = [coords for coords in self.controller.tiles_memory if
                      (self.controller.tiles_memory[coords].type in ["land", "menhir"]) and
                      ("mist" not in self.controller.tiles_memory[coords].effects)]

        def at_least_two_walls(coords, tiles_memory):
            place_next_to = (coords[0] + 0, coords[1] + 1)
            place_next_to2 = (coords[0] + 1, coords[1] + 0)
            place_next_to3 = (coords[0] + 0, coords[1] - 1)
            place_next_to4 = (coords[0] - 1, coords[1] + 0)
            def_place = 0
            for place in [place_next_to, place_next_to2, place_next_to3, place_next_to4]:
                try:
                    if tiles_memory[place].type == 'wall':
                        def_place += 1
                except KeyError as err:
                    continue
            if def_place >= 2:
                return True
            return False

        random_hide = random.choice(land_tiles)
        while not at_least_two_walls(random_hide, self.controller.tiles_memory):
            random_hide = random.choice(land_tiles)
        return random_hide


class KillThemAll(Strategy):
    """ Offensive strategy; bot tries to find the best weapon and then - it goes after enemies to take them down;
     it is not concerned about finding the menhir unless the mist comes too close """
    MODES_LIST = ["Find best weapon", "Hunting", "Go to menhir"]

    def __init__(self, controller):
        super().__init__(controller, "kill_them_all")
        self.current_mode = "Find best weapon"
        self.best_weapon = None
        self.hunting_countdown = 0

    def reset_mode(self):
        super().reset_mode()
        self.current_mode = "Find best weapon"
        self.best_weapon = None
        self.hunting_countdown = 0

    def proceed(self, knowledge):
        # identify visible enemies
        if self.enemy_in_reach(knowledge):
            if self.controller.hold_weapon == "bow_loaded":
                self.controller.hold_weapon = "bow_unloaded"
            return characters.Action.ATTACK
        # if moving to menhir
        if self.current_mode == "Go to menhir":
            if self.controller.camp_init:
                return right_action(self.controller)
            if self.watch_back:
                self.watch_back = False
                return left_action(self.controller)
            if random.random() <= 0.1:
                self.watch_back = True
                return left_action(self.controller)
            next_step = self.move(knowledge.position)
            if next_step is not None:
                return next_step
            else:
                self.controller.camp_init = True
                return right_action(self.controller)
        # looking for a bow or a sword
        elif self.current_mode == "Find best weapon":
            # draw a path to the menhir if mist visible
            if self.check_if_mist_visible(knowledge.visible_tiles):
                menhir_found = self.get_menhir_position()
                if menhir_found:
                    self.controller.current_path = self.bfs_shortest_path(knowledge.position,
                                                                          self.controller.destination)
                    self.current_mode = "Go to menhir"
                    return right_action(self.controller)
            if self.controller.destination is None:
                for w in list(reversed(list(WEAPONS_PRIORITIES.keys())))[:3]:
                    if self.controller.hold_weapon == w:
                        self.current_mode = "Hunting"
                        self.hunting_countdown = 50
                        return right_action(self.controller)
                    coords_list = self.find_best_weapon(w)
                    if len(coords_list) != 0:
                        paths_lens = {}
                        for c in coords_list:
                            paths_lens[c] = self.bfs_shortest_path(knowledge.position, c)
                        self.controller.destination = min(paths_lens.items(), key=lambda x: len(x[1]))[0]
                        self.best_weapon = w
                        self.controller.current_path = paths_lens[self.controller.destination]
                        return right_action(self.controller)
                # if there are no good weapons found, bot turns into hunting mode regardless
                self.current_mode = "Hunting"
                self.hunting_countdown = 50
                return right_action(self.controller)
            else:
                if self.controller.destination in knowledge.visible_tiles:
                    if knowledge.visible_tiles[self.controller.destination].loot.name != self.best_weapon:
                        self.controller.destination = None
                        self.controller.current_path = []
                        return right_action(self.controller)
                next_step = self.move(knowledge.position)
                if next_step is not None:
                    return next_step
                else:
                    return right_action(self.controller)
        # killing everyone we see
        else:
            # draw a path to the menhir if mist visible
            if self.check_if_mist_visible(knowledge.visible_tiles):
                menhir_found = self.get_menhir_position()
                if menhir_found:
                    self.controller.current_path = self.bfs_shortest_path(knowledge.position,
                                                                          self.controller.destination)
                    self.current_mode = "Go to menhir"
                    return right_action(self.controller)
            self.hunting_countdown -= 1
            if self.hunting_countdown == 0:
                self.current_mode = "Find best weapon"
                self.controller.destination = None
                self.controller.current_path = []
                return right_action(self.controller)
            action = self.enemy_to_the_side(knowledge.position)
            if action != characters.Action.DO_NOTHING:
                return action
            if self.controller.destination is None:
                coords_list = self.find_enemies_locations()
                if len(coords_list) != 0:
                    enemies_lens = {}
                    for c in coords_list:
                        enemies_lens[c] = self.bfs_shortest_path(knowledge.position, c)
                    self.controller.destination = min(enemies_lens.items(), key=lambda x: len(x[1]))[0]
                    self.controller.current_path = enemies_lens[self.controller.destination]
                else:
                    self.controller.destination = self.get_random_land_position()
                    self.controller.current_path = self.bfs_shortest_path(knowledge.position, self.controller.destination)
                return right_action(self.controller)
            else:
                next_step = self.move(knowledge.position)
                if next_step is not None:
                    return next_step
                else:
                    return right_action(self.controller)

    def find_best_weapon(self, weapon_name):
        return [coords for coords in self.controller.tiles_memory if (self.controller.tiles_memory[coords].loot is not None)
                and (self.controller.tiles_memory[coords].loot.name == weapon_name) and ("mist" not in self.controller.tiles_memory[coords].effects)]

    def find_enemies_locations(self):
        return [coords for coords in self.controller.tiles_memory if (self.controller.tiles_memory[coords].character is not None)
                and (self.controller.tiles_memory[coords].character.controller_name != self.controller.name) and
                ("mist" not in self.controller.tiles_memory[coords].effects)]

    def enemy_to_the_side(self, position):
        """ Bots tries to remember if there were any enemies on their left or right """
        area_left = self.get_area_of_attack(position, self.controller.direction.turn_left())
        area_right = self.get_area_of_attack(position, self.controller.direction.turn_right())
        left_out_of_reach = False
        right_out_of_reach = False
        for i in range(len(area_left)):
            try:
                left_tile = self.controller.tiles_memory[area_left[i]]
            except KeyError:
                left_out_of_reach = True
            else:
                if left_tile.type == "wall":
                    left_out_of_reach = True
                if not left_out_of_reach and left_tile.character is not None:
                    if left_tile.character.controller_name != self.controller.name:
                        return left_action(self.controller)
            try:
                right_tile = self.controller.tiles_memory[area_right[i]]
            except KeyError:
                right_out_of_reach = True
            else:
                if right_tile.type == "wall":
                    right_out_of_reach = True
                if not right_out_of_reach and right_tile.character is not None:
                    if right_tile.character.controller_name != self.controller.name:
                        return right_action(self.controller)
            if left_out_of_reach and right_out_of_reach:
                break
        return characters.Action.DO_NOTHING

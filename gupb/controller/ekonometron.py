# created by Michał Kędra and Jan Proniewicz

"""
It's a bit confused but it's got a spirit
"""

import random
import numpy as np

from typing import Tuple, Optional, Dict

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription
from gupb.model.profiling import profile


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class EkonometronController(controller.Controller):
    weapons_priorities = {
        "knife": 1,
        "amulet": 2,
        "axe": 3,
        "sword": 4,
        "bow_unloaded": 5,
        "bow_loaded": 5
    }

    line_weapons_reach = {
        "knife": 1,
        "sword": 3,
        "bow_loaded": 50
    }

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        # knowledge about the direction the controller is facing
        self.starting_coords: Optional[coordinates.Coords] = None
        self.direction: Optional[Facing] = None
        self.starting_combination = [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        # bot tries to remember the tiles it has seen thus far
        self.tiles_memory: Dict[coordinates.Coords, TileDescription] = {}
        # knowledge about the weapon the bot is currently holding
        self.hold_weapon: str = "knife"
        # the mode our bot goes into after noticing the mist
        self.mist_incoming: bool = False
        self.move_to_chosen_place: bool = False
        self.actual_path: list = []
        self.menhir_position: Optional[coordinates.Coords] = None
        self.menhir_visited: bool = False
        # looking for a place to camp in
        self.move_to_hide = False
        self.camp_visited = False
        self.camp_position = False
        self.turns = 0
        self.only_attack = False
        # strategies
        # strategy1 - bot 'tries their best'; it moves however it wants, it picks up whatever weapon it can and attacks enemies in sight
        # strategy2 - bot is looking for a specific spot that is surrounded by water or wall from the three sides; when it finds it, it remains there and keeps attacking one spot
        # strategy3 - bot has a bow as a bigger priority; tries to avoid worse weapons; it checks for the enemies on the side so it can take them down faster
        self.strategy_rewards = {
            "strategy1": [],
            "strategy2": [],
            "strategy3": []
        }
        self.chosen_strategy = None
        self.initial_start_counter = 15

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EkonometronController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.starting_coords = None
        self.direction = None
        self.starting_combination = [characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD,
                                     characters.Action.TURN_RIGHT, characters.Action.STEP_FORWARD]
        self.tiles_memory = {}
        self.hold_weapon = "knife"
        self.mist_incoming = False
        self.move_to_chosen_place = False
        self.actual_path = []
        self.menhir_position = None
        self.menhir_visited = False
        self.move_to_hide = False
        self.camp_visited = False
        self.camp_position = False
        self.turns = 0
        self.only_attack = False
        # choosing the strategy
        if self.initial_start_counter != 0:
            strat_id = self.initial_start_counter % 3 + 1
            self.chosen_strategy = "strategy" + str(strat_id)
            self.initial_start_counter -= 1
        else:
            prob_1 = np.random.normal(np.mean(self.strategy_rewards["strategy1"]),
                                      np.std(self.strategy_rewards["strategy1"]))
            prob_2 = np.random.normal(np.mean(self.strategy_rewards["strategy2"]),
                                      np.std(self.strategy_rewards["strategy2"]))
            prob_3 = np.random.normal(np.mean(self.strategy_rewards["strategy3"]),
                                      np.std(self.strategy_rewards["strategy3"]))
            strat_id = np.argmax([prob_1, prob_2, prob_3]) + 1
            self.chosen_strategy = "strategy" + str(strat_id)
        #print(self.strategy_rewards)
        #print(self.chosen_strategy)

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # if bot holds an unloaded bow
        if self.hold_weapon == "bow_unloaded":
            self.hold_weapon = "bow_loaded"
            return characters.Action.ATTACK
        # update bot's memory, based on the visible tiles
        visible_tiles = knowledge.visible_tiles
        self._update_memory(visible_tiles)
        # making graph
        visible_graph = self.find_edges()
        # save menhir position if visible
        if self.menhir_position is None:
            self.save_menhir_position_if_visible(knowledge.visible_tiles)

        # when bot doesn't know which direction it is facing
        if self.starting_coords is None:
            self.starting_coords = knowledge.position
            return self._forward_action(knowledge.position)
            #return characters.Action.STEP_FORWARD
        if self.direction is None:
            if self.starting_coords != knowledge.position:
                coords_diff = knowledge.position - self.starting_coords
                if coords_diff.x != 0:
                    if coords_diff.x > 0:
                        self.direction = Facing.RIGHT
                    else:
                        self.direction = Facing.LEFT
                elif coords_diff.y > 0:
                    self.direction = Facing.DOWN
                else:
                    self.direction = Facing.UP
            else:
                return self._forward_action(knowledge.position, self.starting_combination.pop(0))
                #return self.starting_combination.pop(0)

        # when bot is aware which direction it is facing
        # identify visible enemies
        if self._enemy_in_reach(knowledge):
            if self.hold_weapon == "bow_loaded":
                self.hold_weapon = "bow_unloaded"
            return characters.Action.ATTACK

        if self.menhir_visited:
            return characters.Action.TURN_RIGHT

        # if moving to menhir
        if self.move_to_chosen_place:
            if self.move_all(knowledge.position):
                return self._forward_action(knowledge.position)
                #return characters.Action.STEP_FORWARD
            else:
                self.direction = self.direction.turn_right()
                return characters.Action.TURN_RIGHT

        # check if mist visible
        self._check_if_mist_visible(knowledge.visible_tiles)
        # if mist, init run to menhir
        if not self.move_to_chosen_place and self.mist_incoming and not self.menhir_visited:
            self.actual_path = self.bfs_shortest_path(visible_graph, knowledge.position, self.menhir_position)
            if self.actual_path:
                self.actual_path.pop(0)
                self.move_to_chosen_place = True
                if self.move_all(knowledge.position):
                    return self._forward_action(knowledge.position)
                    #return characters.Action.STEP_FORWARD
                else:
                    self.direction = self.direction.turn_right()
                    return characters.Action.TURN_RIGHT

        if self.chosen_strategy == "strategy2":
            if not self.camp_position:
                self.save_camp_position_if_visible(knowledge.visible_tiles)
            if self.move_to_hide:
                if self.move_all_hide(knowledge.position):
                    return self._forward_action(knowledge.position)
                else:
                    self.direction = self.direction.turn_right()
                    return characters.Action.TURN_RIGHT
            if not self.move_to_hide and not self.camp_visited and self.camp_position:
                self.actual_path = self.bfs_shortest_path(visible_graph, knowledge.position, self.camp_position)
                if self.actual_path:
                    self.actual_path.pop(0)
                    self.move_to_hide = True
                    if self.move_all_hide(knowledge.position):
                        return self._forward_action(knowledge.position)
                    else:
                        self.direction = self.direction.turn_right()
                        return characters.Action.TURN_RIGHT
            if self.turns > 0 and self.only_attack:
                self.turns -= 1
                self.direction = self.direction.turn_right()
                return characters.Action.TURN_RIGHT
            if self.only_attack:
                return characters.Action.ATTACK

        # if bot uses the strategy3, try to remember if there were any enemies to your side
        if self.chosen_strategy == "strategy3":
            action = self._enemy_to_the_side(knowledge.position)
            if action != characters.Action.DO_NOTHING:
                return action
        # react to a weapon on the ground
        if self._weapon_in_reach(knowledge.position):
            action = self._react_to_weapon(knowledge.position)
            if action != characters.Action.DO_NOTHING:
                return action
        # turn if there is an obstacle in front
        if self._obstacle_in_front(knowledge.position):
            return self._take_a_turn(knowledge.position)
        # if there is nothing interesting going on, bot will move forward
        rand_gen = random.random()
        if rand_gen <= 0.9:
            return self._forward_action(knowledge.position)
            #return characters.Action.STEP_FORWARD
        else:
            return self._take_a_turn(knowledge.position)

    """ Utils """
    def _forward_action(self, position: coordinates.Coords, action=characters.Action.STEP_FORWARD):
        if action == characters.Action.STEP_FORWARD and self.direction is not None:
            front_coords = position + self.direction.value
            front_tile = self.tiles_memory[front_coords]
            if front_tile.loot is not None:
                self.hold_weapon = front_tile.loot.name
        return action

    def _update_memory(self, visible_tiles: Dict[coordinates.Coords, TileDescription]):
        for coords, tile_desc in visible_tiles.items():
            self.tiles_memory[coords] = tile_desc

    def _rand_turn(self):
        rand_gen = random.random()
        if rand_gen <= 0.5:
            self.direction = self.direction.turn_left()
            return characters.Action.TURN_LEFT
        else:
            self.direction = self.direction.turn_right()
            return characters.Action.TURN_RIGHT

    def _take_a_turn(self, position: coordinates.Coords):
        """Bot chooses, whether to turn left or right"""
        left_coords = position + self.direction.turn_left().value
        right_coords = position + self.direction.turn_right().value
        try:
            left_tile = self.tiles_memory[left_coords]
            right_tile = self.tiles_memory[right_coords]
        except KeyError:
            return self._rand_turn()
        else:
            if left_tile.type not in ["land", "menhir"] and right_tile.type in ["land", "menhir"]:
                self.direction = self.direction.turn_right()
                return characters.Action.TURN_RIGHT
            elif right_tile.type not in ["land", "menhir"] and left_tile.type in ["land", "menhir"]:
                self.direction = self.direction.turn_left()
                return characters.Action.TURN_LEFT
            else:
                return self._rand_turn()

    def _obstacle_in_front(self, position: coordinates.Coords):
        """Bots identifies the tile right in front of it"""
        coords_in_front = position + self.direction.value
        tile_in_front = self.tiles_memory[coords_in_front]
        if tile_in_front.type not in ["land", "menhir"]:
            return True
        return False

    def _check_if_mist_visible(self, visible_tiles: Dict[coordinates.Coords, TileDescription]):
        for coord, tile in visible_tiles.items():
            for e in tile.effects:
                if e.type == 'mist':
                    self.mist_incoming = True

    def _weapon_in_reach(self, position: coordinates.Coords):
        """Bot checks if it is next to a potential weapon it can reach"""
        front_coords = position + self.direction.value
        left_coords = position + self.direction.turn_left().value
        right_coords = position + self.direction.turn_right().value
        # front tile had to be inspected independently to right and left tiles because bot doesn't need to know
        # neither right or left tile to pick up a weapon that is right in front of it
        front_tile = self.tiles_memory[front_coords]
        if front_tile.loot is not None:
            return True
        try:
            left_tile = self.tiles_memory[left_coords]
            right_tile = self.tiles_memory[right_coords]
        except KeyError:
            return False
        else:
            if left_tile.loot is not None or right_tile.loot is not None:
                return True
            return False

    def _react_to_weapon(self, position: coordinates.Coords):
        """Bot picks a proper action to a weapon laying on the ground"""
        front_coords = position + self.direction.value
        left_coords = position + self.direction.turn_left().value
        right_coords = position + self.direction.turn_right().value
        front_tile = self.tiles_memory[front_coords]
        # front tile had to be inspected independently to right and left tiles because bot doesn't need to know
        # neither right or left tile to pick up a weapon that is right in front of it;
        if front_tile.loot is not None:
            if self.weapons_priorities[front_tile.loot.name] > self.weapons_priorities[self.hold_weapon]:
                self.hold_weapon = front_tile.loot.name
                return characters.Action.STEP_FORWARD
            else:
                if self.chosen_strategy != "strategy1":
                    return self._take_a_turn(position)
        try:
            left_tile = self.tiles_memory[left_coords]
            right_tile = self.tiles_memory[right_coords]
        except KeyError:
            if front_tile.loot is not None:
                self.hold_weapon = front_tile.loot.name
            return characters.Action.STEP_FORWARD
        if left_tile.loot is not None:
            if self.weapons_priorities[left_tile.loot.name] > self.weapons_priorities[self.hold_weapon]:
                self.direction = self.direction.turn_left()
                return characters.Action.TURN_LEFT
        if right_tile.loot is not None:
            if self.weapons_priorities[right_tile.loot.name] > self.weapons_priorities[self.hold_weapon]:
                self.direction = self.direction.turn_right()
                return characters.Action.TURN_RIGHT
        return characters.Action.DO_NOTHING

    """ Think about aggro """
    def get_area_of_attack(self, position, direction):
        aoa = []
        if self.hold_weapon in ["knife", "sword", "bow_loaded"]:
            for i in range(self.line_weapons_reach[self.hold_weapon]):
                attack_coords = position + direction.value * (i + 1)
                aoa.append(attack_coords)
        else:
            attack_coords = position + direction.value
            if self.hold_weapon == "axe":
                aoa.append(attack_coords)
            for turn in [self.direction.turn_left().value, self.direction.turn_right().value]:
                aoa.append(attack_coords + turn)
        return aoa

    def _enemy_to_the_side(self, position):
        """ Bots tries to remember if there were any enemies on their left or right """
        area_left = self.get_area_of_attack(position, self.direction.turn_left())
        area_right = self.get_area_of_attack(position, self.direction.turn_right())
        left_out_of_reach = False
        right_out_of_reach = False
        for i in range(len(area_left)):
            try:
                left_tile = self.tiles_memory[area_left[i]]
            except KeyError:
                left_out_of_reach = True
            else:
                if left_tile.type == "wall":
                    left_out_of_reach = True
                if not left_out_of_reach and left_tile.character is not None:
                    if left_tile.character.controller_name != self.name:
                        self.direction = self.direction.turn_left()
                        return characters.Action.TURN_LEFT
            try:
                right_tile = self.tiles_memory[area_right[i]]
            except KeyError:
                right_out_of_reach = True
            else:
                if right_tile.type == "wall":
                    right_out_of_reach = True
                if not right_out_of_reach and right_tile.character is not None:
                    if right_tile.character.controller_name != self.name:
                        self.direction = self.direction.turn_right()
                        return characters.Action.TURN_RIGHT
            if left_out_of_reach and right_out_of_reach:
                break
        return characters.Action.DO_NOTHING

    def _enemy_in_reach(self, knowledge: characters.ChampionKnowledge):
        """Bot checks whether the enemy is in potential area of attack"""
        area_of_attack = self.get_area_of_attack(knowledge.position, self.direction)
        # getting coordinates for visible tiles that bot can attack
        area_of_attack = list(set(area_of_attack) & set(knowledge.visible_tiles.keys()))
        for coords in area_of_attack:
            current_tile = knowledge.visible_tiles[coords]
            if current_tile.character is not None:
                return True
        return False

    def find_edges(self):
        """Finding edges for vertexes"""
        vertexes = []
        for coord, tile in self.tiles_memory.items():
            if tile.type == 'land' or tile.type == 'menhir':
                vertexes.append(coord)

        vertexes_edges = {}

        def check_if_next_to(vertex1, vertex2):
            if vertex1[0] == vertex2[0]:
                if (vertex1[1] - 1 == vertex2[1]) or (vertex1[1] + 1 == vertex2[1]):
                    return True
            elif vertex1[1] == vertex2[1]:
                if (vertex1[0] - 1 == vertex2[0]) or (vertex1[0] + 1 == vertex2[0]):
                    return True
            return False

        for ver in vertexes:
            vertex_edges = []
            for ver2 in vertexes:
                if ver != ver2 and check_if_next_to(ver, ver2):
                    vertex_edges.append(ver2)
            vertexes_edges[ver] = vertex_edges

        return vertexes_edges

    def bfs_shortest_path(self, graph, start, goal):
        """For given vertex return shortest path"""
        explored, queue = [], [[start]]
        if start == goal:
            return False
        while queue:
            path = queue.pop(0)
            node = path[-1]
            if node not in explored:
                neighbours = graph[node]
                for neighbour in neighbours:
                    new_path = list(path)
                    new_path.append(neighbour)
                    queue.append(new_path)
                    if neighbour == goal:
                        return new_path
                explored.append(node)
        # no connection
        return False

    def move(self, start, end):
        diff = end - start
        if start != end:
            if diff.x == 1:
                if self.direction == Facing.RIGHT:
                    # return True mean he should go forward
                    return True
            elif diff.x == -1:
                if self.direction == Facing.LEFT:
                    return True
            elif diff.y == 1:
                if self.direction == Facing.DOWN:
                    return True
            elif diff.y == -1:
                if self.direction == Facing.UP:
                    return True
        return False

    def move_all(self, position):
        if position == coordinates.Coords(*self.actual_path[0]):
            self.actual_path.pop(0)
        actual_path_0 = coordinates.Coords(*self.actual_path[0])
        if self.move(position, actual_path_0):
            if len(self.actual_path) == 1:
                self.menhir_visited = True
                self.move_to_chosen_place = False
            return True
        else:
            return False

    def save_menhir_position_if_visible(self, visible_coords):
        for v_coord in visible_coords:
            if visible_coords[v_coord].type == 'menhir':
                self.menhir_position = v_coord
                break

    def move_all_hide(self, position):
        if position == coordinates.Coords(*self.actual_path[0]):
            self.actual_path.pop(0)
        actual_path_0 = coordinates.Coords(*self.actual_path[0])
        if self.move(position, actual_path_0):
            if len(self.actual_path) == 1:
                self.move_to_hide = False
                self.camp_visited = True
                self.turns = 2
                self.only_attack = True
                self.actual_path = []
            return True
        else:
            return False

    def save_camp_position_if_visible(self, visible_coords):
        for v_coord in visible_coords:
            if visible_coords[v_coord].type == 'land':
                place_next_to = (v_coord[0] + 0, v_coord[1] + 1)
                place_next_to2 = (v_coord[0] + 1, v_coord[1] + 0)
                place_next_to3 = (v_coord[0] + 0, v_coord[1] - 1)
                place_next_to4 = (v_coord[0] - 1, v_coord[1] + 0)
                def_place = 0
                for place in [place_next_to, place_next_to2, place_next_to3, place_next_to4]:
                    try:
                        if self.tiles_memory[place].type != 'land':
                            def_place += 1
                    except KeyError as err:
                        pass
                if def_place == 3:
                    self.camp_position = v_coord
                    break

    @property
    def name(self) -> str:
        return f'EkonometronController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN

    def praise(self, score: int) -> None:
        self.strategy_rewards[self.chosen_strategy].append(score)


POTENTIAL_CONTROLLERS = [
    EkonometronController("Johnathan"),
]

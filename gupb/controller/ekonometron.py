# created by Michał Kędra and Jan Proniewicz

"""
It's a bit confused but it's got a spirit
"""

import random

from typing import Tuple, Optional, Dict

from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class EkonometronController:
    line_weapons_reach = {
        "knife": 1,
        "sword": 3,
        "bow_loaded": 50
    }

    weapons_priorities = {
        "knife": 1,
        "amulet": 2,
        "axe": 3,
        "sword": 4,
        "bow_unloaded": 5,
        "bow_loaded": 5
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
            self.actual_path.pop(0)
            if self.actual_path:
                self.move_to_chosen_place = True
                if self.move_all(knowledge.position):
                    return self._forward_action(knowledge.position)
                    #return characters.Action.STEP_FORWARD
                else:
                    self.direction = self.direction.turn_right()
                    return characters.Action.TURN_RIGHT

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
        if rand_gen <= 0.75:
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

    """ Think about weapons priorities """
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
    def _enemy_in_reach(self, knowledge: characters.ChampionKnowledge):
        """Bot checks whether the enemy is in potential area of attack"""

        def get_area_of_attack():
            aoa = []
            if self.hold_weapon in ["knife", "sword", "bow_loaded"]:
                for i in range(self.line_weapons_reach[self.hold_weapon]):
                    attack_coords = knowledge.position + self.direction.value * (i + 1)
                    aoa.append(attack_coords)
            else:
                attack_coords = knowledge.position + self.direction.value
                for turn in [self.direction.turn_left().value, self.direction.turn_right().value]:
                    aoa.append(attack_coords + turn)
                if self.hold_weapon == "axe":
                    aoa.append(attack_coords)
            return aoa

        area_of_attack = get_area_of_attack()
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

    @property
    def name(self) -> str:
        return f'EkonometronController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN


POTENTIAL_CONTROLLERS = [
    EkonometronController("Johnathan"),
]

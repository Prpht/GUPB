import random
import numpy as np
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena

from gupb.model.characters import Facing
from gupb.model import coordinates

HIDING_SPOTS = [(7, 11), (11, 7)]
WEAPON_SPOTS = [(3, 3), (15, 3), (3, 15)]


class ShrekController:
    def __init__(self, first_name: str):
        self.tactic = 1
        self.first_name: str = first_name
        self.position = None
        self.facing = None
        self.current_map_knowledge = {}
        self.weapon_name = 'knife'
        self.panic_moves = []
        self.path = []
        self.map = self.load_map('lone_sanctum')
        self.flag = True
        self.goal = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ShrekController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.position = None
        self.facing = None
        self.current_map_knowledge = {}
        self.weapon_name = 'knife'
        self.goal = (9, 9)
        self.flag = True
        self.panic_moves = False
        self.path = []
        self.tactic = 1

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.position = knowledge.position
        info = knowledge.visible_tiles[self.position].character
        self.facing = info.facing
        self.weapon_name = info.weapon.name
        if self.is_enemy_around(knowledge):
            facing_tile = self.position + self.facing.value  # if we face character we fight
            if knowledge.visible_tiles[facing_tile].character:
                return characters.Action.ATTACK
            if self.weapon_name == 'sword':  # if we have sword we fight the characters if they are 3 tiles in front of us
                facing_tile2 = facing_tile + self.facing.value
                facing_tile3 = facing_tile2 + self.facing.value
                if facing_tile2 in knowledge.visible_tiles:
                    if knowledge.visible_tiles[facing_tile2].character:
                        return characters.Action.ATTACK
                if facing_tile3 in knowledge.visible_tiles:
                    if knowledge.visible_tiles[facing_tile3].character:
                        return characters.Action.ATTACK

        if self.am_i_on_goal():
            self.find_better_weapon(knowledge)
            if not self.path:
                self.goal = HIDING_SPOTS[0]
                self.path = self.find_path(self.goal)
            if not self.path:
                self.hide()

        if self.flag:
            self.set_goal(knowledge)
            self.flag = False

        if self.path:
            wanted_field = coordinates.Coords(self.path[0][0], self.path[0][1])
            substract_points = coordinates.sub_coords(wanted_field, self.position)
            needed_facing = Facing(substract_points)
            if self.facing == needed_facing:
                self.path.pop(0)
                # check 3 fields next to goal if someone is there:
                if len(self.path) == 2:
                    if self.wanted_position_is_occupied(knowledge, self.goal):
                        if not self.wanted_position_is_occupied(knowledge, HIDING_SPOTS[0]):
                            self.goal = HIDING_SPOTS[0]
                            self.flag = True

                return characters.Action.STEP_FORWARD
            else:
                return characters.Action.TURN_RIGHT

        # if self.path_blocked(knowledge):
        #         return self.make_a_turn()
        # else:
        #     return self.move()

        # if self.mist_comes(knowledge):
        #     self.path = []
        #     res = self.find_path((9,9))
        #     self.flag = False

        # if self.next_moves:
        #     return self.next_moves.pop(0)

        # # later:
        # # TODO if mnist coming : RUN in right direction - create list of direction to remember where to go - for now it only turns in other direction
        # # TODO weapon around, get it has to be better the knife
        # # TODO go after enemy
        # # TODO remember next step for some strategy
        # # TODO remember direction -> not go back

        # if self.is_enemy_around(knowledge):
        #     if info.health >= characters.CHAMPION_STARTING_HP * 0.5:
        #         facing_tile = self.position + self.facing.value
        #         if knowledge.visible_tiles[facing_tile].character:
        #             return characters.Action.ATTACK
        #     else:
        #         return characters.Action.STEP_FORWARD

    def wanted_position_is_occupied(self, knowledge: characters.ChampionKnowledge, goal):

        for coordinate, tile_descr in knowledge.visible_tiles.items():
            x = coordinate[0]
            y = coordinate[1]
            if tile_descr.character and x == goal[0] and y == goal[1]:
                return True
        return False

    def am_i_on_goal(self):
        cords = coordinates.Coords(self.goal[0], self.goal[1])

        if self.position.x == cords.x and self.position.y == cords.y:
            return True
        return False

    def path_blocked(self, knowledge: characters.ChampionKnowledge):
        """
        Check if there is an obstacle blocking the path (Sea or Wall)
        """
        facing_tile = self.position + self.facing.value
        if knowledge.visible_tiles[facing_tile].type != 'land':
            return True

        return False

    def mist_comes(self, knowledge: characters.ChampionKnowledge):
        """
        Check if there is mist nearby
        """
        facing_tile = self.position + self.facing.value
        for effect in knowledge.visible_tiles[facing_tile].effects:
            if effect.type == 'mist':
                return True
        return False

    def make_a_turn(self):
        """
        Make a random turn right or left
        """
        POSSIBLE_TURNS = [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
        return random.choice(POSSIBLE_TURNS)

    def move(self):
        """
        Take a step forward, or turn
        """
        rand_num = random.random()
        if rand_num <= 0.8:
            return characters.Action.STEP_FORWARD
        elif rand_num > 0.8 and rand_num <= 0.9:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT

    def is_enemy_around(self, knowledge: characters.ChampionKnowledge):
        """
        Check if any enemies in sight
        """
        for coord, tile_descr in knowledge.visible_tiles.items():
            if tile_descr.character and coord != (self.position.x, self.position.y):
                return True
        return False

    def load_map(self, map_name):
        arena = Arena.load(map_name)
        map_matrix = [[1 for x in range(arena.size[0])] for y in range(arena.size[1])]
        for cords, tile in arena.terrain.items():
            map_matrix[cords.y][cords.x] = 0 if tile.description().type in ['wall', 'sea'] else 1
            if tile.description().loot:
                map_matrix[cords.x][cords.y] = 0 if tile.description().loot.name in ["knife", "amulet", "bow"] else 1
        return map_matrix

    def find_path(self, destination):
        grid = Grid(matrix=self.map)
        start = grid.node(self.position[0], self.position[1])
        end = grid.node(destination[0], destination[1])
        finder = AStarFinder()
        path, runs = finder.find_path(start, end, grid)
        if len(path) > 0:
            path.pop(0)
        return path

    def learn_the_terrain(self, visible_tiles, position):
        """
        For now it only learns the path to menhir
        """
        bigest_x = 0
        bigest_y = 0
        menhir = []
        for coordinate, tile_descr in visible_tiles.items():
            if coordinate[0] > bigest_x:
                bigest_x = coordinate[0]
            if coordinate[1] > bigest_y:
                bigest_y = coordinate[1]
        mat = np.zeros((bigest_y + 2, bigest_x + 2))
        interesting_objects = {}
        for coordinate, tile_descr in visible_tiles.items():
            x = coordinate[0]
            y = coordinate[1]
            if tile_descr.type == 'land' and tile_descr.effects == []:
                mat[y][x] = 1
            if tile_descr.type == 'menhir':
                mat[y][x] = 1
                menhir = coordinate
                interesting_objects[tile_descr.type] = coordinate

        grid = Grid(matrix=mat)
        start = grid.node(position[0], position[1])
        end = 0
        if menhir:
            end = grid.node(menhir[0], menhir[1])
        if end != 0:
            finder = AStarFinder()
            path, runs = finder.find_path(start, end, grid)
            if len(path) > 1:
                path.pop(0)
            self.path = path

    def weapon_value(self, weapon):
        if weapon == 'knife':
            return 1
        elif weapon == 'amulet':
            return 0
        elif weapon == 'sword':
            return 4
        elif weapon == 'axe':
            return 2
        elif weapon == 'bow_unloaded' or weapon == 'bow_loaded' or weapon == 'bow':
            return 3
        else:
            return 0

    def set_goal(self, knowledge: characters.ChampionKnowledge):
        if (self.position.x<4 and self.position.y<4) or (self.position.x < 4 and self.position.y>14) or (self.position.x>14 and self.position.y <4):
            self.find_better_weapon(knowledge)
        for spot in WEAPON_SPOTS:
            if len(self.find_path(spot)) <= len(self.find_path(self.goal)) or self.find_path(spot) == []:
                self.goal = spot
        self.path = self.find_path(self.goal)

    def find_better_weapon(self, knowledge: characters.ChampionKnowledge):
        shortest_path = 100
        for coords, tile_desc in knowledge.visible_tiles.items():
            if tile_desc.loot:
                if self.weapon_value(tile_desc.loot.name) > self.weapon_value(self.weapon_name) and not self.mist_comes(knowledge) and not self.is_near_menhir():
                    path = self.find_path(coords)
                    if len(path) < shortest_path:
                        self.path = path
                        self.goal = (coords[0], coords[1])
                        shortest_path = len(path)

    def hide(self):
        if self.position.x != 7 and self.position.y != 11:
            self.goal = HIDING_SPOTS[0]
            self.path = self.find_path(self.goal)
        else:
            self.goal = HIDING_SPOTS[1]
            self.path = self.find_path(self.goal)

    def is_near_menhir(self):
        if len(self.find_path((9, 9))) < 7:
            return True
        return False

    @property
    def name(self) -> str:
        return f'ShrekController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BROWN


POTENTIAL_CONTROLLERS = [
    ShrekController("Fiona"),
]

from math import atan2

import numpy as np
from pathfinding.core.grid import Grid

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.controller.berserk.knowledge_decoder import KnowledgeDecoder

from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from collections import deque
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.controller.berserk.utilities import distance
from gupb.model.weapons import *
from gupb.model.arenas import Arena

WEAPONS = {
    "bow": Bow(),
    "bow_unloaded": Bow(),
    "bow_loaded": Bow(),
    "axe": Axe(),
    "sword": Sword(),
    "knife": Knife(),
    "amulet": Amulet(),
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BerserkBot(controller.Controller):
    G_T_F_O_A_F_A_P = 220

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.knowledge_decoder = KnowledgeDecoder()
        self._possible_actions = [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.ATTACK,
        ]
        self.probabilities = [0.1, 0.1, 0.8, 0]
        self.move_counter = 0
        self.path = deque()
        self.picked_up_weapon = 0
        self.goal = coordinates.Coords(100, 100)
        self.position_history = list()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BerserkBot):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.knowledge_decoder.map = self.knowledge_decoder.load_map(arena_description.name)
        self.probabilities = [0.1, 0.1, 0.8, 0]
        self.move_counter = 0
        self.path = deque()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.knowledge_decoder.knowledge = knowledge
        self.position_history.append(knowledge.position)
        self.is_goal_reached()
        self.is_moving()

        if self.move_counter > self.G_T_F_O_A_F_A_P:
            self.find_menhir()
            move = self.parse_path()

        elif self.can_attack():
            move = characters.Action.ATTACK

        elif self.move_counter <= 2:
            move = self.look_around()

        elif self.picked_up_weapon == 0 and self.knowledge_decoder.info['weapons_in_sight']:
            self.find_weapon()
            move = self.parse_path()

        elif self.path:
            move = self.parse_path()

        elif self.knowledge_decoder.info['enemies_in_sight']:
            self.find_enemy()
            move = self.parse_path()
        else:
            move = self.walk_around()
        self.move_counter += 1
        return move

    @property
    def name(self) -> str:
        return f'BerserkBot{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

    def find_path(self, start, goal):
        grid = Grid(matrix=self.knowledge_decoder.map)
        start = grid.node(start.x, start.y)
        goal = grid.node(goal.x, goal.y)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)

        path, runs = finder.find_path(start, goal, grid)
        self.path.extend(path[1:])

    def parse_path(self):
        facing = self.knowledge_decoder.info['facing']
        position = self.knowledge_decoder.knowledge.position
        target = self.path[0]

        target = coordinates.Coords(target[0], target[1])

        cords_sub = coordinates.sub_coords(target, position)
        sub_max = max([abs(cords_sub.x), abs(cords_sub.y)])
        if sub_max == 0:
            print("T: ", target, " P: ", position)
            print(self.path)

        cords_facing = coordinates.Coords(cords_sub.x/sub_max, cords_sub.y/sub_max)
        # print('Cords_for_facing: ', cords_facing)

        needed_facing = Facing(cords_facing)

        if facing == needed_facing:
            self.path.popleft()
            return characters.Action.STEP_FORWARD
        else:
            # cords_dict = {
            #     Facing.UP: coordinates.Coords(0, -1),
            #     Facing.DOWN: coordinates.Coords(0, 1),
            #     Facing.RIGHT: coordinates.Coords(1, 0),
            #     Facing.LEFT: coordinates.Coords(-1, 0),
            # }
            # angle = atan2(cords_dict.get(facing, coordinates.Coords(0, 0))) - atan2(target.y - position.y, target.x - position.x)
            #
            # if angle > 0:
            #     return characters.Action.TURN_LEFT
            # else:
            return characters.Action.TURN_RIGHT

    def look_around(self):
        return characters.Action.TURN_RIGHT

    def walk_around(self):
        return np.random.choice(self._possible_actions, 1, self.probabilities)[0]

    def choose_shorter_dist(self, list_of_objects):
        position = self.knowledge_decoder.knowledge.position
        distances = [distance(position, object_pos) for object_pos in list_of_objects]
        return list_of_objects[np.argmin(distances)]

    def find_weapon(self):
        # print("find weapon")
        self.picked_up_weapon = 1
        weapon_cords = self.choose_shorter_dist(self.knowledge_decoder.info['weapons_in_sight'])
        position = self.knowledge_decoder.knowledge.position
        self.find_path(position, weapon_cords)
        self.goal = weapon_cords

    def find_enemy(self):

        enemy_cords = self.choose_shorter_dist(self.knowledge_decoder.info['enemies_in_sight'])
        position = self.knowledge_decoder.knowledge.position

        self.find_path(position, enemy_cords)
        # del self.path[-1]
        self.goal = coordinates.Coords(self.path[-1][0], self.path[-1][1])

    def find_menhir(self):
        menhir_coords = self.knowledge_decoder.info['menhir_position']
        position = self.knowledge_decoder.knowledge.position
        self.find_path(position, menhir_coords)
        self.goal = menhir_coords

    def can_attack(self):
        bot_weapon = self.knowledge_decoder.info['weapon']
        bot_coords = self.knowledge_decoder.knowledge.position
        bot_facing = self.knowledge_decoder.info['facing']
        knowledge = self.knowledge_decoder.knowledge
        if bot_weapon == 'bow_unloaded':
            return True
        can_attack_enemy = any(
            coord
            for coord in
            WEAPONS[bot_weapon].cut_positions(self.knowledge_decoder.arena.terrain, bot_coords, bot_facing)
            if coord in knowledge.visible_tiles and knowledge.visible_tiles[coord].character
        )
        return can_attack_enemy

    def runaway_from_mist(self):
        pass

    def is_goal_reached(self):
        if self.knowledge_decoder.knowledge.position.x == self.goal.x and self.knowledge_decoder.knowledge.position.y == self.goal.y:
            self.path = deque()

    def is_moving(self):
        if self.is_the_same_position():
            self.path = deque()
            self.position_history = []

    def is_the_same_position(self, past: int = 5):
        current_position = self.knowledge_decoder.knowledge.position
        if len(self.position_history) > past + 1:
            four_moves = self.position_history[-past]
        else:
            return False
        if four_moves.x == current_position.x and four_moves.y == current_position.y:
            return True
        return False

import numpy as np

from pathfinding.core.grid import Grid
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder

from collections import deque
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.controller.berserk.utilities import distance
from gupb.model.weapons import *
from gupb.model.arenas import Arena
from gupb.controller.bb8.strategy import ROTATIONS


WEAPONS = {
    "bow": Bow(),
    "bow_unloaded": Bow(),
    "bow_loaded": Bow(),
    "axe": Axe(),
    "sword": Sword(),
    "knife": Knife(),
    "amulet": Amulet(),
}

WEAPONS_VALUE = {
    "bow": 20,
    "bow_unloaded": 20,
    "bow_loaded": 20,
    "axe": 15,
    "sword": 10,
    "knife": 1,
    "amulet": 15,
}

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Strategy:
    def __init__(self, knowledge_decoder):
        self.knowledge_decoder = knowledge_decoder
        self.path = deque()
        self.important_moves = deque()
        self.goal = coordinates.Coords(100, 100)
        self.position_history = list()
        self.walk_around_probabilities = [0.1, 0.1, 0.8, 0]

    def pick_action(self):
        pass

    def find_path(self, start, goal):
        grid = Grid(matrix=self.knowledge_decoder.map)
        start = grid.node(start.x, start.y)
        goal = grid.node(goal.x, goal.y)
        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)

        path, runs = finder.find_path(start, goal, grid)
        if path:
            self.path.extend(path[1:])
        else:
            self.path.extend([(start.x-1, start.y), (start.x-2, start.y)])

    def parse_path(self):
        facing = self.knowledge_decoder.info['facing']
        position = self.knowledge_decoder.knowledge.position
        target = self.path[0]

        target = coordinates.Coords(target[0], target[1])

        cords_sub = coordinates.sub_coords(target, position)
        sub_max = max([abs(cords_sub.x), abs(cords_sub.y)])

        cords_facing = coordinates.Coords(cords_sub.x / sub_max, cords_sub.y / sub_max)
        if cords_facing.x == 1:
            cords_facing = coordinates.Coords(1, 0)
        elif cords_facing.x == -1:
            cords_facing = coordinates.Coords(-1, 0)
        elif cords_facing.y == 1:
            cords_facing = coordinates.Coords(0, 1)
        elif cords_facing.y == -1:
            cords_facing = coordinates.Coords(0, -1)

        needed_facing = Facing(cords_facing)

        if facing == needed_facing:
            self.path.popleft()
            return characters.Action.STEP_FORWARD
        else:
            return ROTATIONS[(facing, needed_facing)]

    def look_around(self):
        return characters.Action.TURN_RIGHT

    def walk_around(self, probabilities=None):
        if probabilities:
            return np.random.choice(POSSIBLE_ACTIONS, 1, probabilities)[0]
        else:
            return np.random.choice(POSSIBLE_ACTIONS, 1, self.walk_around_probabilities)[0]

    def choose_shorter_dist(self, list_of_objects):
        position = self.knowledge_decoder.knowledge.position
        distances = [distance(position, object_pos) for object_pos in list_of_objects]
        return list_of_objects[np.argmin(distances)]

    def find_weapon(self):
        weapon_cords = self.choose_shorter_dist(self.knowledge_decoder.info['weapons_in_sight'])
        position = self.knowledge_decoder.knowledge.position
        self.find_path(position, weapon_cords)
        self.goal = weapon_cords

    def find_enemy(self):
        enemy_cords = self.choose_shorter_dist(self.knowledge_decoder.info['enemies_in_sight'])
        position = self.knowledge_decoder.knowledge.position

        self.find_path(position, enemy_cords)
        self.goal = coordinates.Coords(self.path[-1][0], self.path[-1][1])

    def find_menhir(self):
        menhir_coords = self.knowledge_decoder.info['menhir_position']
        if menhir_coords:
            goal = menhir_coords
        else:
            goal = self.knowledge_decoder.info['temp_safe_spot']
        position = self.knowledge_decoder.knowledge.position
        self.find_path(position, goal)
        self.goal = goal

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
        mist = self.knowledge_decoder.info['mist']
        if mist:
            nearest_mist = self.choose_shorter_dist(self.knowledge_decoder.info['mist'])
            mist_dist = distance(self.knowledge_decoder.knowledge.position, nearest_mist)
            if mist_dist <= 5:
                self.path = deque()
                self.find_menhir()
                list_path = list(self.path)
                if len(list_path) > 7:
                    self.path = deque(list_path[:6])

    def is_goal_reached(self):
        if self.goal:
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

    def preparation(self):
        self.position_history.append(self.knowledge_decoder.knowledge.position)
        self.is_goal_reached()
        self.is_moving()
        self.runaway_from_mist()
        self._is_possible_to_move()

    def name(self) -> str:
        return self.__class__.__name__.lower()

    def _is_possible_to_move(self):
        if self.path:
            next_step = self.path[0]
            position = self.knowledge_decoder.knowledge.position
            possible_moves_x = list(range(position.x - 1, position.x + 2))
            possible_moves_y = list(range(position.y - 1, position.y + 2))
            if next_step[0] in possible_moves_x and next_step[1] in possible_moves_y:
                pass
            else:
                # print('Resetting path, ns: ', next_step, ' pos: ', position)
                self.path = deque()
                self.important_moves.extend([characters.Action.TURN_RIGHT, characters.Action.TURN_RIGHT])

    def low_health(self):
        if self.knowledge_decoder.info['health'] <= 2 and self.knowledge_decoder.info['enemies_in_sight']:
            nearest_enemy = self.choose_shorter_dist(self.knowledge_decoder.info['enemies_in_sight'])
            enemy_dist = distance(self.knowledge_decoder.knowledge.position, nearest_enemy)
            if enemy_dist <= 3:
                self.path = deque()
                self.important_moves = deque()
                self.important_moves.extend([
                    characters.Action.TURN_RIGHT,
                    characters.Action.TURN_RIGHT,
                    characters.Action.STEP_FORWARD,
                    characters.Action.STEP_FORWARD
                ])


class AggressiveStrategy(Strategy):
    def __init__(self, knowledge_decoder):
        super().__init__(knowledge_decoder)

    def pick_action(self):
        self.preparation()

        if self.important_moves:
            next_move = self.important_moves.popleft()
        elif self.can_attack():
            next_move = characters.Action.ATTACK
        elif self.path:
            next_move = self.parse_path()
        elif self.knowledge_decoder.info['weapon'] != 'knife' and self.knowledge_decoder.info['weapons_in_sight']:
            self.find_weapon()
            next_move = self.parse_path()
        elif self.knowledge_decoder.info['enemies_in_sight']:
            self.find_enemy()
            next_move = self.parse_path()
        else:
            next_move = self.walk_around()
        return next_move


class MenhirStrategy(Strategy):
    def __init__(self, knowledge_decoder):
        super().__init__(knowledge_decoder)
        self.menhir_reached = False
        self.safe_spot_reached = False
        self.look_for_menhir_probabilities = [0.2, 0.2, 0.6, 0]

    def _is_on_menhir(self):
        position = self.knowledge_decoder.knowledge.position
        menhir_coords = self.knowledge_decoder.info['menhir_position']
        safe_spot = self.knowledge_decoder.info['temp_safe_spot']
        if menhir_coords is not None:
            if menhir_coords.x == position.x and menhir_coords.y == position.y:
                self.menhir_reached = True
                self.path = deque()
        else:
            if position.x == safe_spot.x and position.y == safe_spot.y:
                self.safe_spot_reached = True
                self.path = deque()


class FastMenhirStrategy(MenhirStrategy):
    def __init__(self, knowledge_decoder):
        super().__init__(knowledge_decoder)

    def pick_action(self):
        self.preparation()
        self._is_on_menhir()

        if self.important_moves:
            next_move = self.important_moves.popleft()
        elif self.can_attack():
            next_move = characters.Action.ATTACK
        elif self.path:
            next_move = self.parse_path()
        elif not self.menhir_reached:
            self.find_menhir()
            next_move = self.parse_path()
        elif self.menhir_reached:
            next_move = self.look_around()
        elif self.safe_spot_reached:
            next_move = self.walk_around(self.look_for_menhir_probabilities)
        else:
            next_move = self.walk_around()
        return next_move


class GoodWeaponMenhirStrategy(MenhirStrategy):
    def __init__(self, knowledge_decoder):
        super().__init__(knowledge_decoder)
        self.weapon_value = 1

    def pick_action(self):
        self.preparation()
        self._is_on_menhir()
        self.weapon_choose()

        if self.important_moves:
            next_move = self.important_moves.popleft()
        elif self.can_attack():
            next_move = characters.Action.ATTACK
        elif self.path:
            next_move = self.parse_path()
        elif self.weapon_value < 15 and self.knowledge_decoder.info['weapons_in_sight']:
            self.find_weapon()
            next_move = self.parse_path()
        elif self.weapon_value < 15:
            next_move = self.walk_around()
        elif not self.menhir_reached:
            self.find_menhir()
            next_move = self.parse_path()
        elif self.menhir_reached:
            next_move = self.look_around()
        elif self.safe_spot_reached:
            next_move = self.walk_around(self.look_for_menhir_probabilities)
        else:
            next_move = self.walk_around()
        return next_move

    def weapon_choose(self):
        bot_weapon = self.knowledge_decoder.info['weapon']
        self.weapon_value = WEAPONS_VALUE.get(bot_weapon, 1)


class RunawayStrategy(Strategy):
    def __init__(self, knowledge_decoder):
        super().__init__(knowledge_decoder)
        self.dist_to_menhir = 200
        self.old_dist_to_menhir = 200
        self.map_size = None

    def calculate_dist(self):
        self.old_dist_to_menhir = self.dist_to_menhir
        position = self.knowledge_decoder.knowledge.position
        menhir_coords = self.knowledge_decoder.info['menhir_position']
        safe_spot = self.knowledge_decoder.info['temp_safe_spot']
        if menhir_coords:
            self.dist_to_menhir = distance(position, menhir_coords)
        else:
            self.dist_to_menhir = distance(position, safe_spot)

    def pick_action(self):
        self.preparation()
        self.calculate_dist()
        self.map_size = self.knowledge_decoder.info['map_size']
        if self.knowledge_decoder.info['enemies_in_sight']:
            nearest_enemy = self.choose_shorter_dist(self.knowledge_decoder.info['enemies_in_sight'])
            enemy_dist = distance(self.knowledge_decoder.knowledge.position, nearest_enemy)
        else:
            enemy_dist = 10

        if self.important_moves:
            next_move = self.important_moves.popleft()
        elif self.can_attack():
            next_move = characters.Action.ATTACK
        elif self.path:
            next_move = self.parse_path()
        elif enemy_dist <= 5:
            self.turn_around()
            next_move = characters.Action.TURN_RIGHT
        else:
            next_move = self.walk_around()
        return next_move

    def turn_around(self):
        runaway_moves = [
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.STEP_FORWARD
        ]
        self.important_moves.extendleft(runaway_moves)

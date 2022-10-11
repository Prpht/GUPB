import random
import numpy as np

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Axe, Bow, Sword, Amulet

current_arena = arenas.Arena.load("lone_sanctum")

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]

weapons = {
    'knife': Knife,
    'axe': Axe,
    'bow_loaded': Bow,
    'bow_unloaded': Bow,
    'sword': Sword,
    'amulet': Amulet
}

clusters = np.array(
    [[ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0],
     [ 0, 18, 18, 18,  0, 11, 11, 11,  0,  0,  0, 23, 23, 23,  0, 24, 24, 24,  0],
     [ 0, 18, 18, 18,  0, 11, 11, 17,  0,  0, 22, 23, 23, 20,  0, 24, 24, 24,  0],
     [ 0, 18, 18, 18, 11, 11, 11, 17, 17,  0, 22, 22, 20, 20, 20, 24, 24, 24,  0],
     [ 0,  0,  0,  0,  0, 11, 11, 17, 17, 22, 22, 20, 20, 20,  0,  0,  0,  0,  0],
     [ 0, 10, 10,  6,  6,  6, 11, 17, 17, 22, 22,  0,  0, 13, 13, 13, 13, 13,  0],
     [ 0, 10,  6,  6,  6,  0,  0,  0,  0,  0,  0,  0,  0,  7, 13,  7, 13,  7,  0],
     [ 0, 10, 10,  6,  3,  3,  3,  3,  3,  1,  4,  4,  0,  7,  7,  7,  7,  7,  0],
     [ 0,  0,  0, 12,  0,  0,  0,  3,  1,  1,  0,  4,  0,  0,  0,  7,  0,  0,  0],
     [ 0,  0,  0, 12,  0,  0,  0,  3,  1,  1,  1,  4,  0,  0,  0,  7,  0,  0,  0],
     [ 0,  0,  0, 12,  0,  0,  0,  2,  0,  1,  2,  4,  0,  0,  0,  7,  0,  0,  0],
     [ 0, 19, 12, 12, 12, 19,  0,  2,  2,  2,  2,  2,  5,  5,  5,  5,  8,  0,  0],
     [ 0, 19, 19, 12, 19, 19,  0,  0,  0,  0,  0,  0,  0,  0,  5,  5,  8,  0,  0],
     [ 0, 19, 19, 19, 19, 19,  0,  0, 16, 16, 16,  9,  9,  9,  5,  8,  8,  8,  0],
     [ 0,  0,  0,  0,  0, 21, 21, 21, 16, 16, 16, 14,  9,  9,  0,  0,  0,  0,  0],
     [ 0, 26, 26, 25, 25, 25, 21, 21, 16,  0, 14, 14, 14,  9, 15, 15, 15, 15,  0],
     [ 0, 26, 26, 26,  0, 25, 25, 21, 16,  0,  0, 14, 14,  9,  0, 15, 15, 15,  0],
     [ 0, 26, 26, 26,  0, 25, 25, 21,  0,  0,  0, 14, 14,  9,  0, 15, 15, 15,  0],
     [ 0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0,  0]]
)

adj = {
    1: [3, 2, 4],
    2: [1, 5, 3, 4],
    3: [6, 2, 1],
    4: [1, 2],
    5: [9, 8, 7, 2],
    6: [10, 3, 11, 12],
    7: [5, 13],
    8: [5],
    9: [15, 14, 16, 5],
    10: [6],
    11: [18, 17, 6],
    12: [6, 19],
    13: [7, 20],
    14: [9, 16],
    15: [9],
    16: [9, 21, 14],
    17: [11, 22],
    18: [11],
    19: [21, 12],
    20: [13, 22, 23, 24],
    21: [16, 19, 25],
    22: [23, 20, 17],
    23: [22, 20],
    24: [20],
    25: [26, 21],
    26: [25]
}

closest_weapon = np.array(
    [['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-'],
     ['-', 'A', 'A', 'A', '-', 'A', 'A', 'A', '-', '-', '-', 'B', 'B', 'B', '-', 'B', 'B', 'B', '-'],
     ['-', 'A', 'A', 'A', '-', 'A', 'A', 'A', '-', '-', 'B', 'B', 'B', 'B', '-', 'B', 'B', 'B', '-'],
     ['-', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', '-', 'B', 'B', 'B', 'B', 'B', 'B', 'B', 'B', '-'],
     ['-', '-', '-', '-', '-', 'A', 'A', 'A', 'A', 'A', 'B', 'B', 'B', 'B', '-', '-', '-', '-', '-'],
     ['-', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'B', '-', '-', 'B', 'B', 'B', 'B', 'B', '-'],
     ['-', 'A', 'A', 'A', 'A', '-', '-', '-', '-', '-', '-', '-', '-', 'B', 'B', 'B', 'B', 'B', '-'],
     ['-', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', 'A', '-', 'B', 'B', 'B', 'B', 'B', '-'],
     ['-', '-', '-', 'A', '-', '-', '-', 'A', 'A', 'A', '-', 'M', '-', '-', '-', 'B', '-', '-', '-'],
     ['-', '-', '-', 'A', '-', '-', '-', 'A', 'A', 'A', 'M', 'M', '-', '-', '-', 'B', '-', '-', '-'],
     ['-', '-', '-', 'S', '-', '-', '-', 'A', '-', 'M', 'M', 'M', '-', '-', '-', 'M', '-', '-', '-'],
     ['-', 'S', 'S', 'S', 'S', 'S', '-', 'A', 'M', 'M', 'M', 'M', 'M', 'M', 'M', 'M', 'M', '-', '-'],
     ['-', 'S', 'S', 'S', 'S', 'S', '-', '-', '-', '-', '-', '-', '-', '-', 'M', 'M', 'M', '-', '-'],
     ['-', 'S', 'S', 'S', 'S', 'S', '-', '-', 'S', 'S', 'M', 'M', 'M', 'M', 'M', 'M', 'M', 'M', '-'],
     ['-', '-', '-', '-', '-', 'S', 'S', 'S', 'S', 'S', 'M', 'M', 'M', 'M', '-', '-', '-', '-', '-'],
     ['-', 'S', 'S', 'S', 'S', 'S', 'S', 'S', 'S', '-', 'M', 'M', 'M', 'M', 'M', 'M', 'M', 'M', '-'],
     ['-', 'S', 'S', 'S', '-', 'S', 'S', 'S', 'S', '-', '-', 'M', 'M', 'M', '-', 'M', 'M', 'M', '-'],
     ['-', 'S', 'S', 'S', '-', 'S', 'S', 'S', '-', '-', '-', 'M', 'M', 'M', '-', 'M', 'M', 'M', '-'],
     ['-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-', '-']]
)

weapon_locations = {'A': Coords(1, 1), 'B': Coords(17, 1), 'S': Coords(1, 17), 'M': Coords(17, 17)}
menhir_location = Coords(9, 9)

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Spejson(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = True
        self.target = Coords(9, 9)
        self.jitter = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Spejson):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.move_number += 1
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        available_actions = POSSIBLE_ACTIONS.copy()

        me = knowledge.visible_tiles[position].character
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon

        if not self.menhir_found:
            for tile_coord in visible_tiles:
                if visible_tiles[tile_coord].type == 'menhir':
                    self.target = Coords(tile_coord[0], tile_coord[1])
                    self.menhir_found = True

        if self.weapon.name == 'knife':
            self.target = weapon_locations[closest_weapon[position.y, position.x]]
            self.jitter = 10
        else:
            self.target = menhir_location
            self.jitter = 35

        # Positions in reach
        in_reach = weapons[self.weapon.name].cut_positions(current_arena.terrain, position, self.facing)
        anyone_in_reach = False
        for pos in in_reach:
            if pos in visible_tiles and knowledge.visible_tiles[pos].character is not None:
                available_actions = [Action.ATTACK]
                anyone_in_reach = True
                break

        if not anyone_in_reach:
            available_actions = [x for x in available_actions if x not in [Action.ATTACK]]

        # Rule out stupid moves
        next_block = position + self.facing.value
        if next_block in visible_tiles:
            if visible_tiles[next_block].type in ['sea', 'wall']:
                available_actions = [x for x in available_actions if x not in [Action.STEP_FORWARD]]

        if Action.STEP_FORWARD in available_actions:
            distance_from_target = self.target - position
            distance_from_target = distance_from_target.x ** 2 + distance_from_target.y ** 2
            if distance_from_target > self.jitter:
                if np.random.rand() < 0.8:
                    return Action.STEP_FORWARD
            else:
                if np.random.rand() < 0.5:
                    return Action.STEP_FORWARD

        if Action.ATTACK not in available_actions:
            left_ahead = self.target - (position + self.facing.turn_left().value)
            left_ahead = left_ahead.x ** 2 + left_ahead.y ** 2
            right_ahead = self.target - (position + self.facing.turn_right().value)
            right_ahead = right_ahead.x ** 2 + right_ahead.y ** 2

            if left_ahead < right_ahead:
                return Action.TURN_LEFT if np.random.rand() < 0.7 else Action.TURN_RIGHT
            else:
                return Action.TURN_RIGHT if np.random.rand() < 0.7 else Action.TURN_LEFT

        return random.choice(available_actions)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = True
        self.target = Coords(9, 9)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK


POTENTIAL_CONTROLLERS = [
    Spejson("Spejson"),
]

import os
import random
import enum
from typing import NamedTuple, Optional, List, Tuple

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.coordinates import Coords, add_coords, sub_coords
from gupb.model.tiles import TileDescription
from gupb.model.characters import Facing, Action, ChampionDescription, PENALISED_IDLE_TIME
from gupb.model.weapons import WeaponDescription

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

TILE_ENCODING = {
    '=': TileDescription(type='sea', loot=None, character=None, effects=[]),
    '.': TileDescription(type='land', loot=None, character=None, effects=[]),
    '#': TileDescription(type='wall', loot=None, character=None, effects=[]),
}

WEAPON_ENCODING = {
    'K': WeaponDescription(name='knife'),
    'S': WeaponDescription(name='sword'),
    'A': WeaponDescription(name='axe'),
    'B': WeaponDescription(name='bow_unloaded'),
    'M': WeaponDescription(name='amulet'),
}

AREAS = {
    'center': (Coords(7, 7), Coords(12, 12)),
    'north-west': (Coords(0, 0), Coords(10, 10)),
    'north-east': (Coords(10, 0), Coords(19, 9)),
    'south-west': (Coords(0, 10), Coords(9, 19)),
    'south-east': (Coords(9, 9), Coords(19, 19))
}

INFINITY: int = 99999999
TURNS_TO_FOG: int = 80
MENHIR: Coords = Coords(9, 9)


class Strategy(enum.Enum):
    EARLY_SPIN = 'early_spin'
    ATTACK = 'attack'
    MOVE_TO_CENTER = 'move_to_center'
    ESCAPE = 'escape'
    RANDOM = 'random'
    MINIMIZE_RISK = 'minimize_risk'
    GRAB_WEAPON = 'grab_weapon'
    ENDGAME = 'endgame'
    ANTI_IDLE = 'anti_idle'


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class DodgeController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.tiles: {Coords: TileDescription} = {}
        self.spinning_stage = 0
        self.position: Coords = Coords(-1, -1)
        self.facing: Facing = Facing.UP
        self.path: Optional[List[Coords]] = None
        self.target: Optional[Coords] = None
        self.weapon: WeaponDescription = WeaponDescription(name='knife')
        self.known_enemies: {str: Tuple[Coords, ChampionDescription, int]} = {}
        self.danger_ratings: {str: int} = {'left': INFINITY,
                                           'right': INFINITY,
                                           'down': INFINITY,
                                           'up': INFINITY,
                                           'center': INFINITY}
        self.turn: int = 0
        self.health: int = 8
        self.run: int = 0
        self.areas: {str: List[ChampionDescription]} = {
            'center': [],
            'north-west': [],
            'north-east': [],
            'south-west': [],
            'south-east': [],
        }
        self.safe_to_get_weapon = True
        self.idle_time = 0
        self.last_position = None
        self.last_facing = None
        self.load_arena()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DodgeController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # Gather information from seen tiles
        self.turn += 1
        self.last_facing = self.facing
        self.last_position = self.position
        self.position = knowledge.position
        for tile in knowledge.visible_tiles:
            self.tiles[Coords(tile[0], tile[1])] = knowledge.visible_tiles[tile]
            if tile == self.position:
                self.facing = knowledge.visible_tiles[tile].character.facing
                self.weapon = knowledge.visible_tiles[tile].character.weapon
                if self.health > knowledge.visible_tiles[tile].character.health:
                    self.run = 5
                    self.health = knowledge.visible_tiles[tile].character.health
            elif knowledge.visible_tiles[tile].character is not None:
                self.known_enemies[knowledge.visible_tiles[tile].character.controller_name] \
                    = (Coords(tile[0], tile[1]), knowledge.visible_tiles[tile].character, -1)
                for area in self.areas.keys():
                    if self.areas[area].count(knowledge.visible_tiles[tile].character) > 0:
                        self.areas[area].remove(knowledge.visible_tiles[tile].character)
                current_area = 'center'
                for area in AREAS.keys():
                    if AREAS[area][0].x <= tile[0] < AREAS[area][1].x and AREAS[area][0].y <= tile[1] < AREAS[area][1].y:
                        current_area = area
                        break
                self.areas[current_area].append(knowledge.visible_tiles[tile].character)
            if knowledge.visible_tiles[tile].type == 'menhir':
                self.target = Coords(tile[0], tile[1])

        if self.position == self.last_position and self.facing == self.last_facing:
            self.idle_time += 1
        else:
            self.idle_time = 0

        # Check where to go
        if self.turn > TURNS_TO_FOG or not self.safe_to_get_weapon:
            self.target = MENHIR
            self.safe_to_get_weapon = False
        else:
            for area in self.areas.keys():
                if AREAS[area][0].x <= self.position.x < AREAS[area][1].x and AREAS[area][0].y <= self.position.y < AREAS[area][1].y:
                    if area == 'center':
                        self.safe_to_get_weapon = False
                        self.target = None
                    elif area == 'north-west':
                        if self.weapon == WeaponDescription(name='knife'):
                            self.target = Coords(1, 2)
                        else:
                            self.target = Coords(3, 2)
                    elif area == 'north-east':
                        if self.weapon == WeaponDescription(name='knife'):
                            self.target = Coords(17, 2)
                        else:
                            self.target = Coords(17, 3)
                    elif area == 'south-west':
                        if self.weapon == WeaponDescription(name='knife'):
                            self.target = Coords(1, 16)
                        else:
                            self.target = Coords(3, 15)
                    elif area == 'south-east':
                        if self.weapon == WeaponDescription(name='knife'):
                            self.target = Coords(16, 17)
                        else:
                            self.target = Coords(15, 16)
                    break

        # Check if getting a weapon is safe
        if self.safe_to_get_weapon and self.weapon == WeaponDescription(name='knife'):
            for area in self.areas.keys():
                if AREAS[area][0].x <= self.position.x < AREAS[area][1].x and AREAS[area][0].y <= self.position.y < AREAS[area][1].y:
                    current_distance = self.find_path(self.position, self.target, self.facing)[1]
                    for enemy in self.areas[area]:
                        if self.find_path(self.known_enemies[enemy.controller_name][0], self.target, enemy.facing)[1] < current_distance:
                            self.safe_to_get_weapon = False
                            break
                    break

        # Update risks
        for enemy in self.known_enemies.keys():
            value = self.known_enemies[enemy]
            self.known_enemies[enemy] = value[0], value[1], value[2] + 1
            self.danger_ratings['center'] = \
                min(self.danger_ratings['center'], self.find_path(self.known_enemies[enemy][0],
                                                                  self.position,
                                                                  self.known_enemies[enemy][1].facing)[1]
                    + value[2] + 1)
            self.danger_ratings['left'] = \
                min(self.danger_ratings['left'], self.find_path(self.known_enemies[enemy][0],
                                                                self.forward(self.position, Facing.LEFT),
                                                                self.known_enemies[enemy][1].facing)[1]
                    + value[2] + 1)
            self.danger_ratings['right'] = \
                min(self.danger_ratings['right'], self.find_path(self.known_enemies[enemy][0],
                                                                 self.forward(self.position, Facing.RIGHT),
                                                                 self.known_enemies[enemy][1].facing)[1]
                    + value[2] + 1)
            self.danger_ratings['up'] = \
                min(self.danger_ratings['up'], self.find_path(self.known_enemies[enemy][0],
                                                              self.forward(self.position, Facing.UP),
                                                              self.known_enemies[enemy][1].facing)[1]
                    + value[2] + 1)
            self.danger_ratings['down'] = \
                min(self.danger_ratings['down'], self.find_path(self.known_enemies[enemy][0],
                                                                self.forward(self.position, Facing.DOWN),
                                                                self.known_enemies[enemy][1].facing)[1])

        # Find the safest move
        best_move: str = 'center'
        best_rating: int = -1
        for move in ('left', 'right', 'up', 'down', 'center'):
            if self.danger_ratings[move] > best_rating and self.move_possible(move):
                best_rating = self.danger_ratings[move]
                best_move = move

        # Find the best path to the chosen target
        if self.target is not None:
            self.path = self.find_path(self.position, self.target, self.facing)[0]
            if len(self.path) > 0:
                self.path.pop(0)

        # Choose strategy for the turn
        strategy: Strategy = Strategy.RANDOM
        if self.idle_time == PENALISED_IDLE_TIME - 1:
            strategy = Strategy.ANTI_IDLE
        elif not all(enemy[2] >= 2 or not self.is_in_range(enemy[0]) for enemy in self.known_enemies.values()):
            strategy = Strategy.ATTACK
        elif self.run > 0 and self.tiles[self.forward(self.position, self.facing)].type in ('land', 'menhir'):
            strategy = Strategy.ESCAPE
        elif self.spinning_stage < 4:
            strategy = Strategy.EARLY_SPIN
        elif self.safe_to_get_weapon:
            strategy = Strategy.GRAB_WEAPON
        elif random.random() * TURNS_TO_FOG * 2 < self.turn and self.path is not None and len(self.path) > 0:
            strategy = Strategy.MOVE_TO_CENTER
        elif self.turn > TURNS_TO_FOG and 7 <= self.position.x < 12 and 7 <= self.position.y < 12:
            strategy = Strategy.ENDGAME
        elif random.random() * 100 < best_rating:
            strategy = Strategy.RANDOM
        else:
            strategy = Strategy.MINIMIZE_RISK

        # Update some values
        if self.run > 0:
            self.run -= 1
        if self.spinning_stage < 4:
            self.spinning_stage += 1

        # Execute strategy
        if strategy == Strategy.ANTI_IDLE:
            self.idle_time = 0
            return characters.Action.TURN_LEFT
        if strategy == Strategy.ATTACK:
            return characters.Action.ATTACK
        elif strategy == Strategy.ESCAPE:
            return characters.Action.STEP_FORWARD
        elif strategy == Strategy.EARLY_SPIN:
            return characters.Action.TURN_LEFT
        elif strategy == Strategy.GRAB_WEAPON:
            if self.target == self.position:
                if self.position.x < 9:
                    if self.position.y > 9:
                        if self.facing == Facing.RIGHT:
                            return characters.Action.ATTACK
                        elif self.facing.turn_left() == Facing.RIGHT:
                            return characters.Action.TURN_LEFT
                        else:
                            return characters.Action.TURN_RIGHT
                    else:
                        if self.facing == Facing.DOWN:
                            return characters.Action.ATTACK
                        elif self.facing.turn_left() == Facing.DOWN:
                            return characters.Action.TURN_LEFT
                        else:
                            return characters.Action.TURN_RIGHT
                else:
                    if self.facing == Facing.LEFT:
                        return characters.Action.ATTACK
                    elif self.facing.turn_left() == Facing.LEFT:
                        return characters.Action.TURN_LEFT
                    else:
                        return characters.Action.TURN_RIGHT
            else:
                return self.get_action_to_move_in_path()
        elif strategy == Strategy.MOVE_TO_CENTER:
            return self.get_action_to_move_in_path()
        elif strategy == Strategy.ENDGAME:
            if self.position == Coords(9, 9):
                return characters.Action.TURN_LEFT
            if self.weapon == WeaponDescription(name='sword')\
                    or self.weapon == WeaponDescription(name='bow_loaded')\
                    or self.weapon == WeaponDescription(name='bow_unloaded'):
                optimal_positions = [Coords(7, 9), Coords(9, 7), Coords(9, 11), Coords(11, 9)]
                if self.position not in optimal_positions:
                    path = None
                    distance = INFINITY
                    for position in optimal_positions:
                        current_path, current_distance = self.find_path(self.position, position, self.facing)
                        if current_distance < distance:
                            distance = current_distance
                            path = current_path
                    if len(path) > 1:
                        direction = sub_coords(path[1], self.position)
                        if direction == self.facing.value:
                            self.path.pop(1)
                            return characters.Action.STEP_FORWARD
                        elif direction == self.facing.turn_left().value:
                            return characters.Action.TURN_LEFT
                        else:
                            return characters.Action.TURN_RIGHT
                    else:
                        return random.choice(POSSIBLE_ACTIONS)
                else:
                    direction = Coords(int(sub_coords(self.target, self.position).x / 2),
                                       int(sub_coords(self.target, self.position).y / 2))
                    if direction == self.facing.turn_left().value:
                        return characters.Action.TURN_LEFT
                    else:
                        return characters.Action.TURN_RIGHT
            elif self.weapon == WeaponDescription(name='axe'):
                enemy_weapon = WeaponDescription(name='knife')
                for enemy in self.known_enemies.values():
                    if enemy[0] == Coords(9, 9):
                        enemy_weapon = enemy[1].weapon.name
                        break

                optimal_positions = [Coords(8, 9), Coords(9, 8), Coords(10, 9), Coords(9, 10)]\
                    if enemy_weapon == 'amulet' else [Coords(8, 8), Coords(10, 10)]

                if self.position in optimal_positions:
                    if self.position.x == self.position.y:
                        if self.facing == Facing.RIGHT or self.facing == Facing.LEFT:
                            return characters.Action.TURN_LEFT
                        else:
                            return characters.Action.TURN_RIGHT
                    else:
                        direction = sub_coords(self.target, self.position)
                        if direction == self.facing.turn_left().value:
                            return characters.Action.TURN_LEFT
                        else:
                            return characters.Action.TURN_RIGHT
                else:
                    path = None
                    distance = INFINITY
                    for position in optimal_positions:
                        current_path, current_distance = self.find_path(self.position, position, self.facing)
                        if current_distance < distance:
                            distance = current_distance
                            path = current_path
                    if len(path) > 1:
                        direction = sub_coords(path[1], self.position)
                        if direction == self.facing.value:
                            self.path.pop(1)
                            return characters.Action.STEP_FORWARD
                        elif direction == self.facing.turn_left().value:
                            return characters.Action.TURN_LEFT
                        else:
                            return characters.Action.TURN_RIGHT
                    else:
                        return random.choice(POSSIBLE_ACTIONS)
            elif self.weapon == WeaponDescription(name='amulet'):
                optimal_positions = [Coords(7, 7), Coords(11, 11), Coords(7, 11), Coords(11, 7)]
                if self.position in optimal_positions:
                    return self.get_action_to_move_in_path()
                else:
                    path = None
                    distance = INFINITY
                    for position in optimal_positions:
                        current_path, current_distance = self.find_path(self.position, position, self.facing)
                        if current_distance < distance:
                            distance = current_distance
                            path = current_path
                    if len(path) > 1:
                        direction = sub_coords(path[1], self.position)
                        if direction == self.facing.value:
                            self.path.pop(1)
                            return characters.Action.STEP_FORWARD
                        elif direction == self.facing.turn_left().value:
                            return characters.Action.TURN_LEFT
                        else:
                            return characters.Action.TURN_RIGHT
                    else:
                        return random.choice(POSSIBLE_ACTIONS)
            else:
                return self.get_action_to_move_in_path()
        elif strategy == Strategy.RANDOM:
            return random.choice(POSSIBLE_ACTIONS)
        else:
            return self.pick_action(best_move)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.tiles: {Coords: TileDescription} = {}
        self.spinning_stage = 0
        self.position: Coords = Coords(-1, -1)
        self.facing: Facing = Facing.UP
        self.path: Optional[List[Coords]] = None
        self.target: Optional[Coords] = None
        self.weapon: WeaponDescription = WeaponDescription(name='knife')
        self.known_enemies: {str: Tuple[Coords, ChampionDescription, int]} = {}
        self.danger_ratings: {str: int} = {'left': INFINITY,
                                           'right': INFINITY,
                                           'down': INFINITY,
                                           'up': INFINITY,
                                           'center': INFINITY}
        self.turn: int = 0
        self.health: int = 8
        self.run: int = 0
        self.areas: {str: List[ChampionDescription]} = {
            'center': [],
            'north-west': [],
            'north-east': [],
            'south-west': [],
            'south-east': [],
        }
        self.safe_to_get_weapon = True
        self.idle_time = 0
        self.last_position = None
        self.last_facing = None
        self.load_arena()

    @property
    def name(self) -> str:
        return f'DodgeController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.STRIPPED

    def get_action_to_move_in_path(self) -> characters.Action:
        direction = sub_coords(self.path[0], self.position)
        if direction == self.facing.value:
            self.path.pop(0)
            return characters.Action.STEP_FORWARD
        elif direction == self.facing.turn_left().value:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT

    def load_arena(self):
        with open(os.path.abspath('resources/arenas/lone_sanctum.gupb')) as file:
            for y, line in enumerate(file.readlines()):
                for x, character in enumerate(line):
                    if character != '\n':
                        position = Coords(x, y)
                        if character in TILE_ENCODING:
                            self.tiles[position] = TILE_ENCODING[character]
                        elif character in WEAPON_ENCODING:
                            self.tiles[position] = TileDescription(type=TILE_ENCODING['.'].type,
                                                                   loot=WEAPON_ENCODING[character],
                                                                   character=None,
                                                                   effects=[])

    def move_possible(self, move):
        if move == 'center':
            return True
        if move == 'left':
            return self.tiles[self.forward(self.position, Facing.LEFT)].type in ('land', 'menhir')
        if move == 'right':
            return self.tiles[self.forward(self.position, Facing.RIGHT)].type in ('land', 'menhir')
        if move == 'up':
            return self.tiles[self.forward(self.position, Facing.UP)].type in ('land', 'menhir')
        if move == 'right':
            return self.tiles[self.forward(self.position, Facing.RIGHT)].type in ('land', 'menhir')

    def pick_action(self, direction: str) -> Action:
        if direction == 'center':
            return characters.Action.TURN_LEFT

        correct_facing: Facing
        if direction == 'left':
            correct_facing = Facing.LEFT
        elif direction == 'right':
            correct_facing = Facing.RIGHT
        elif direction == 'up':
            correct_facing = Facing.UP
        else:
            correct_facing = Facing.DOWN

        if correct_facing.value == self.facing.value:
            return characters.Action.STEP_FORWARD

        if correct_facing.turn_left().value == self.facing.value:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT

    def forward(self, current_coords: Coords, direction: Facing) -> Coords:
        if direction == Facing.LEFT:
            return Coords(current_coords.x - 1, current_coords.y)
        if direction == Facing.RIGHT:
            return Coords(current_coords.x + 1, current_coords.y)
        if direction == Facing.UP:
            return Coords(current_coords.x, current_coords.y - 1)
        if direction == Facing.DOWN:
            return Coords(current_coords.x, current_coords.y + 1)

    def is_in_range(self, enemy_coords: Coords) -> bool:
        if self.weapon.name == 'knife':
            return enemy_coords in [add_coords(self.position, self.facing.value)]
        if self.weapon.name == 'sword':
            return enemy_coords in [add_coords(self.position, self.facing.value),
                                    Coords(self.position.x + 2 * self.facing.value.x,
                                           self.position.y + 2 * self.facing.value.y),
                                    Coords(self.position.x + 3 * self.facing.value.x,
                                           self.position.y + 3 * self.facing.value.y)]
        if self.weapon.name == 'axe':
            return enemy_coords in [add_coords(self.position, self.facing.value),
                                    Coords(self.position.x - self.facing.value.y,
                                           self.position.y - self.facing.value.x),
                                    Coords(self.position.x + self.facing.value.y,
                                           self.position.y + self.facing.value.x)]
        if self.weapon.name == 'bow_unloaded' or self.weapon.name == 'bow_loaded':
            diff_vector: Coords = sub_coords(enemy_coords, self.position)
            if diff_vector.x * diff_vector.y != 0:
                return False
            if diff_vector.x * self.facing.value.x + diff_vector.y * self.facing.value.y <= 0:
                return False
            return True
        if self.weapon.name == 'amulet':
            return enemy_coords in [Coords(self.position.x + 1, self.position.y + 1),
                                    Coords(self.position.x - 1, self.position.y - 1),
                                    Coords(self.position.x + 1, self.position.y - 1),
                                    Coords(self.position.x - 1, self.position.y + 1),
                                    Coords(self.position.x - 2, self.position.y + 2),
                                    Coords(self.position.x - 2, self.position.y - 2),
                                    Coords(self.position.x + 2, self.position.y - 2),
                                    Coords(self.position.x + 2, self.position.y + 2)]
        return False

    def get_facing(self, f_coords: Coords) -> Facing:
        if f_coords == Coords(0, 1):
            return Facing.DOWN
        elif f_coords == Coords(0, -1):
            return Facing.UP
        elif f_coords == Coords(1, 0):
            return Facing.LEFT
        elif f_coords == Coords(-1, 0):
            return Facing.RIGHT

    def find_path(self, start: Coords, end: Coords, facing: Facing) -> (Optional[List[Coords]], int):
        def get_h_cost(h_start: Coords, h_end: Coords, h_facing: Facing) -> int:
            distance: int = abs(h_end.y - h_start.y) + abs(h_end.x - h_start.x)
            direction: Coords = Coords(1 if h_end.x - h_start.x > 0 else -1 if h_end.x - h_start.x < 0 else 0,
                                       1 if h_end.y - h_start.y > 0 else -1 if h_end.y - h_start.y < 0 else 0)
            turns = abs(h_facing.value.x - direction.x) + abs(h_facing.value.y - direction.y)
            return (turns if turns <= 2 else 2) + distance

        a_coords = NamedTuple('a_coords', [('coords', Coords),
                                           ('g_cost', int),
                                           ('h_cost', int),
                                           ('parent', Optional[Coords]),
                                           ('facing', Facing)])

        open_coords: [a_coords] = []
        closed_coords: {Coords: a_coords} = {}
        open_coords.append(a_coords(start, 0, get_h_cost(start, end, facing), None, facing))

        while len(open_coords) > 0:

            open_coords = list(sorted(open_coords, key=lambda x: (x.g_cost + x.h_cost, x.h_cost), reverse=False))
            current: a_coords = open_coords.pop(0)
            closed_coords[current.coords] = current

            if current.coords == end:
                trace: Optional[List[Coords]] = [current.coords]
                current_parent: Optional[a_coords] = current

                while current_parent.parent is not None:
                    current_parent = closed_coords[current_parent.parent]
                    trace.insert(0, current_parent.coords)

                return trace, int(current.h_cost + current.g_cost)

            neighbors: [Coords] = [add_coords(current.coords, (Coords(0, 1))),
                                   add_coords(current.coords, (Coords(0, -1))),
                                   add_coords(current.coords, (Coords(1, 0))),
                                   add_coords(current.coords, (Coords(-1, 0)))]

            for neighbor in neighbors:
                if neighbor in self.tiles.keys() and (self.tiles[neighbor].type == 'land' or self.tiles[
                    neighbor].type == 'menhir') and neighbor not in closed_coords.keys():
                    neighbor_direction: Coords = Coords(neighbor.x - current.coords.x, neighbor.y - current.coords.y)
                    neighbor_g_cost = (1 if neighbor_direction == current.facing.value else
                                       3 if add_coords(neighbor_direction, current.facing.value) == Coords(0, 0) else 2) \
                                      + current.g_cost
                    neighbor_h_cost = get_h_cost(neighbor, end, self.get_facing(neighbor_direction))

                    for coords in open_coords:
                        if coords.coords == neighbor:
                            open_coords.remove(coords)

                    open_coords.append(a_coords(neighbor,
                                                neighbor_g_cost,
                                                neighbor_h_cost,
                                                current.coords,
                                                self.get_facing(neighbor_direction)))

        trace: Optional[List[Coords]] = None
        return trace, INFINITY


POTENTIAL_CONTROLLERS = [
    DodgeController("ElvisNaProchach")
]

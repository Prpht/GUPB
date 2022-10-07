import random
from typing import NamedTuple, Optional, List, Tuple

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.coordinates import Coords, add_coords, sub_coords
from gupb.model.tiles import TileDescription
from gupb.model.characters import Facing, Action, ChampionDescription
from gupb.model.weapons import WeaponDescription

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

INFINITY: int = 99999999


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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DodgeController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # Gather information from seen tiles
        self.turn += 1
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
            if knowledge.visible_tiles[tile].type == 'menhir':
                self.target = Coords(tile[0], tile[1])

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

        for enemy in self.known_enemies.values():
            if enemy[2] < 2 and self.is_in_range(enemy[0]):
                return characters.Action.ATTACK

        if self.run > 0:
            self.run -= 1
            if self.tiles[self.forward(self.position, self.facing)].type in ('land', 'menhir'):
                return characters.Action.STEP_FORWARD

        if self.spinning_stage < 4:
            self.spinning_stage += 1
            return characters.Action.TURN_LEFT

        if self.target is not None:
            self.path = self.find_path(self.position, self.target, self.facing)[0]
            if len(self.path) > 0:
                self.path.pop(0)

        best_move: str = 'center'
        best_rating: int = -1
        for move in ('left', 'right', 'up', 'down', 'center'):
            if self.danger_ratings[move] > best_rating and self.move_possible(move):
                best_rating = self.danger_ratings[move]
                best_move = move

        if random.random() * 400 < self.turn and self.path is not None and len(self.path) > 0:
            direction = sub_coords(self.path[0], self.position)
            if direction == self.facing.value:
                self.path.pop(0)
                return characters.Action.STEP_FORWARD
            elif direction == self.facing.RIGHT.value:
                return characters.Action.TURN_LEFT
            else:
                return characters.Action.TURN_RIGHT

        if random.random() * 100 < best_rating:
            return random.choice(POSSIBLE_ACTIONS)

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

    @property
    def name(self) -> str:
        return f'DodgeController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY

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
        if self.weapon.name == 'bow':
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
                                    Coords(self.position.x - 1, self.position.y + 1)]
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

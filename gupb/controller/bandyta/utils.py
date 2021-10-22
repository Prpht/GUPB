from enum import Enum
from math import fabs
from typing import NamedTuple, List, Optional, Dict
import random

from gupb.model import characters, tiles
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords, sub_coords
from gupb.model.weapons import WeaponDescription


class Direction(Enum):
    S = Coords(0, 1)
    W = Coords(-1, 0)
    N = Coords(0, -1)
    E = Coords(1, 0)
    @staticmethod
    def get_all():
        return [Direction.S, Direction.W, Direction.N, Direction.E]

    @staticmethod
    def random():
        return random.choice(Direction.get_all())


class Weapon(Enum):
    bow = 'bow'
    bow_unloaded = 'bow_unloaded'
    bow_loaded = 'bow_loaded'
    axe = 'axe'
    sword = 'sword'
    knife = 'knife'
    amulet = 'amulet'

    @staticmethod
    def get_all():
        return [Weapon.bow, Weapon.axe, Weapon.sword, Weapon.knife, Weapon.amulet, Weapon.bow_loaded, Weapon.bow_unloaded]

    @staticmethod
    def from_string(string: str):
        for weapon in Weapon.get_all():
            if weapon.name == string:
                return weapon
        raise KeyError("Not known weapon with name ", string)


DirectedCoords = NamedTuple('DirectedCoords', [('coords', Coords), ('direction', Direction)])
Path = NamedTuple('Path', [('dest', Optional[str]), ('route', List[DirectedCoords])])


def get_rank_weapons() -> List[Weapon]:
    return [Weapon.bow_unloaded, Weapon.bow_loaded, Weapon.sword, Weapon.axe]


def rotate_cw(direction: Direction) -> Direction:
    return Direction(Coords(-direction.value.y, direction.value.x))


def rotate_ccw(direction: Direction) -> Direction:
    return Direction(Coords(direction.value.y, -direction.value.x))


def rotate_cw_dc(dc: DirectedCoords) -> DirectedCoords:
    return DirectedCoords(dc.coords, rotate_cw(dc.direction))


def rotate_ccw_dc(dc: DirectedCoords) -> DirectedCoords:
    return DirectedCoords(dc.coords, rotate_ccw(dc.direction))


def step_forward(dc: DirectedCoords) -> DirectedCoords:
    return DirectedCoords(dc.coords + dc.direction.value, dc.direction)


def get_direction(knowledge: ChampionKnowledge) -> Direction:
    for direction in Direction:
        if (knowledge.position + direction.value) in knowledge.visible_tiles:
            return direction


def get_distance(a: Coords, b: Coords) -> int:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** (1 / 2)


def left_walk(knowledge: ChampionKnowledge, direction: Direction) -> characters.Action:
    if knowledge.visible_tiles[knowledge.position + direction.value].type == 'land':
        return characters.Action.STEP_FORWARD
    else:
        return characters.Action.TURN_LEFT


def knife_attack_possible(my_coord: Coords, enemy_coord: Coords):
    sub = sub_coords(my_coord, enemy_coord)
    return (fabs(sub.x) == 1 and sub.y == 0) or (fabs(sub.y) == 1 and sub.x == 0)


def is_attack_possible(my_coord: Coords, enemy_coord: Coords, weapon: WeaponDescription) -> bool:
    sub = sub_coords(my_coord, enemy_coord)
    if weapon.name == Weapon.sword.value:
        return (fabs(sub.x) <= 3 and sub.y == 0) or (fabs(sub.y) <= 3 and sub.x == 0)
    elif weapon.name in [Weapon.bow_unloaded.value, Weapon.bow_loaded.value]:
        return (fabs(sub.x) <= 50 and sub.y == 0) or (fabs(sub.y) <= 50 and sub.x == 0)
    elif weapon.name == Weapon.axe.value:
        return fabs(sub.x) <= 1 and fabs(sub.y) <= 1
    elif weapon.name == Weapon.amulet.value:
        return fabs(sub.x) == 1 and fabs(sub.y) == 1
    else:
        knife_attack_possible(my_coord, enemy_coord)


def find_players(name: str, visible_tiles: Dict[Coords, tiles.TileDescription]):
    players: Dict[str, Coords] = {}
    for cords, tile in visible_tiles.items():
        if (tile.character is not None and
                tile.character.controller_name != name):
            players[tile.character.controller_name] = cords
    return players


def find_closest_player(name: str, knowledge: ChampionKnowledge):
    players = find_players(name, knowledge.visible_tiles)
    if len(players) == 0:
        return None

    distances = {}
    for player in players.items():
        distances[player[0]] = get_distance(knowledge.position, player[1])

    player = min(distances, key=distances.get)
    return player, players[player]


def find_target_player(name: str, knowledge: ChampionKnowledge, target: str):
    players = find_players(name, knowledge.visible_tiles)
    return (target, players[target]) if target in players.keys() else \
        (list(players.keys())[0], list(players.values())[0]) if len(players) > 0 else None


def find_menhir(visible_tiles: Dict[Coords, tiles.TileDescription]):
    for cords, tile in visible_tiles.items():
        if tile.type == 'menhir':
            return cords
    return None


def find_furthest_point(knowledge: ChampionKnowledge):
    furthest_point = knowledge.position
    for tile, desc in knowledge.visible_tiles:
        furthest_point = tile if \
            desc == 'land' and get_distance(knowledge.position, tile) > get_distance(knowledge.position,
                                                                                     furthest_point) else \
            furthest_point
    return furthest_point


def read_arena(arena_description: ArenaDescription):
    arena = {'land': [], 'wall': [], 'knife': [], 'sword': [], 'axe': [], 'bow': [], 'amulet': []}
    with open(f"resources/arenas/{arena_description.name}.gupb", "r") as f:
        y = 1
        for line in f.read().split("\n"):
            x = 1
            for char in line:
                key = None
                if char == '.':
                    key = 'land'
                elif char == '#':
                    key = 'wall'
                elif char == 'K':
                    key = Weapon.knife.value
                elif char == 'S':
                    key = Weapon.sword.value
                elif char == 'A':
                    key = Weapon.axe.value
                elif char == 'B':
                    key = Weapon.bow.value
                elif char == 'M':
                    key = Weapon.amulet.value
                if key is not None:
                    arena[key].append(Coords(x, y))
                x += 1
            y += 1
        arena['x_size'] = x
        arena['y_size'] = y
    return arena


def line_weapon_attack_coords(target: Coords, reach_number: int, filter_function, is_wall) -> list[DirectedCoords]:
    possible = []
    S = True
    N = True
    E = True
    W = True
    for i in range(reach_number):
        if S:
            c = sub_coords(target, Coords(0, 1 + i))
            if is_wall(c):
                S = False
            else:
                possible.append(DirectedCoords(c, Direction.S))
        if N:
            c = sub_coords(target, Coords(0, -1 - i))
            if is_wall(c):
                N = False
            else:
                possible.append(DirectedCoords(c, Direction.N))
        if E:
            c = sub_coords(target, Coords(1 + i, 0))
            if is_wall(c):
                E = False
            else:
                possible.append(DirectedCoords(c, Direction.E))
        if W:
            c = sub_coords(target, Coords(-1 - i, 0))
            if is_wall(c):
                W = False
            else:
                possible.append(DirectedCoords(c, Direction.W))

    return list(filter(filter_function, possible))


def axe_attack_coords(target: Coords, filter_function) -> list[DirectedCoords]:
    possible = []
    x = target.x
    y = target.y
    for i in range(3):
        possible.append(DirectedCoords(Coords(x - 1, y - 1 + i), Direction.E))
        possible.append(DirectedCoords(Coords(x - 1 + i, y - 1), Direction.S))
        possible.append(DirectedCoords(Coords(x + 1, y - 1 + i), Direction.W))
        possible.append(DirectedCoords(Coords(x - 1 + i, y + 1), Direction.N))
    return list(filter(filter_function, possible))


def amulet_attack_coords(target: Coords, filter_function) -> list[DirectedCoords]:
    x = target.x
    y = target.y
    possible = [
        DirectedCoords(Coords(x - 1, y - 1), None),
        DirectedCoords(Coords(x - 1, y + 1), None),
        DirectedCoords(Coords(x + 1, y - 1), None),
        DirectedCoords(Coords(x + 1, y + 1), None)
    ]
    return list(filter(filter_function, possible))


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD
]

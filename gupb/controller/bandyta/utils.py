from enum import Enum
from math import fabs
from typing import NamedTuple, List, Optional, Dict

from gupb.model import characters, tiles
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords, sub_coords
from gupb.model.weapons import WeaponDescription


class Direction(Enum):
    S = Coords(0, 1)
    W = Coords(-1, 0)
    N = Coords(0, -1)
    E = Coords(1, 0)


class Weapon(Enum):
    bow_unloaded = 'bow_unloaded'
    bow_loaded = 'bow_loaded'
    axe = 'axe'
    sword = 'sword'
    knife = 'knife'
    amulet = 'amulet'


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


def is_attack_possible(my_coord: Coords, enemy_coord: Coords, weapon: WeaponDescription) -> bool:
    sub = sub_coords(my_coord, enemy_coord)
    if weapon.name == Weapon.sword.value:
        return (fabs(sub.x) <= 3 and sub.y == 0) or (fabs(sub.y) <= 3 and sub.x == 0)
    elif weapon.name in [Weapon.bow_unloaded.value, Weapon.bow_loaded.value]:
        return (fabs(sub.x) <= 50 and sub.y == 0) or (fabs(sub.y) <= 50 and sub.x == 0)
    else:
        return (fabs(sub.x) == 1 and sub.y == 0) or (fabs(sub.y) == 1 and sub.x == 0)


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
            desc == 'land' and get_distance(knowledge.position, tile) > get_distance(knowledge.position, furthest_point) else \
            furthest_point
    return furthest_point


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD
]

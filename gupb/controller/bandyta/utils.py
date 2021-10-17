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


Path = NamedTuple('Path', [('dest', Optional[str]), ('route', List[Coords])])


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
    if weapon.name == 'sword':
        return (fabs(sub.x) <= 3 and sub.y == 0) or (fabs(sub.y) <= 3 and sub.x == 0)
    elif weapon.name == 'bow':
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
            desc is 'land' and get_distance(knowledge.position, tile) > get_distance(knowledge.position, furthest_point) else \
            furthest_point
    return furthest_point


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD
]

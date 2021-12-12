import random
from enum import Enum
from functools import reduce
from math import fabs
from typing import NamedTuple, List, Optional, Dict, Tuple

import gupb.controller.bandyta.bfs as bfs
from gupb.model import characters, tiles
from gupb.model.arenas import ArenaDescription
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords, sub_coords


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
        return [Weapon.bow,
                Weapon.axe,
                Weapon.sword,
                Weapon.knife,
                Weapon.amulet,
                Weapon.bow_loaded,
                Weapon.bow_unloaded]

    @staticmethod
    def from_string(string: str):
        for weapon in Weapon.get_all():
            if weapon.name == string:
                return weapon
        raise KeyError("Not known weapon with name ", string)

    @classmethod
    def has_value(cls, value):
        return value in cls._value2member_map_


class State:
    def __init__(self, name: str):
        self.name: str = name
        self.landscape_map: Dict[int, Dict[int, str]] = dict()
        self.item_map: Dict[Coords, Weapon] = dict()
        self.not_reachable_items: List[Coords] = list()
        self.path = Path(None, [])
        self.menhir: Optional[Coords] = None
        self.arena = None
        self.directed_position: Optional[DirectedCoords] = None
        self.weapon: Optional[Weapon] = None
        self.mist_coming: bool = False
        self.exploration_points: List[Tuple[int, int]] = []

    def reset(self):
        self.not_reachable_items = []
        self.menhir = None
        self.directed_position = None
        self.weapon = None
        self.mist_coming = False
        self.landscape_map = dict()
        self.arena = None
        self.item_map = dict()
        self.path = Path(None, [])


DirectedCoords = NamedTuple('DirectedCoords', [('coords', Coords), ('direction', Optional[Direction])])
Path = NamedTuple('Path', [('dest', Optional[str]), ('route', List[DirectedCoords])])


def get_rank_weapons() -> List[Weapon]:
    return [Weapon.bow, Weapon.bow_unloaded, Weapon.bow_loaded, Weapon.sword, Weapon.axe, Weapon.amulet]


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


def is_attack_possible(knowledge: ChampionKnowledge, weapon: Weapon, my_name: str) -> bool:
    players: Dict[str, Coords] = find_players(my_name, knowledge.visible_tiles)

    for enemy_coord in players.values():
        sub = sub_coords(knowledge.position, enemy_coord)
        if weapon == Weapon.sword and ((fabs(sub.x) <= 3 and sub.y == 0) or (fabs(sub.y) <= 3 and sub.x == 0)):
            return True
        elif weapon in [Weapon.bow_unloaded, Weapon.bow_loaded] and (
                (fabs(sub.x) <= 50 and sub.y == 0) or (fabs(sub.y) <= 50 and sub.x == 0)):
            return True
        elif weapon == Weapon.axe and (fabs(sub.x) <= 1 and fabs(sub.y) <= 1):
            return True
        elif weapon == Weapon.amulet and (fabs(sub.x) == 1 and fabs(sub.y) == 1):
            return True
        elif weapon == Weapon.knife and knife_attack_possible(knowledge.position, enemy_coord):
            return True
        else:
            continue

    return False


def safe_attack_possible(knowledge: ChampionKnowledge, weapon: Weapon, my_name: str) -> bool:
    return is_attack_possible(knowledge, weapon, my_name) and weapon not in [Weapon.knife, Weapon.amulet]


def find_players_with_health(name: str, visible_tiles: Dict[Coords, tiles.TileDescription]):
    players: Dict[str, (Coords, int)] = {}
    for cords, tile in visible_tiles.items():
        if (tile.character is not None and
                tile.character.controller_name != name):
            players[tile.character.controller_name] = (Coords(cords[0], cords[1]), tile.character.health)
    return players


def get_my_health(name: str, visible_tiles: Dict[Coords, tiles.TileDescription]) -> int:
    for cords, tile in visible_tiles.items():
        if tile.character is not None and tile.character.controller_name != name:
            return tile.character.health


def find_players(name: str, visible_tiles: Dict[Coords, tiles.TileDescription]) -> Dict[str, Coords]:
    players: Dict[str, Coords] = find_players_with_health(name, visible_tiles)
    players_without_health: Dict[str, Coords] = {}
    for key, value in players.items():
        players_without_health[key] = value[0]
    return players_without_health


def find_closest_player(name: str, knowledge: ChampionKnowledge):
    players = find_players(name, knowledge.visible_tiles)
    if len(players) == 0:
        return None

    distances = {}
    for player in players.items():
        distances[player[0]] = get_distance(knowledge.position, player[1])

    player = min(distances, key=distances.get)
    return player, players[player]


def find_target_player(name: str, knowledge: ChampionKnowledge, target: str) -> Tuple[str, Coords]:
    players = find_players(name, knowledge.visible_tiles)
    return (target, players[target]) if target in players.keys() else \
        (list(players.keys())[0], list(players.values())[0]) if len(players) > 0 else None


def safe_find_target_player(name: str, knowledge: ChampionKnowledge, target: str) -> Tuple[str, Coords]:
    players = find_players_with_health(name, knowledge.visible_tiles)
    my_health = get_my_health(name, knowledge.visible_tiles)
    return (target, players[target][0]) if target in players.keys() and players[target][1] <= my_health else \
        (list(players.keys())[0], list(players.values())[0][0]) if len(players) > 0 else None


def find_menhir(visible_tiles: Dict[Coords, tiles.TileDescription]):
    for cords, tile in visible_tiles.items():
        if tile.type == 'menhir':
            return cords
    return None


def find_furthest_point(landscape_map: Dict[int, Dict[int, str]], position: Coords):
    furthest_point = position
    for x, x_map in landscape_map.items():
        for y, tile_name in x_map.items():
            tile = Coords(x, y)
            furthest_point = (
                tile if
                tile_name == 'land' and get_distance(position, tile) > get_distance(position, furthest_point) else
                furthest_point)
    return furthest_point


def read_arena(arena_description: ArenaDescription):
    arena = {'land': [], 'wall': [], 'knife': [], 'sword': [], 'axe': [], 'bow': [], 'amulet': []}
    with open(f"resources/arenas/{arena_description.name}.gupb", "r") as f:
        y = 0
        for line in f.read().split("\n"):
            x = 0
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
                    if Weapon.has_value(key):
                        arena['land'].append(Coords(x, y))
                x += 1
            y += 1
    return arena


def parse_arena(arena):
    item_map = dict()
    landscape_map = dict()
    for sword in arena['sword']:
        item_map[sword] = Weapon.sword
    for axe in arena['axe']:
        item_map[axe] = Weapon.axe
    for bow in arena['bow']:
        item_map[bow] = Weapon.bow
    for amulet in arena['amulet']:
        item_map[amulet] = Weapon.amulet
    for knife in arena['knife']:
        item_map[knife] = Weapon.knife
    for land in arena['land']:
        if land[0] not in landscape_map:
            landscape_map[land[0]] = {}
        landscape_map[land[0]][land[1]] = 'land'

    return item_map, landscape_map


def extract_pytagorian_nearest(state: State) -> DirectedCoords:
    my_position = state.directed_position.coords

    def square_dist(x: Tuple[int, int]):
        return (x[0] - my_position.x) ** 2 + (x[1] - my_position.y) ** 2

    nearest = state.exploration_points[0]
    for point in state.exploration_points:
        if square_dist(nearest) > square_dist(point):
            nearest = point

    state.exploration_points.remove(nearest)

    return DirectedCoords(Coords(nearest[0], nearest[1]), None)


def nearest_coord_to_attack(
        state: State,
        enemies_positions: List[Coords],
        my_position: Coords,
        weapon: Weapon) -> DirectedCoords:
    possible = possible_attack_coords(enemies_positions, weapon, state)

    def remove_front_coords(c: DirectedCoords) -> bool:
        return c.coords in reduce(list.__add__, [
            [sub_coords(enemy_position, Direction.S.value),
             sub_coords(enemy_position, Direction.N.value),
             sub_coords(enemy_position, Direction.E.value),
             sub_coords(enemy_position, Direction.W.value)]
            for enemy_position in enemies_positions])

    possible = list(filter(remove_front_coords, possible))
    min_distance = 10000
    best_coord = None
    for p in possible:
        distance = get_distance(my_position, p.coords)
        if distance < min_distance:
            min_distance = distance
            best_coord = p
    if best_coord.direction is None:
        best_coord = DirectedCoords(best_coord.coords, Direction.random())  # maybe better tactic for amulet
    return best_coord


def possible_attack_coords(enemies_positions: List[Coords], weapon: Weapon, state: State) -> List[DirectedCoords]:
    coords2attack: List[List[DirectedCoords]] = []
    for enemy_position in enemies_positions:
        if weapon == Weapon.knife:
            coords2attack.append(line_weapon_attack_coords(enemy_position, 1, state))
        elif weapon in [Weapon.bow, Weapon.bow_unloaded, Weapon.bow_loaded]:
            coords2attack.append(line_weapon_attack_coords(enemy_position, 50, state))
        elif weapon == Weapon.sword:
            coords2attack.append(line_weapon_attack_coords(enemy_position, 3, state))
        elif weapon == Weapon.axe:
            coords2attack.append(axe_attack_coords(enemy_position, state))
        elif weapon == Weapon.amulet:
            coords2attack.append(amulet_attack_coords(enemy_position, state))
        else:
            raise KeyError(f"Not known weapon {weapon.name}.")
    return reduce(list.__add__, coords2attack)


def is_wall(state: State, coords: Coords) -> bool:
    return coords in state.arena['wall']


def is_valid_coords(state: State, coords: DirectedCoords) -> bool:
    c = coords.coords
    return c in state.arena['land'] or c == state.menhir


def line_weapon_attack_coords(target: Coords, reach_number: int, state: State) -> List[DirectedCoords]:
    possible: List[DirectedCoords] = []
    do_search_map: Dict[Direction, bool] = {
        Direction.S: True,
        Direction.N: True,
        Direction.E: True,
        Direction.W: True
    }

    # start = 2 if reach_number > 1 else 1

    for i in range(1, reach_number):
        for direction, do_search in do_search_map.items():
            if do_search:
                c = target + Coords(i * direction.value.x, i * direction.value.y)
                if is_wall(state, c):
                    do_search_map[direction] = False
                else:
                    possible.append(DirectedCoords(c, direction))

    return list(filter(lambda coords: is_valid_coords(state, coords), possible))


def axe_attack_coords(target: Coords, state: State) -> List[DirectedCoords]:
    possible = []
    x = target.x
    y = target.y
    for i in range(3):
        possible.append(DirectedCoords(Coords(x - 1, y - 1 + i), Direction.E))
        possible.append(DirectedCoords(Coords(x - 1 + i, y - 1), Direction.S))
        possible.append(DirectedCoords(Coords(x + 1, y - 1 + i), Direction.W))
        possible.append(DirectedCoords(Coords(x - 1 + i, y + 1), Direction.N))
    return list(filter(lambda coords: is_valid_coords(state, coords), possible))


def amulet_attack_coords(target: Coords, state: State) -> List[DirectedCoords]:
    x = target.x
    y = target.y
    possible = [
        DirectedCoords(Coords(x - 1, y - 1), None),
        DirectedCoords(Coords(x - 1, y + 1), None),
        DirectedCoords(Coords(x + 1, y - 1), None),
        DirectedCoords(Coords(x + 1, y + 1), None)
    ]
    return list(filter(lambda coords: is_valid_coords(state, coords), possible))


def is_mist_coming(knowledge: ChampionKnowledge):
    for cords, tile in knowledge.visible_tiles.items():
        for effect in tile.effects:
            if effect.type == 'mist':
                return True
    return False


def get_my_weapon(visible_tiles: Dict[Coords, tiles.TileDescription], name: str):
    for cords, tile in visible_tiles.items():
        if tile.character is not None and tile.character.controller_name == name:
            return Weapon.from_string(tile.character.weapon.name)


def update_item_map(knowledge: ChampionKnowledge, item_map: Dict[Coords, Weapon]) -> Dict[Coords, Weapon]:
    item_map = item_map.copy()

    for cords, tile in knowledge.visible_tiles.items():
        if tile.loot is not None:
            item_map[cords] = Weapon.from_string(tile.loot.name)

        if tile.loot is None and cords in item_map:
            del item_map[cords]

    return item_map


def get_weapon_path(
        dc: DirectedCoords,
        item_map: Dict[Coords, Weapon],
        not_reachable_items: List[Coords],
        landscape_map: Dict[int, Dict[int, str]],
        preferred_weapons: List[Weapon]):
    for ranked_weapon in preferred_weapons:
        weapon_list: List[Tuple[Coords, int]] = []

        for coords, weapon in item_map.items():
            if weapon.name == ranked_weapon.name and coords not in not_reachable_items:
                weapon_list.append((coords, get_distance(dc.coords, coords)))

        if len(weapon_list) > 0:
            sorted_by_distance = sorted(weapon_list, key=lambda tup: tup[1])
            for coords, distance in sorted_by_distance:
                path = bfs.find_path(dc, DirectedCoords(coords, None), landscape_map)
                if len(path) > 0:
                    return Path('weapon', path)
                else:
                    not_reachable_items.append(coords)
    return Path('', [])


def move_on_path(state: State, dc: DirectedCoords) -> characters.Action:
    next_node = state.path.route.pop(0)

    if dc.direction is not next_node.direction:
        return characters.Action.TURN_RIGHT if \
            rotate_cw_dc(dc).direction is next_node.direction else \
            characters.Action.TURN_LEFT
    else:
        return characters.Action.STEP_FORWARD


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD
]

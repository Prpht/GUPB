import random
import numpy as np

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action, Facing
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

menhir_location = Coords(9, 9)

facings = {
    "U": ["L", "R"], "R": ["U", "D"], "D": ["R", "L"], "L": ["D", "U"]
}
forwards = {
    "U": np.array([-1, 0]), "R": np.array([0, 1]), "D": np.array([1, 0]), "L": np.array([0, -1])
}
facing_to_letter = {
    Facing.UP: "U",Facing.RIGHT: "R", Facing.DOWN: "D", Facing.LEFT: "L"
}
weapons_knowledge = {
    (1, 1): 'A', (1, 2): 'A', (2, 1): 'A',
    (1, 16): 'B', (1, 17): 'B', (2, 17): 'B',
    (16, 1): 'S', (17, 1): 'S', (17, 2): 'S',
    (16, 17): 'M', (17, 16): 'M', (17, 17): 'M',
}
weapons_to_letter = {
    Knife: "K", Axe: "A", Bow: "B", Sword: "S", Amulet: "M"
}
weapons_name_to_letter = {
    'knife': "K", 'axe': "A", 'bow_loaded': "B", 'bow_unloaded': "B", 'sword': "S", 'amulet': "M"
}


def find_path(adjacency_dict, c_from, c_to):
    accessed_from = np.zeros(len(adjacency_dict), dtype=np.int32)
    accessed_from[c_from - 1] = -1
    stack = [c_from]

    while stack:
        node_from = stack.pop(0)
        for node_to in adjacency_dict[node_from]:
            if accessed_from[node_to - 1] == 0:
                accessed_from[node_to - 1] = node_from
                stack.append(node_to)

    path = []
    step = c_to
    while step != -1:
        path.append(step)
        step = accessed_from[path[-1] - 1]

    return path[::-1]


def pathfinding_next_move(position, facing, next_cluster):
    stack = [(position, facing)]
    visited = {stack[0]: None}
    is_found = False
    pos_found = None

    while stack and not is_found:
        pos, face = stack.pop(0)

        for new_pos, new_face in list(zip([pos, pos], facings[face])) + [(tuple(forwards[face] + pos), face)]:

            if clusters[new_pos] and (new_pos, new_face) not in visited:
                visited[(new_pos, new_face)] = (pos, face)
                stack.append((new_pos, new_face))

                if clusters[new_pos] == next_cluster:
                    is_found = True
                    pos_found = (new_pos, new_face)

    path = []
    step = pos_found
    while step is not None:
        path.append(step)
        step = visited[path[-1]]

    path = path[::-1]

    f_0 = path[0][1]
    f_1 = path[1][1]

    if f_0 == f_1:
        return Action.STEP_FORWARD
    elif f_1 == facings[facing][0]:
        return Action.TURN_LEFT
    elif f_1 == facings[facing][1]:
        return Action.TURN_RIGHT


def pathfinding_next_move_in_cluster(position, facing, target_pos):
    stack = [(position, facing)]
    visited = {stack[0]: None}
    is_found = False
    pos_found = None

    while stack and not is_found:
        pos, face = stack.pop(0)

        for new_pos, new_face in list(zip([pos, pos], facings[face])) + [(tuple(forwards[face] + pos), face)]:

            if clusters[new_pos] and (new_pos, new_face) not in visited:
                visited[(new_pos, new_face)] = (pos, face)
                stack.append((new_pos, new_face))

                if new_pos == target_pos:
                    is_found = True
                    pos_found = (new_pos, new_face)

    path = []
    step = pos_found
    while step is not None:
        path.append(step)
        step = visited[path[-1]]

    path = path[::-1]

    f_0 = path[0][1]
    f_1 = path[1][1]

    if f_0 == f_1:
        return Action.STEP_FORWARD
    elif f_1 == facings[facing][0]:
        return Action.TURN_LEFT
    elif f_1 == facings[facing][1]:
        return Action.TURN_RIGHT


def analyze_weapons_on_map(weapons_knowledge):
    stack_axe = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'A']
    stack_bow = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'B']
    stack_sword = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'S']
    stack_amulet = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'M']

    def get_dists(stack, base=0):
        dists = 99 * np.ones([19, 19], dtype=np.int32)

        for pos in stack:
            dists[pos] = base

        while stack:
            pos = stack.pop(0)

            for dxdy in np.array([[-1, 0], [1, 0], [0, -1], [0, 1]]):
                new_pos = tuple(pos + dxdy)
                if clusters[new_pos] and dists[pos] + 1 < dists[new_pos]:
                    dists[new_pos] = dists[pos] + 1
                    stack.append(new_pos)

        return dists

    dists_axe = get_dists(stack_axe)
    dists_bow = get_dists(stack_bow, base=-1)  # Preferred weapon
    dists_sword = get_dists(stack_sword)
    dists_amulet = get_dists(stack_amulet)

    closest_weapon = np.argmin(np.stack(
        [98 * np.ones([19, 19], dtype=np.int32),
         dists_axe, dists_bow, dists_sword, dists_amulet,
        ], axis=-1), axis=-1)

    closest_weapon = np.where(
        closest_weapon == 0,
        "-",
        np.where(
            closest_weapon < 3,
            np.where(closest_weapon == 1, "A", "B"),
            np.where(closest_weapon == 3, "S", "M")
        )
    )
    return closest_weapon


def find_closest_weapon(weapons_knowledge, position, weapon_letter):
    closest_weapon_position = (menhir_location.y, menhir_location.x)
    closest_weapon_distance = 9999

    for pos in [pos for pos in weapons_knowledge if weapons_knowledge[pos] == weapon_letter]:
        dist = len(find_path(adj, clusters[(position.y, position.x)], clusters[pos]))
        if dist < closest_weapon_distance:
            closest_weapon_distance = dist
            closest_weapon_position = pos

    return Coords(x=closest_weapon_position[1], y=closest_weapon_position[0])


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
        self.weapons_knowledge = weapons_knowledge
        self.closest_weapon = None
        self.mist_spotted = False
        self.panic_mode = 0
        self.touched_by_mist = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Spejson):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.move_number += 1
        self.panic_mode -= 1
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        available_actions = POSSIBLE_ACTIONS.copy()

        me = knowledge.visible_tiles[position].character
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon

        to_del = []
        for pos in self.weapons_knowledge:
            pos = Coords(x=pos[1], y=pos[0])
            if pos in visible_tiles:
                loot = visible_tiles[pos].loot
                if loot is None:
                    to_del += [(pos.y, pos.x)]
                else:
                    self.weapons_knowledge[(pos.y, pos.x)] = weapons_name_to_letter[loot.name]

        if (position.y, position.x) in self.weapons_knowledge:
            to_del += [(position.y, position.x)]

        for pos in to_del:
            del self.weapons_knowledge[pos]

        for tile_coord in visible_tiles:
            tile = visible_tiles[tile_coord]
            if (tile_coord[1], tile_coord[0]) not in self.weapons_knowledge and tile.loot is not None \
                    and tile.loot.name != 'knife':
                self.weapons_knowledge[(tile_coord[1], tile_coord[0])] = weapons_name_to_letter[tile.loot.name]

        self.closest_weapon = analyze_weapons_on_map(self.weapons_knowledge)

        if not self.menhir_found:
            for tile_coord in visible_tiles:
                if visible_tiles[tile_coord].type == 'menhir':
                    self.target = Coords(tile_coord[0], tile_coord[1])
                    self.menhir_found = True

        if not self.mist_spotted:
            for tile_coord in visible_tiles:
                if "mist" in list(map(lambda x: x.type, visible_tiles[tile_coord].effects)):
                    self.target = menhir_location
                    self.mist_spotted = True

        if self.panic_mode <= 0 and self.weapon.name == 'knife':
            self.target = find_closest_weapon(
                self.weapons_knowledge, position, self.closest_weapon[(position.y, position.x)])
            if self.target == position:
                self.target = menhir_location
                return Action.STEP_FORWARD
            self.jitter = 0
        elif self.panic_mode <= 0:
            self.target = menhir_location
            self.jitter = 0 if self.touched_by_mist else 10

        bad_neighborhood_factor = 0
        if not self.mist_spotted:
            for i in range(-3, 4):
                for j in range(-3, 4):
                    pos = Coords(x=position.x + i, y=position.y + j)
                    if pos in visible_tiles:
                        if visible_tiles[pos].character is not None:
                            bad_neighborhood_factor += 1
        else:
            for i in range(-2, 3):
                for j in range(-2, 3):
                    pos = Coords(x=position.x + i, y=position.y + j)
                    if pos in visible_tiles:
                        if "mist" in list(map(lambda x: x.type, visible_tiles[pos].effects)):
                            self.touched_by_mist = True

        if bad_neighborhood_factor > 2 and self.panic_mode < 2:
            self.panic_mode = 6
            for _ in range(50):  # Just to avoid while True lol
                rx, ry = np.random.randint(19, size=[2])
                if clusters[(ry, rx)]:
                    self.target = Coords(x=rx, y=ry)
                    break

        # Positions in reach
        in_reach = weapons[self.weapon.name].cut_positions(current_arena.terrain, position, self.facing)
        if self.weapon.name != "bow_unloaded":
            for pos in in_reach:
                if pos in visible_tiles and visible_tiles[pos].character is not None:
                    return Action.ATTACK

        if self.weapon.name == "bow_unloaded":
            return Action.ATTACK
        available_actions = [x for x in available_actions if x not in [Action.ATTACK]]

        # Rule out stupid moves
        next_block = position + self.facing.value
        if next_block in visible_tiles:
            if visible_tiles[next_block].type in ['sea', 'wall'] or visible_tiles[next_block].character is not None:
                available_actions = [x for x in available_actions if x not in [Action.STEP_FORWARD]]

        distance_from_target = self.target - position
        distance_from_target = distance_from_target.x ** 2 + distance_from_target.y ** 2

        if distance_from_target < self.jitter and self.target == menhir_location:
            if Action.STEP_FORWARD in available_actions:
                if np.random.rand() < 0.7:
                    return Action.STEP_FORWARD

            left_ahead = self.target - (position + self.facing.turn_left().value)
            left_ahead = left_ahead.x ** 2 + left_ahead.y ** 2
            right_ahead = self.target - (position + self.facing.turn_right().value)
            right_ahead = right_ahead.x ** 2 + right_ahead.y ** 2

            if left_ahead < right_ahead:
                return Action.TURN_LEFT if np.random.rand() < 0.7 else Action.TURN_RIGHT
            else:
                return Action.TURN_RIGHT if np.random.rand() < 0.7 else Action.TURN_LEFT

        else:
            cluster_path_to_target = find_path(
                adj, clusters[(position.y, position.x)], clusters[(self.target.y, self.target.x)])

            if len(cluster_path_to_target) > 1:
                move = pathfinding_next_move(
                    (position.y, position.x), facing_to_letter[self.facing], cluster_path_to_target[1])
                available_actions = (
                    ([move] if move in available_actions else [])
                    + ([Action.ATTACK] if Action.ATTACK in available_actions else [])
                )
            else:
                move = pathfinding_next_move_in_cluster(
                    (position.y, position.x), facing_to_letter[self.facing], (self.target.y, self.target.x))
                available_actions = (
                    ([move] if move in available_actions else [])
                    + ([Action.ATTACK] if Action.ATTACK in available_actions else [])
                )

        if len(available_actions) == 0:
            return random.choice([Action.ATTACK, Action.TURN_LEFT])

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
        self.weapons_knowledge = weapons_knowledge
        self.closest_weapon = None
        self.mist_spotted = False
        self.panic_mode = 0
        self.touched_by_mist = False

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK


POTENTIAL_CONTROLLERS = [
    Spejson("Spejson"),
]

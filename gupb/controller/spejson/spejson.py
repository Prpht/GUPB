import random
import os
import numpy as np

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Axe, Bow, Sword, Amulet

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

facings = {
    "U": ["L", "R"], "R": ["U", "D"], "D": ["R", "L"], "L": ["D", "U"]
}
forwards = {
    "U": np.array([-1, 0]), "R": np.array([0, 1]), "D": np.array([1, 0]), "L": np.array([0, -1])
}
facing_to_letter = {
    Facing.UP: "U",Facing.RIGHT: "R", Facing.DOWN: "D", Facing.LEFT: "L"
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


def pathfinding_next_move(position, facing, next_cluster, clusters):
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
    if len(path) < 2:
        return None

    f_0 = path[0][1]
    f_1 = path[1][1]

    if f_0 == f_1:
        return Action.STEP_FORWARD
    elif f_1 == facings[facing][0]:
        return Action.TURN_LEFT
    elif f_1 == facings[facing][1]:
        return Action.TURN_RIGHT


def pathfinding_next_move_in_cluster(position, facing, target_pos, clusters):
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
    if len(path) < 2:
        return None

    f_0 = path[0][1]
    f_1 = path[1][1]

    if f_0 == f_1:
        return Action.STEP_FORWARD
    elif f_1 == facings[facing][0]:
        return Action.TURN_LEFT
    elif f_1 == facings[facing][1]:
        return Action.TURN_RIGHT


def analyze_weapons_on_map(weapons_knowledge, clusters):
    stack_axe = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'A']
    stack_bow = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'B']
    stack_sword = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'S']
    stack_amulet = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'M']

    def get_dists(stack, base=0):
        dists = 9999 * np.ones(clusters.shape, dtype=np.int32)

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
        [9998 * np.ones(clusters.shape, dtype=np.int32),
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


def find_closest_weapon(weapons_knowledge, position, weapon_letter, clusters, adj, menhir_location):
    closest_weapon_position = (menhir_location.y, menhir_location.x)
    closest_weapon_distance = 9999

    for pos in [pos for pos in weapons_knowledge if weapons_knowledge[pos] == weapon_letter]:
        dist = len(find_path(adj, clusters[(position.y, position.x)], clusters[pos]))
        if dist < closest_weapon_distance:
            closest_weapon_distance = dist
            closest_weapon_position = pos

    return Coords(x=closest_weapon_position[1], y=closest_weapon_position[0])


def analyze_map(arena_name):
    arena_filepath = os.path.join('resources', 'arenas', f'{arena_name}.gupb')

    txt = []

    with open(arena_filepath, mode='r') as file:
        for line in file:
            txt += [line.strip("\n")]

    island_ar = np.array([list(i) for i in txt])

    height = island_ar.shape[0]
    width = island_ar.shape[1]

    traversable = np.logical_and(island_ar != '=', island_ar != '#').astype(np.int32)

    start = ((height - 1) // 2, (width - 1) // 2)
    best_pos = None
    best_dist = 9999

    for _ in range(150):
        pos = (start[0] + np.random.randint(-8, 9), start[1] + np.random.randint(-8, 9))
        if island_ar[pos] == '.':
            dist = (start[0] - pos[0]) ** 2 + (start[1] - pos[1]) ** 2
            if dist < best_dist:
                best_pos = pos
                best_dist = dist

    start = best_pos

    # Initial cluster calculation by BFS in BFS
    clusters = np.zeros([height, width], dtype=np.int32)
    current_cluster = 1
    stack = [start]
    directions = np.array([[-1, 0], [1, 0], [0, -1], [0, 1]])

    while stack:
        pos = stack.pop(0)

        if clusters[pos] == 0:
            clusters[pos] = current_cluster

            substack = [pos]
            i = 0
            while i < 6 and substack:
                i += 1
                pos = substack.pop(0)

                for dxdy in directions:
                    new_pos = tuple(pos + dxdy)
                    if traversable[new_pos] and clusters[new_pos] == 0:
                        clusters[new_pos] = current_cluster
                        substack.append(new_pos)

            for pos in substack:
                clusters[pos] = 0

            stack.extend(substack)
            current_cluster += 1

    # Get derivable cluster information in valid cells
    c = clusters.reshape(-1)
    xs = np.tile(np.arange(width), [width, 1]).reshape(-1)
    ys = np.tile(np.arange(height).reshape(-1, 1), [1, height]).reshape(-1)

    xs = xs[c > 0]
    ys = ys[c > 0]
    c = c[c > 0]

    counts = np.zeros(np.max(c), dtype=np.int32)
    np.add.at(counts, c - 1, 1)

    proto_x = np.zeros(np.max(c), dtype=np.int32)
    proto_y = np.zeros(np.max(c), dtype=np.int32)
    np.put(proto_x, c - 1, xs)
    np.put(proto_y, c - 1, ys)

    # Merge tiny clusters into neighbors
    for i in np.arange(counts.shape[0])[counts < 5]:
        stack = [(proto_y[i], proto_x[i])]

        j = 0
        c_found = 0

        while j < len(stack):
            pos = stack[j]

            for dxdy in directions:
                new_pos = tuple(pos + dxdy)

                if clusters[new_pos] == i + 1:
                    if new_pos not in stack:
                        stack.append(new_pos)
                else:
                    if c_found == 0:
                        c_found = clusters[new_pos]

            j += 1

        counts[i] = 0
        for pos in stack:
            clusters[pos] = c_found

    clusters = np.r_[0, np.cumsum(counts > 0) * (counts > 0)][clusters]

    # Get derivable cluster information in valid cells again (final)
    c = clusters.reshape(-1)
    xs = np.tile(np.arange(width), [width, 1]).reshape(-1)
    ys = np.tile(np.arange(height).reshape(-1, 1), [1, height]).reshape(-1)

    xs = xs[c > 0]
    ys = ys[c > 0]
    c = c[c > 0]

    counts = np.zeros(np.max(c), dtype=np.int32)
    np.add.at(counts, c - 1, 1)

    proto_x = np.zeros(np.max(c), dtype=np.int32)
    proto_y = np.zeros(np.max(c), dtype=np.int32)
    np.put(proto_x, c - 1, xs)
    np.put(proto_y, c - 1, ys)

    # Get neighbors pairs and construct adjacency dictionary
    neighbors = np.concatenate([
        np.stack([clusters[:, 1:], clusters[:, :-1]], axis=-1).reshape(-1, 2),
        np.stack([clusters[1:, :], clusters[:-1, :]], axis=-1).reshape(-1, 2)
    ], axis=0)

    neighbors = neighbors[neighbors[:, 0] != neighbors[:, 1]]
    neighbors = neighbors[np.logical_and(neighbors[:, 0] != 0, neighbors[:, 1] != 0)]
    neighbors = list(
        set(map(lambda x: tuple(x), np.vstack([neighbors, neighbors[:, ::-1]]).tolist())))

    adj = {i: [] for i in range(1, counts.shape[0] + 1)}
    for c_from, c_to in neighbors:
        adj[c_from].append(c_to)

    # Create initial weapons knowledge dict
    weapons_knowledge = {}
    for i in range(height):
        for j in range(width):
            if island_ar[i, j] == 'A':
                weapons_knowledge[(i, j)] = 'A'
            elif island_ar[i, j] == 'B':
                weapons_knowledge[(i, j)] = 'B'
            elif island_ar[i, j] == 'S':
                weapons_knowledge[(i, j)] = 'S'
            elif island_ar[i, j] == 'M':
                weapons_knowledge[(i, j)] = 'M'

    return start, clusters, adj, weapons_knowledge


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Spejson(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.position = None
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.menhir_location = Coords(16, 16)
        self.target = Coords(16, 16)
        self.jitter = 0
        self.weapons_knowledge = None
        self.closest_weapon = None
        self.mist_spotted = False
        self.panic_mode = 0
        self.touched_by_mist = False
        self.clusters = None
        self.adj = None
        self.terrain = None
        self.latest_states = []

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
        self.position = position
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon

        self.latest_states = (self.latest_states + [(self.position, self.facing)])[-5:]
        if len(self.latest_states) >= 5 and (
                self.latest_states[0] == self.latest_states[1] == self.latest_states[2]
                == self.latest_states[3] == self.latest_states[4]
        ):
            self.panic_mode = 6
            for _ in range(50):  # Just to avoid while True lol
                rx, ry = np.random.randint(32, size=[2])
                if self.clusters[(ry, rx)]:
                    self.target = Coords(x=rx, y=ry)
                    break

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

        self.closest_weapon = analyze_weapons_on_map(self.weapons_knowledge, self.clusters)

        if not self.menhir_found:
            for tile_coord in visible_tiles:
                if visible_tiles[tile_coord].type == 'menhir':
                    self.target = Coords(tile_coord[0], tile_coord[1])
                    self.menhir_found = True
                    self.menhir_location = self.target

        if not self.mist_spotted:
            for tile_coord in visible_tiles:
                if "mist" in list(map(lambda x: x.type, visible_tiles[tile_coord].effects)):
                    self.target = self.menhir_location
                    self.mist_spotted = True

        if self.panic_mode <= 0 and self.weapon.name == 'knife':
            self.target = find_closest_weapon(
                self.weapons_knowledge, position, self.closest_weapon[(position.y, position.x)], self.clusters, self.adj, self.menhir_location)
            if self.target == position:
                self.target = self.menhir_location
                return Action.STEP_FORWARD
            self.jitter = 0
        elif self.panic_mode <= 0:
            self.target = self.menhir_location
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
                rx, ry = np.random.randint(32, size=[2])
                if self.clusters[(ry, rx)]:
                    self.target = Coords(x=rx, y=ry)
                    break

        # Positions in reach
        in_reach = weapons[self.weapon.name].cut_positions(self.terrain, position, self.facing)
        if self.weapon.name != "bow_unloaded":
            for pos in in_reach:
                if pos in visible_tiles and visible_tiles[pos].character is not None:
                    self.latest_states += ["att"]
                    return Action.ATTACK

        if self.weapon.name == "bow_unloaded":
            self.latest_states += ["att"]
            return Action.ATTACK
        available_actions = [x for x in available_actions if x not in [Action.ATTACK]]

        # Rule out stupid moves
        next_block = position + self.facing.value
        if next_block in visible_tiles:
            if visible_tiles[next_block].type in ['sea', 'wall'] or visible_tiles[next_block].character is not None:
                available_actions = [x for x in available_actions if x not in [Action.STEP_FORWARD]]

        distance_from_target = self.target - position
        distance_from_target = distance_from_target.x ** 2 + distance_from_target.y ** 2

        if distance_from_target < self.jitter and self.target == self.menhir_location:
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
                self.adj, self.clusters[(position.y, position.x)], self.clusters[(self.target.y, self.target.x)])

            if len(cluster_path_to_target) > 1:
                move = pathfinding_next_move(
                    (position.y, position.x), facing_to_letter[self.facing], cluster_path_to_target[1], self.clusters)
                if move is None:
                    self.panic_mode = 8
                    for _ in range(50):  # Just to avoid while True lol
                        rx, ry = np.random.randint(32, size=[2])
                        if self.clusters[(ry, rx)]:
                            self.target = Coords(x=rx, y=ry)
                            break
                else:
                    available_actions = (
                        ([move] if move in available_actions else [])
                        + ([Action.ATTACK] if Action.ATTACK in available_actions else [])
                    )
            else:
                move = pathfinding_next_move_in_cluster(
                    (position.y, position.x), facing_to_letter[self.facing], (self.target.y, self.target.x), self.clusters)
                if move is None:
                    self.panic_mode = 8
                    for _ in range(50):  # Just to avoid while True lol
                        rx, ry = np.random.randint(32, size=[2])
                        if self.clusters[(ry, rx)]:
                            self.target = Coords(x=rx, y=ry)
                            break
                else:
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
        self.position = None
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.menhir_location = Coords(16, 16)
        self.closest_weapon = None
        self.mist_spotted = False
        self.panic_mode = 0
        self.touched_by_mist = False
        self.latest_states = []

        self.arena_name = arena_description.name
        self.terrain = arenas.Arena.load(self.arena_name).terrain
        start, clusters, adj, weapons_knowledge = analyze_map(self.arena_name)
        self.target = Coords(x=start[1], y=start[0])
        self.menhir_location = self.target
        self.clusters = clusters
        self.adj = adj
        self.weapons_knowledge = weapons_knowledge

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK


POTENTIAL_CONTROLLERS = [
    Spejson("Spejson"),
]

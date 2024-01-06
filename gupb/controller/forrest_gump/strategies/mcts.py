from copy import deepcopy
from typing import Optional

import numpy as np

from gupb.controller.forrest_gump.strategies import Strategy
from gupb.controller.forrest_gump.utils import CharacterInfo, manhattan_distance_to, next_facing, next_step
from gupb.model import tiles, characters, coordinates, arenas, weapons


ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK,
    characters.Action.DO_NOTHING
]

PROBS = {
    'AlphaGUPB': np.array([0.408, 0.064, 0.487, 0.1, 0.1, 0.1, 0.026, 0.016], dtype=np.float64),
    'Ancymon': np.array([0.085, 0.157, 0.547, 0.009, 0.065, 0.072, 0.066, 0.1], dtype=np.float64),
    'Aragorn': np.array([0.078, 0.182, 0.356, 0.130, 0.097, 0.1, 0.057, 0.1], dtype=np.float64),
    'AresControllerNike': np.array([0.138, 0.171, 0.515, 0.048, 0.039, 0.042, 0.047, 0.1], dtype=np.float64),
    'Batman': np.array([0.213, 0.321, 0.125, 0.014, 0.015, 0.015, 0.014, 0.282], dtype=np.float64),
    'Bob': np.array([0.1, 0.487, 0.485, 0.1, 0.1, 0.1, 0.018, 0.01], dtype=np.float64),
    'Cynamonka': np.array([0.046, 0.073, 0.150, 0.1, 0.360, 0.362, 0.008, 0.1], dtype=np.float64),
    'Forrest Gump': np.array([0.2, 0.2, 0.2, 0.2, 0.2, 0.2, 0.3, 0.1], dtype=np.float64),
    'Frog': np.array([0.125, 0.125, 0.125, 0.125, 0.125, 0.125, 0.125, 0.125], dtype=np.float64),
    'Kot i Pat': np.array([0.089, 0.289, 0.472, 0.072, 0.1, 0.1, 0.066, 0.011], dtype=np.float64),
    'LittlePonny': np.array([0.166, 0.119, 0.632, 0.1, 0.1, 0.1, 0.083, 0.1], dtype=np.float64),
    'Mongolek': np.array([0.199, 0.126, 0.590, 0.1, 0.1, 0.1, 0.086, 0.1], dtype=np.float64),
    'RandomControllerAlice': np.array([0.25, 0.25, 0.25, 0., 0., 0., 0.25, 0.], dtype=np.float64),
    'RecklessRoamingDancingDruid_R2D2': np.array([0.196, 0.276, 0.300, 0.056, 0.049, 0.047, 0.077, 0.1], dtype=np.float64),
    'Roger_1': np.array([0.094, 0.191, 0.525, 0.020, 0.050, 0.049, 0.072, 0.1], dtype=np.float64),
    'krombopulos-michael': np.array([0.108, 0.120, 0.301, 0.013, 0.162, 0.166, 0.073, 0.057], dtype=np.float64),
}

WEAPONS = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    'bow_loaded': weapons.Bow,
    'bow_unloaded': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}

WEAPONS_CUT = {
    'knife': 2,
    'sword': 2,
    'bow': 1.5,
    'bow_loaded': 3,
    'bow_unloaded': 0,
    'axe': 3,
    'amulet': 2
}


class Node:
    def __init__(self, state: list, action: Optional[characters.Action], parent: Optional['Node']) -> None:
        self.state = state
        self.action = action
        self.parent = parent
        self.children = []
        self.N = 0
        self.T = 0


def next_state_to_action(old_state: list, new_state: list, player_index: int, arena: arenas.Arena) -> characters.Action:
    old_facing, new_facing = old_state[player_index]['facing'], new_state[player_index]['facing']
    old_position, new_position = old_state[player_index]['position'], new_state[player_index]['position']

    if old_facing != new_facing:
        if new_facing == next_facing(old_facing, characters.Action.TURN_LEFT):
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT
    elif old_position != new_position:
        if new_position == next_step(old_position, old_facing, characters.Action.STEP_FORWARD):
            return characters.Action.STEP_FORWARD
        elif new_position == next_step(old_position, old_facing, characters.Action.STEP_BACKWARD):
            return characters.Action.STEP_BACKWARD
        elif new_position == next_step(old_position, old_facing, characters.Action.STEP_LEFT):
            return characters.Action.STEP_LEFT
        else:
            return characters.Action.STEP_RIGHT

    cut_pos = WEAPONS[old_state[player_index]['weapon']].cut_positions(arena.terrain, old_position, old_facing)

    for idx in range(len(old_state)):
        if idx != player_index and old_state[idx]['position'] in cut_pos and new_state[idx]['health'] < old_state[idx]['health']:
            return characters.Action.ATTACK

    return characters.Action.DO_NOTHING


def make_move(state: list, action: characters.Action, player_index: int, arena: arenas.Arena, fields: list) -> list:
    new_state = deepcopy(state)

    character = new_state[player_index]
    targets = new_state[:player_index] + new_state[player_index + 1:]

    if action == characters.Action.ATTACK:
        cut_pos = WEAPONS[character['weapon']].cut_positions(arena.terrain, character['position'], character['facing'])
        for target in targets:
            if target['position'] in cut_pos:
                target['health'] -= WEAPONS_CUT[character['weapon']]
        if character['weapon'] == 'bow_loaded':
            character['weapon'] = 'bow_unloaded'
        elif character['weapon'] == 'bow_unloaded':
            character['weapon'] = 'bow_loaded'
    elif action in [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]:
        character['facing'] = next_facing(character['facing'], action)
    else:
        next_position = next_step(character['position'], character['facing'], action)
        if [next_position.x, next_position.y] in fields and all(target['position'] != next_position for target in targets):
            character['position'] = next_position

    return new_state


def evaluate_state(state: list) -> float:
    if state[0]['health'] <= 3:
        return -1000

    forrest_health = state[0]['health']
    enemies_health = sum(max(0, enemy['health']) for enemy in state[1:])
    potions = sum(1 for enemy in state[1:] if enemy['health'] <= 0)

    return forrest_health - enemies_health + potions


def uct_value(node: Node, c: float) -> float:
    if node.N == 0:
        return float('inf')

    return (node.T / node.N) + c * np.sqrt(np.log(node.parent.N) / node.N)


def expand_node(node: Node, player_index: int, arena: arenas.Arena, fields: list) -> Node:
    for action in ACTIONS:
        new_state = make_move(node.state, action, player_index, arena, fields)
        new_node = Node(new_state, action, node)
        node.children.append(new_node)

    return np.random.choice(node.children)


def simulate(node: Node, player_index: int, players_num: int, max_depth: int, current_depth: int, arena: arenas.Arena, fields: list) -> float:
    state = node.state.copy()

    while current_depth < max_depth and state[0]['health'] > 0:
        if (probs := PROBS.get(state[player_index]['name'], None)) is not None:
            probs /= np.sum(probs)

        action = np.random.choice(ACTIONS, p=probs)
        state = make_move(state, action, player_index, arena, fields)
        player_index = (player_index + 1) % players_num
        current_depth += 1

    return evaluate_state(state)


def backpropagate(node: Node, result: float) -> None:
    while node is not None:
        node.N += 1
        node.T += result
        node = node.parent


def mcts(root: Node, players_num: int, iterations: int, max_depth: int, c: float, arena: arenas.Arena, fields: list) -> characters.Action:
    for _ in range(iterations):
        node = root
        current_depth = 0
        player_index = 0

        while node.children:
            node = max(node.children, key=lambda child: uct_value(child, c))
            player_index = (player_index + 1) % players_num
            current_depth += 1

        if node.N != 0:
            node = expand_node(node, player_index, arena, fields)
            player_index = (player_index + 1) % players_num
            current_depth += 1

        result = simulate(node, player_index, players_num, max_depth, current_depth, arena, fields)
        backpropagate(node, result)

    best_child = max(root.children, key=lambda child: child.T / child.N)
    return best_child.action


class MCTS(Strategy):
    def __init__(
            self,
            arena_description: arenas.ArenaDescription,
            enter_distance: int,
            exit_distance: int,
            iterations: int,
            c: float,
            max_depth: int
    ) -> None:
        super().__init__(arena_description)
        self.enter_distance = enter_distance
        self.exit_distance = exit_distance
        self.iterations = iterations
        self.c = c
        self.max_depth = max_depth

        self.enemies = []
        self.old_enemies = []
        self.move_number = 0

    def enter(self) -> None:
        pass

    def should_enter(self, coords: coordinates.Coords, tile: tiles.TileDescription, character_info: CharacterInfo) -> bool:
        if character_info.step > self.move_number:
            self.move_number = character_info.step
            self.enemies = []

        if tile.character:
            distance = manhattan_distance_to(character_info.position, coords)
            cut_positions = WEAPONS[tile.character.weapon.name].cut_positions(self.arena.terrain, character_info.position, character_info.facing)

            if distance <= self.enter_distance or character_info.position in cut_positions:
                self.enemies.append({
                    'distance': distance,
                    'facing': tile.character.facing,
                    'health': tile.character.health,
                    'name': tile.character.controller_name,
                    'position': coords,
                    'weapon': tile.character.weapon.name
                })
                return True

        return False

    def should_leave(self, character_info: CharacterInfo) -> bool:
        return len(self.enemies) == 0 or all([enemy['distance'] > self.exit_distance for enemy in self.enemies])

    def left(self) -> None:
        self.enemies = []
        self.old_enemies = []

    def next_action(self, character_info: CharacterInfo) -> characters.Action:
        self.enemies.sort(key=lambda x: x['name'])

        initial_state = [{
            'distance': 0,
            'facing': character_info.facing,
            'health': character_info.health,
            'name': 'Forrest Gump',
            'position': character_info.position,
            'weapon': character_info.weapon
        }] + self.enemies

        if len(self.enemies) != len(self.old_enemies) or any([enemy['name'] != old_enemy['name'] for enemy, old_enemy in zip(self.enemies, self.old_enemies)]):
            root = Node(initial_state, action=None, parent=None)
        else:
            root = self.root

            for idx in range(len(initial_state)):
                action = next_state_to_action(root.state, initial_state, idx, self.arena)
                root = [child for child in root.children if child.action == action]

                if len(root) == 0:
                    root = Node(initial_state, action=None, parent=None)
                    break
                else:
                    root = root[0]

        self.root = root
        self.old_enemies = self.enemies.copy()

        return mcts(root, len(initial_state), self.iterations, self.max_depth, self.c, self.arena, self.fields)

    @property
    def priority(self) -> int:
        return 3

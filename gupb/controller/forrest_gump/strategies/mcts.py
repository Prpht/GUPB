import numpy as np

from gupb.controller.forrest_gump.strategies import Strategy
from gupb.controller.forrest_gump.utils import CharacterInfo, distance_to, next_facing, next_step
from gupb.model import tiles, characters, coordinates, arenas, weapons


ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK
]


WEAPONS = {
    'knife': weapons.Knife,
    'sword': weapons.Sword,
    'bow': weapons.Bow,
    'bow_loaded': weapons.Bow,
    'bow_unloaded': weapons.Bow,
    'axe': weapons.Axe,
    'amulet': weapons.Amulet
}


class Node:
    def __init__(self, state: dict, action: characters.Action, parent: 'Node') -> None:
        self.state = state
        self.action = action
        self.parent = parent
        self.children = []
        self.N = 0
        self.T = 0


def make_move(state: dict, action: characters.Action, maximizing_player: bool, arena: arenas.Arena, fields: list) -> dict:
    def move(position_p, facing_p, weapon_p, position_e, health_e) -> tuple:
        if action == characters.Action.DO_NOTHING:
            return position_p, facing_p, health_e
        elif action == characters.Action.ATTACK:
            if position_e in WEAPONS[weapon_p].cut_positions(arena.terrain, position_p, facing_p):
                return position_p, facing_p, health_e - WEAPONS[weapon_p].cut_effect().damage
            else:
                return position_p, facing_p, health_e
        elif action in [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]:
            return position_p, next_facing(facing_p, action), health_e
        else:
            next_p = next_step(position_p, facing_p, action)

            if [next_p.x, next_p.y] not in fields or next_p == position_e:
                return position_p, facing_p, health_e

            return next_p, facing_p, health_e

    if maximizing_player:
        forrest_position, forrest_facing, enemy_health = move(
            state['forrest_position'], state['forrest_facing'], state['forrest_weapon'],
            state['enemy_position'], state['enemy_health']
        )
        return {
            'forrest_position': forrest_position,
            'forrest_facing': forrest_facing,
            'forrest_health': state['forrest_health'],
            'forrest_weapon': state['forrest_weapon'],
            'enemy_position': state['enemy_position'],
            'enemy_facing': state['enemy_facing'],
            'enemy_health': enemy_health,
            'enemy_weapon': state['enemy_weapon']
        }
    else:
        enemy_position, enemy_facing, forrest_health = move(
            state['enemy_position'], state['enemy_facing'], state['enemy_weapon'],
            state['forrest_position'], state['forrest_health']
        )
        return {
            'forrest_position': state['forrest_position'],
            'forrest_facing': state['forrest_facing'],
            'forrest_health': forrest_health,
            'forrest_weapon': state['forrest_weapon'],
            'enemy_position': enemy_position,
            'enemy_facing': enemy_facing,
            'enemy_health': state['enemy_health'],
            'enemy_weapon': state['enemy_weapon']
        }


def evaluate_state(state: dict) -> float:
    value = state['forrest_health'] - state['enemy_health']
    return value if value > 0 else 10 * value


def uct_value(node: Node, c: float) -> float:
    if node.N == 0:
        return float('inf')

    return (node.T / node.N) + c * np.sqrt(np.log(node.parent.N) / node.N)


def expand_node(node: Node, maximizing_player: bool, arena: arenas.Arena, fields: list) -> Node:
    for action in ACTIONS:
        new_state = make_move(node.state, action, maximizing_player, arena, fields)
        new_node = Node(new_state, action, node)
        node.children.append(new_node)

    return np.random.choice(node.children)


def simulate(node: Node, maximizing_player: bool, max_depth: int, current_depth: int, arena: arenas.Arena, fields: list) -> float:
    state = node.state.copy()

    while current_depth < max_depth and state['forrest_health'] > 0 and state['enemy_health'] > 0:
        action = np.random.choice(ACTIONS)
        state = make_move(state, action, maximizing_player, arena, fields)
        maximizing_player = not maximizing_player
        current_depth += 1

    return evaluate_state(state)


def backpropagate(node: Node, result: float) -> None:
    while node is not None:
        node.N += 1
        node.T += result
        node = node.parent


def mcts(initial_state: dict, iterations: int, max_depth: int, c: float, arena: arenas.Arena, fields: list) -> characters.Action:
    root = Node(initial_state, action=None, parent=None)

    for _ in range(iterations):
        node = root
        maximizing_player = True
        current_depth = 0

        while node.children:
            node = max(node.children, key=lambda child: uct_value(child, c))
            maximizing_player = not maximizing_player
            current_depth += 1

        if node.N != 0:
            node = expand_node(node, maximizing_player, arena, fields)
            maximizing_player = not maximizing_player
            current_depth += 1

        result = simulate(node, maximizing_player, max_depth, current_depth, arena, fields)
        backpropagate(node, result)

    best_child = max(root.children, key=lambda child: child.T / child.N)
    return best_child.action


class MCTS(Strategy):
    def __init__(self, arena_description: arenas.ArenaDescription, enter_distance: int, iterations: int, c: float, max_depth: int) -> None:
        super().__init__(arena_description)
        self.enter_distance = enter_distance
        self.iterations = iterations
        self.c = c
        self.max_depth = max_depth
        self.no_enemy = False

    def enter(self) -> None:
        self.no_enemy = False

    def should_enter(self, coords: coordinates.Coords, tile: tiles.TileDescription, character_info: CharacterInfo) -> bool:
        self.no_enemy = True

        if tile.character:
            self.distance = distance_to(self.matrix, coords, character_info.position)
            cut_positions = WEAPONS[tile.character.weapon.name].cut_positions(self.arena.terrain, character_info.position, character_info.facing)

            if self.distance <= self.enter_distance or character_info.position in cut_positions:
                self.no_enemy = False
                self.enemy = tile.character
                self.enemy_position = coords
                return True

        return False

    def should_leave(self, character_info: CharacterInfo) -> bool:
        return self.distance > self.enter_distance or self.no_enemy

    def left(self) -> None:
        self.no_enemy = True

    def next_action(self, character_info: CharacterInfo) -> characters.Action:
        initial_state = {
            'forrest_position': character_info.position,
            'forrest_facing': character_info.facing,
            'forrest_health': character_info.health,
            'forrest_weapon': character_info.weapon,
            'enemy_position': self.enemy_position,
            'enemy_facing': self.enemy.facing,
            'enemy_health': self.enemy.health,
            'enemy_weapon': self.enemy.weapon.name
        }

        return mcts(initial_state, self.iterations, self.max_depth, self.c, self.arena, self.fields)

    @property
    def priority(self) -> int:
        return 3

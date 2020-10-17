import operator
import os
import random
from typing import Dict, List, Tuple

from pathfinding.core.grid import Grid
from pathfinding.finder.dijkstra import DijkstraFinder

from gupb.model.arenas import ArenaDescription
from gupb.model.characters import Facing, Action, ChampionKnowledge
from gupb.model.coordinates import Coords, add_coords, sub_coords
from gupb.model.tiles import TileDescription

RIGHT_SIDE_TRANSITIONS = {
    Facing.UP: Facing.RIGHT,
    Facing.RIGHT: Facing.DOWN,
    Facing.DOWN: Facing.LEFT,
    Facing.LEFT: Facing.UP,
}

# Used for path finding
MAP_SYMBOLS_COST = {
    '=': 0,  # Sea - obstacle
    '#': 0,  # Wall  - obstacle
    'B': 1,  # Bow
    'S': 4,  # Sword
    'A': 4,  # Axe
    'M': 4,  # Amulet
    '.': 3,  # Land
    'K': 10000,  # Knife - start weapon, we usually want to avoid it
}

WEAPONS_SYMBOLS = 'BSAMK'

WEAPON_INDEX = {
    'knife': 1000,
    'sword': 3,
    'axe': 3,
    'bow': 1,
    'amulet': 3,
}

WEAPON_DECODING = {
    'K': 'knife',
    'S': 'sword',
    'A': 'axe',
    'B': 'bow',
    'M': 'amulet',
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotElkaController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.directions_info: Dict[Facing, int] = {
            Facing.UP: 0, Facing.LEFT: 0, Facing.RIGHT: 0, Facing.DOWN: 0
        }
        self.tiles_info: Dict[Facing, TileDescription] = {}
        self.moves_queue: List[Action] = []
        self.counter: int = 0
        self.grid = None
        self.current_coords = None
        self.current_facing = None
        self.current_weapon = None
        self.menhir_pos = None
        self.go_to_menhir = True
        self.weapon_positions = {}

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotElkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return f"BotElka<{self.first_name}>"

    def reset(self, arena_description: ArenaDescription) -> None:
        self.menhir_pos = arena_description.menhir_position

        arena_file = os.path.join(os.path.dirname(__file__), f"../../resources/arenas/{arena_description.name}.gupb")
        with open(arena_file, 'r') as file:
            lines = file.readlines()

            self.grid = Grid(
                matrix=[
                    [MAP_SYMBOLS_COST.get(symbol, 0) for symbol in row.replace('\n', '')]
                    for row in lines
                ]
            )

            self.weapon_positions = {
                Coords(x, y): WEAPON_DECODING[symbol]
                for y, row in enumerate(lines)
                for x, symbol in enumerate(row.replace('\n', ''))
                if symbol in WEAPONS_SYMBOLS
            }

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.update_current_bot_attributes(knowledge)

        # There are moves available
        if self.moves_queue:
            return self.moves_queue.pop(0)

        if self.current_weapon == 'knife':
            self.find_better_weapon()
            return self.moves_queue.pop(0)

        if self.go_to_menhir:
            self.moves_queue = self.find_path(self.menhir_pos)
            self.go_to_menhir = False
            return self.moves_queue.pop(0)

        self.protect_menhir()

        return self.moves_queue.pop(0)

    def protect_menhir(self):
        actions = []
        menhir_surrounding = [
            add_coords(self.menhir_pos, Facing.UP.value),
            add_coords(self.menhir_pos, Facing.DOWN.value),
            add_coords(self.menhir_pos, Facing.LEFT.value),
            add_coords(self.menhir_pos, Facing.RIGHT.value),
        ]

        destination = random.choice(menhir_surrounding)
        path = self.find_path(destination)
        for instruction in path:
            actions.append(Action.ATTACK)
            actions.append(instruction)

        self.moves_queue += actions

    def find_path(self, coords: Coords) -> List[Action]:
        steps = []
        self.grid.cleanup()

        assert self.current_coords, "current_coords at this step always present"
        assert self.current_facing, "current_facing at this step always present"

        start = self.grid.node(self.current_coords.x, self.current_coords.y)
        end = self.grid.node(coords.x, coords.y)

        finder = DijkstraFinder()
        path, _ = finder.find_path(start, end, self.grid)

        facing = self.current_facing

        for x in range(len(path) - 1):
            actions, facing = _move_one_tile(facing, path[x], path[x + 1])
            steps += actions

        return steps

    def update_current_bot_attributes(self, knowledge: ChampionKnowledge) -> None:
        """
        Determine current facing, weapon and coordinates of the bot.
        """
        coords, visible_tile = next((
            (coords, visible_tile)
            for coords, visible_tile in knowledge.visible_tiles.items()
            if visible_tile.character and visible_tile.character.controller_name == self.name
        ), (None, None))

        assert visible_tile and coords, "Bot attributes always present"

        visible_weapons = {
            coords: visible_tile.loot.name
            for coords, visible_tile in knowledge.visible_tiles.items()
            if visible_tile.loot
        }

        self.weapon_positions.update(visible_weapons)
        self.current_coords = coords
        self.current_facing = visible_tile.character.facing
        self.current_weapon = visible_tile.character.weapon.name

    def find_better_weapon(self) -> None:
        distances = {}
        for coords, weapon in self.weapon_positions.items():
            distances[(weapon, coords)] = len(self.find_path(coords)) * WEAPON_INDEX[weapon]
        weapon, coord = min(distances.items(), key=operator.itemgetter(1))[0]

        self.moves_queue = self.find_path(coord)


def _move_one_tile(starting_facing: Facing, coord_0: Coords, coord_1: Coords) -> Tuple[List[Action], Facing]:
    exit_facing = Facing(sub_coords(coord_1, coord_0))

    # Determine what is better, turning left or turning right.
    # Builds 2 lists and compares length.
    facing_turning_left = starting_facing
    left_actions = []
    while facing_turning_left != exit_facing:
        facing_turning_left = facing_turning_left.turn_left()
        left_actions.append(Action.TURN_LEFT)

    facing_turning_right = starting_facing
    right_actions = []
    while facing_turning_right != exit_facing:
        facing_turning_right = facing_turning_right.turn_right()
        right_actions.append(Action.TURN_RIGHT)

    actions = right_actions if len(left_actions) > len(right_actions) else left_actions
    actions.append(Action.STEP_FORWARD)

    return actions, exit_facing


POTENTIAL_CONTROLLERS = [
    BotElkaController("Z nami na pewno zdasz")
]

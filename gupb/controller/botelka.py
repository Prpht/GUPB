import operator
from typing import Dict, List, Tuple

from pathfinding.core.grid import Grid
from pathfinding.finder.dijkstra import DijkstraFinder

from gupb.model.arenas import ArenaDescription, WEAPON_ENCODING
from gupb.model.characters import Facing, Action, ChampionKnowledge
from gupb.model.coordinates import Coords, add_coords, sub_coords

from gupb.model.tiles import TileDescription
from gupb.model.weapons import Weapon
import os

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
    'S': 1,  # Sword
    'A': 1,  # Axe
    'B': 1,  # Bow
    'M': 1,  # Amulet
    '.': 2,  # Land
    'K': 3,  # Knife - start weapon, we usually want to avoid it
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
        self.menhir_pos = None
        self.menhir_found = False
        self.initial_weapon_positions = {}

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
            self.grid = Grid(
                matrix=[
                    [MAP_SYMBOLS_COST.get(symbol, 0) for symbol in row.replace('\n', '')]
                    for row in file.readlines()
                ]
            )

            self.initial_weapon_positions = {
                Coords(x, y): WEAPON_ENCODING[symbol]
                for y, row in enumerate(file.readlines())
                for x, symbol in enumerate(row.replace('\n', ''))
            }

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        # Determine current Facing of the bot
        current_facing, current_coords = self.get_current_position(knowledge)

        self.current_coords = current_coords
        self.current_facing = current_facing

        if not self.menhir_found:
            self.moves_queue += self.find_path(self.menhir_pos)
            self.menhir_found = True

        # There are moves available
        if self.moves_queue:
            return self.moves_queue.pop(0)

        # self.defense(current_facing, current_coords, knowledge)
        #
        # # Count how many save tiles Bot can see in given direction
        # self.directions_info[current_facing] = len([
        #     visible_tile
        #     for visible_tile in knowledge.visible_tiles.values()
        #     if _is_safe_land(visible_tile)
        # ])
        # # Remember what was if front of us at given facing
        # self.tiles_info[current_facing] = knowledge.visible_tiles[add_coords(current_coords, current_facing.value)]
        #
        # self.control_movement(current_facing)

        return self.moves_queue.pop(0)

    def find_weapons(self, weapon: Weapon) -> List[Coords]:
        pass

    def find_path(self, coords: Coords) -> List[Action]:
        steps = []

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

    def get_current_position(self, knowledge: ChampionKnowledge) -> Tuple[Facing, Coords]:
        """
        Determine current facing and coordinates of the bot.
        """
        facing = next((
            (visible_tile.character.facing, coords)
            for coords, visible_tile in knowledge.visible_tiles.items()
            if visible_tile.character and visible_tile.character.controller_name == self.name
        ), None)

        assert facing, "Bot facing always present"

        return facing

    def control_movement(self, current_facing: Facing) -> None:
        """
        Determine the best direction to go, basing on the availability of the free space.
        """
        self.counter += 1

        if self.counter != 4:
            # Bot needs to spin around, to see whats is around it
            self.moves_queue.append(Action.TURN_RIGHT)
            return

        self.counter = 0
        # Calculate the best direction to run away
        desired_facing = self.get_good_facing()

        self.moves_queue += self.rotate_character(current_facing, desired_facing)
        self.moves_queue.append(Action.STEP_FORWARD)

    def defense(self, facing: Facing, coords: Coords, knowledge: ChampionKnowledge) -> None:
        """
        If there is an enemy in front of the bot, attack it.
        """
        tile_in_front = add_coords(coords, facing.value)

        if knowledge.visible_tiles[tile_in_front].character:
            self.moves_queue.insert(0, Action.ATTACK)

    def rotate_character(self, starting_facing: Facing, desired_facing: Facing) -> List[Action]:
        """
        Rotate character until starting position becomes desired position.
        """
        result = []

        while starting_facing != desired_facing:
            result.append(Action.TURN_RIGHT)
            starting_facing = RIGHT_SIDE_TRANSITIONS[starting_facing]

        return result

    def get_good_facing(self) -> Facing:
        """
        Avoid being stuck on the map.
        """
        desired_facing: Facing = max(self.directions_info.items(), key=operator.itemgetter(1))[0]

        if _is_safe_land(self.tiles_info[desired_facing]):
            return desired_facing

        # Turn right, to prevent being stuck
        return RIGHT_SIDE_TRANSITIONS[desired_facing]


def _is_safe_land(visible_tile: TileDescription) -> bool:
    """
    Determine if Tile is safe for the bot.
    """
    dangerous_effects = [
        effect for effect in visible_tile.effects if effect.type == "mist"
    ]
    if dangerous_effects:
        return False

    if visible_tile.type != "land":
        return False

    return True


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

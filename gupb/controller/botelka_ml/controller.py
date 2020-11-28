from gupb.controller.botelka_ml.actions import go_to_menhir
from gupb.controller.botelka_ml.model import get_model
from gupb.controller.botelka_ml.rewards import calculate_reward
from gupb.controller.botelka_ml.wisdom import State, get_state
from gupb.model.arenas import ArenaDescription, Arena
from gupb.model.characters import Action, ChampionKnowledge, Tabard
from pathfinding.core.grid import Grid
from pathfinding.finder.dijkstra import DijkstraFinder
from gupb.model.characters import ChampionKnowledge, Facing, Action
from gupb.model.coordinates import Coords, add_coords, sub_coords
from typing import Optional, Tuple, List

LEARNING_RATE = 0.5  # (alpha)
DISCOUNT_FACTOR = 0.95  # (gamma)

MAP_TILES_COST = {
    'sea': 0,  # Sea - obstacle
    'wall': 0,  # Wall  - obstacle
    'bow': 1,  # Bow
    'sword': 4,  # Sword
    'axe': 4,  # Axe
    'amulet': 4,  # Amulet
    'land': 3,  # Land
    'knife': 10000,  # Knife - start weapon, we usually want to avoid it
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotElkaController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena = None

        self.old_action_no = 0
        # self.old_state = State(0, 0, 0, 5, 0, False, 0, 3, 100, 100, 100, 0)

        # self.model = get_model()

        self.tick = 0
        self.moves_queue = []

        self.grid = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotElkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    @property
    def name(self) -> str:
        return f"BotElka<{self.first_name}>"

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.BLUE

    def die(self):
        # self.model.update(self.old_state.as_tuple(), self.old_state.as_tuple(), self.old_action_no, 0)
        # self.model.save()
        pass

    def win(self):
        # self.model.update(self.old_state.as_tuple(), self.old_state.as_tuple(), self.old_action_no, 10)
        # self.model.save()
        pass

    def reset(self, arena_description: ArenaDescription) -> None:
        self.prepare_grid()

        self.tick = 0

        self.arena = Arena.load(arena_description.name)
        self.arena.menhir_position = arena_description.menhir_position

        self.old_action_no = 0
        # self.old_state = State(0, 0, 0, 5, 0, False, 0, 3, 100, 100, 100, 0)

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        # self.tick += 1
        #
        # if self.tick == 1:
        #     self.moves_queue = self.find_path(self.arena.menhir_position, knowledge)
        #
        # if self.moves_queue:
        #     return self.moves_queue.pop()

        new_state = get_state(knowledge, self.arena, self.tick)

        # reward = calculate_reward(self.old_state, new_state, self.old_action_no)
        #
        # self.model.update(self.old_state.as_tuple(), new_state.as_tuple(), self.old_action_no, reward)
        #
        # new_actions, action_no = self.model.get_next_action(new_state.as_tuple())
        # self.moves_queue.extend(new_actions)
        #
        # self.old_action_no = action_no
        # self.old_state = new_state
        if not self.moves_queue:
            self.moves_queue += go_to_menhir(self.grid, new_state)

        return self.moves_queue.pop() if self.moves_queue else Action.ATTACK

    def prepare_grid(self):
        matrix = [[0] * self.arena.size[0]] * self.arena.size[1]
        for coords, tile in self.arena.terrain.items():
            x, y = coords
            matrix[x][y] = MAP_TILES_COST.get(tile.description().type, 0)
        self.grid = Grid(matrix=matrix)

    # def find_path(self, coords: Coords, knowledge: ChampionKnowledge) -> List[Action]:
    #     steps = []
    #     self.grid.cleanup()
    #
    #     start = self.grid.node(knowledge.position.x, knowledge.position.y)
    #     end = self.grid.node(coords.x, coords.y)
    #     # print(knowledge.position.x, knowledge.position.y, coords.x, coords.y)
    #     path, _ = self.finder.find_path(start, end, self.grid)
    #
    #     facing = knowledge.visible_tiles[(knowledge.position.x, knowledge.position.y)].character.facing
    #
    #     for x in range(len(path) - 1):
    #         actions, facing = self.move_one_tile(facing, path[x], path[x + 1])
    #         steps += actions
    #
    #     return steps
    #
    # def move_one_tile(self, starting_facing: Facing, coord_0: Coords, coord_1: Coords) -> Tuple[List[Action], Facing]:
    #     exit_facing = Facing(sub_coords(coord_1, coord_0))
    #
    #     # Determine what is better, turning left or turning right.
    #     # Builds 2 lists and compares length.
    #     facing_turning_left = starting_facing
    #     left_actions = []
    #     while facing_turning_left != exit_facing:
    #         facing_turning_left = facing_turning_left.turn_left()
    #         left_actions += [Action.TURN_LEFT]
    #
    #     facing_turning_right = starting_facing
    #     right_actions = []
    #     while facing_turning_right != exit_facing:
    #         facing_turning_right = facing_turning_right.turn_right()
    #         right_actions += [Action.TURN_RIGHT]
    #
    #     actions = right_actions if len(left_actions) > len(right_actions) else left_actions
    #     actions += [Action.STEP_FORWARD]
    #
    #     return actions, exit_facing


POTENTIAL_CONTROLLERS = [
    BotElkaController("Z nami na pewno zdasz")
]

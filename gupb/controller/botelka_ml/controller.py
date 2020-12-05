from pathfinding.core.grid import Grid

from gupb.controller.botelka_ml.actions import go_to_menhir, kill_them_all, find_better_weapon
from gupb.controller.botelka_ml.utils import debug_print
from gupb.controller.botelka_ml.wisdom import get_state
from gupb.model.arenas import ArenaDescription, Arena
from gupb.model.characters import Tabard, ChampionKnowledge, Action
from gupb.model.coordinates import Coords
from gupb.model.tiles import Tile

LEARNING_RATE = 0.5  # (alpha)
DISCOUNT_FACTOR = 0.95  # (gamma)

MAP_TILES_COST = {
    "sea": 0,  # Sea - obstacle
    "wall": 0,  # Wall  - obstacle
    "menhir": 0,  # Obstacle
    "bow": 1,  # Bow
    "sword": 4,  # Sword
    "axe": 4,  # Axe
    "amulet": 4,  # Amulet
    "land": 3,  # Land
    "knife": 10000,  # Knife - start weapon, we usually want to avoid it
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
        self.weapons_info = []

        self.grid = None

        self.menhir_reached = False

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
        self.arena = Arena.load(arena_description.name)
        self.arena.menhir_position = arena_description.menhir_position

        self.prepare_grid()

        self.tick = 0
        # self.old_state = State(0, 0, 0, 5, 0, False, 0, 3, 100, 100, 100, 0)
        map_weapons = {Coords(*coords): tile.loot.description()
        for coords, tile in self.arena.terrain.items() if tile.loot}

        self.weapons_info = map_weapons

        self.menhir_reached = False

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        # self.tick += 1
        #
        # if self.tick == 1:
        #     self.moves_queue = self.find_path(self.arena.menhir_position, knowledge)
        #
        # if self.moves_queue:
        #     return self.moves_queue.pop()

        new_state = get_state(knowledge, self.arena, self.tick, self.weapons_info)

        self.weapons_info = new_state.weapons_info

        # reward = calculate_reward(self.old_state, new_state, self.old_action_no)
        #
        # self.model.update(self.old_state.as_tuple(), new_state.as_tuple(), self.old_action_no, reward)
        #
        # new_actions, action_no = self.model.get_next_action(new_state.as_tuple())
        # self.moves_queue.extend(new_actions)
        #
        # self.old_action_no = action_no
        # self.old_state = new_state

        try:
            go_to_menhir_action = go_to_menhir(self.grid, new_state)
            if go_to_menhir_action == Action.DO_NOTHING:
                self.menhir_reached = True

            if not self.menhir_reached:
                debug_print("Going to menhir")
                return go_to_menhir_action

            if self.menhir_reached:
                debug_print("Menhir reached")
                kill = kill_them_all(self.grid, new_state)

                # Nobody to kill, like look around
                if kill == Action.DO_NOTHING:
                    debug_print("Nobody to kill, going to menhir")
                    return Action.TURN_RIGHT

                debug_print(kill);
                return kill
        except Exception as e:
            # Just to know if anything broke, should be removed
            debug_print(e)
        return Action.TURN_RIGHT

    def prepare_grid(self):
        matrix = [
            [
                get_tile_cost(self.arena.terrain[Coords(x, y)])
                for x in range(self.arena.size[0])
            ]
            for y in range(self.arena.size[1])
        ]
        matrix[self.arena.menhir_position.y][self.arena.menhir_position.x] = 0

        self.grid = Grid(matrix=matrix)


def get_tile_cost(tile: Tile) -> int:
    description = tile.description()

    # Sea od Land
    tile_type = description.type

    if not tile.passable:
        tile_type = "wall"

    # Weapons
    if description.loot:
        tile_type = description.loot.name

    return MAP_TILES_COST[tile_type]


POTENTIAL_CONTROLLERS = [
    BotElkaController("Z nami na pewno zdasz")
]

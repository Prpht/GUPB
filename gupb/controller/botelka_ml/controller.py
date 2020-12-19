from pathfinding.core.grid import Grid

from gupb.controller.botelka_ml.actions import (
    go_to_menhir, kill_them_all, find_better_weapon, flee,
    update_grid_on_incoming_mist, update_grid_tiles_costs, grid_with_players_mask,
)
from gupb.controller.botelka_ml.state import State, get_state
from gupb.controller.botelka_ml.utils import debug_print
from gupb.model.arenas import ArenaDescription, Arena
from gupb.model.characters import Tabard, ChampionKnowledge, Action, Facing
from gupb.model.coordinates import Coords
from gupb.model.tiles import Tile
from gupb.model.weapons import Knife

LEARNING_RATE = 0.5  # (alpha)
DISCOUNT_FACTOR = 0.95  # (gamma)

MAP_TILES_COST = {
    "sea": 0,  # Obstacle
    "wall": 0,  # Obstacle
    "menhir": 0,  # Obstacle
    "bow": 1,
    "amulet": 1,
    "sword": 4,
    "axe": 4,
    "land": 3,
    "knife": 10000,
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotElkaController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena = None

        self.old_action_no = 0
        self.old_state = None

        # self.model = get_model()

        self.tick = 0
        self.moves_queue = []
        self.weapons_info = {}

        self.grid = None

        self.mist_on_map = False
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
        self.old_state = State(self.arena, Coords(0, 0), 5, [], False, Facing.UP, Knife(), 1000,
                               self.arena.menhir_position, 0, {}, False)

        self.weapons_info = {
            Coords(*coords): tile.loot.description()
            for coords, tile in self.arena.terrain.items() if tile.loot
        }

        self.mist_on_map = False
        self.menhir_reached = False

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.tick += 1

        old_state, new_state = self.old_state, get_state(knowledge, self.arena, self.tick, self.weapons_info)
        self.weapons_info = new_state.weapons_info

        self.grid = update_grid_tiles_costs(knowledge, self.grid)
        self.grid, mist_on_map = update_grid_on_incoming_mist(self.arena, self.grid, self.tick)

        grid_with_mask = grid_with_players_mask(self.grid, knowledge, new_state)

        if mist_on_map:
            self.mist_on_map = True

        lost_health = old_state.health > new_state.health
        self.old_state = new_state

        if kill_them_all(grid_with_mask, new_state) == Action.ATTACK:
            debug_print("DIE!!!")
            return Action.ATTACK

        if lost_health:
            debug_print("Ouch! Running away.")
            return flee(grid_with_mask, new_state)

        if new_state.weapon.description().name == "knife":
            new_weapon = find_better_weapon(grid_with_mask, new_state)

            if new_weapon == Action.DO_NOTHING:
                debug_print("Could not find a better weapon, going to the menhir")
                return go_to_menhir(grid_with_mask, new_state)

            debug_print("Going for a better weapon")
            return new_weapon

        if not self.mist_on_map:
            debug_print("Mist not yet visible, spinning")
            return Action.TURN_RIGHT

        go_to_menhir_action = go_to_menhir(grid_with_mask, new_state)

        if go_to_menhir_action == Action.DO_NOTHING:
            debug_print("Menhir reached, spinning")
            return Action.TURN_RIGHT

        debug_print("Mist on the map, going to menhir")
        return go_to_menhir_action

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

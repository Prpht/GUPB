import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class SnieznyKockodanController(controller.Controller):
    weapon_distance = 5

    def __init__(self, first_name: str):
        self.first_name: str = first_name

        self.menhir = False
        self.mist = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SnieznyKockodanController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir = False
        self.mist = False

    @property
    def name(self) -> str:
        return f'SnieznyKockodanController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE

    @classmethod
    def count_x_distance(cls, tile_position, current_position):
        return abs(tile_position[0] - current_position[0])

    @classmethod
    def count_y_distance(cls, tile_position, current_position):
        return abs(tile_position[1] - current_position[1])

    @classmethod
    def is_potential_weapon_tile(cls, tile_position, current_position):
        x_distance = SnieznyKockodanController.count_x_distance(tile_position, current_position)
        if x_distance > SnieznyKockodanController.weapon_distance:
            y_distance = SnieznyKockodanController.count_y_distance(tile_position, current_position)
            return y_distance <= SnieznyKockodanController.weapon_distance

        return False


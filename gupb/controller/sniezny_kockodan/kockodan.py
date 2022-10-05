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
        self.weapon = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, SnieznyKockodanController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if not self.weapon:
            weapons = SnieznyKockodanController.get_visible_weapons(knowledge)
            pass  # move
        # elif i can see the enemy
        # else idę do menhira, na środek lub przeciw mgle

        return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir = False
        self.mist = False
        self.weapon = False

    @property
    def name(self) -> str:
        return f'SnieznyKockodanController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE

    @staticmethod
    def count_x_distance(tile_position, current_position):
        return abs(tile_position[0] - current_position[0])

    @staticmethod
    def count_y_distance(tile_position, current_position):
        return abs(tile_position[1] - current_position[1])

    @staticmethod
    def is_potential_weapon_tile(tile_position, current_position):
        x_distance = SnieznyKockodanController.count_x_distance(tile_position, current_position)
        if x_distance > SnieznyKockodanController.weapon_distance:
            y_distance = SnieznyKockodanController.count_y_distance(tile_position, current_position)
            return y_distance <= SnieznyKockodanController.weapon_distance

        return False

    @staticmethod
    def get_visible_weapons(knowledge):
        weapons = []
        for tile in knowledge.visible_tiles:
            if knowledge.visible_tiles[tile].loot is not None:
                weapons += [tile]

        return weapons

    # @staticmethod
    # def is_weapon_visible(current_position, knowledge):
    #     for tile in knowledge.visible_tiles.values:


    # TODO:
    # walking procedure



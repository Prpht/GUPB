import math
import random

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

ACTIONS_WITH_WEIGHTS = {
    characters.Action.TURN_LEFT: 0.2,
    characters.Action.TURN_RIGHT: 0.2,
    characters.Action.STEP_FORWARD: 0.5,
    characters.Action.ATTACK: 0.1,
}

TABARD_ASSIGNMENT = {
    "R2D2": characters.Tabard.WHITE
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class R2D2Controller:
    def __init__(self, first_name: str):
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, R2D2Controller):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def calculate_distance(self, self_position: coordinates.Coords, other_position: coordinates.Coords) -> int:
        distance = math.sqrt((self_position.x - other_position.x) ** 2 + (self_position.y - other_position.y) ** 2)
        return int(round(distance))

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles
        enemy_nearby = False
        nearest_enemy_distance = 35000
        nearest_enemy_position = None

        for visible_position in visible_tiles.keys():
            if visible_tiles[visible_position].character is not None \
                    and visible_tiles[visible_position].character.controller_name != self.first_name:
                enemy_nearby = True
                nearest_enemy_distance = min(nearest_enemy_distance,
                                             self.calculate_distance(position, visible_position))
                nearest_enemy_position = visible_position

        self_description = visible_tiles[position].character
        if self_description is not None:
            health = self_description.health
            facing = self_description.facing

            if health >= characters.CHAMPION_STARTING_HP * 0.25 and nearest_enemy_distance == 1:
                return characters.Action.ATTACK

        # return random action considering probability distribution
        return random.choices(population=list(ACTIONS_WITH_WEIGHTS.keys()),
                              weights=list(ACTIONS_WITH_WEIGHTS.values()),
                              k=1)[0]

    @property
    def name(self) -> str:
        return f'RandomController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return TABARD_ASSIGNMENT[self.first_name] if self.first_name in TABARD_ASSIGNMENT else characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    R2D2Controller("R2D2")
]

import random

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
class RandomController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RandomController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self,  knowledge: characters.ChampionKnowledge) -> characters.Action:
        return random.choice(POSSIBLE_ACTIONS)

    @property
    def name(self) -> str:
        return f'RandomController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    RandomController("Alice"),
    RandomController("Bob"),
    RandomController("Cecilia"),
    RandomController("Darius"),
]

import random

from gupb.model import arenas
from gupb.model import characters

ACTIONS_WITH_WEIGHTS = {
    characters.Action.TURN_LEFT: 0.2,
    characters.Action.TURN_RIGHT: 0.2,
    characters.Action.STEP_FORWARD: 0.5,
    characters.Action.ATTACK: 0.1,
}

TABARD_ASSIGNMENT = {
    "Alice": characters.Tabard.BLUE,
    "Bob": characters.Tabard.YELLOW,
    "Cecilia": characters.Tabard.RED,
    "Darius": characters.Tabard.GREY,
}


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

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
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
    RandomController("Alice"),
    RandomController("Bob"),
    RandomController("Cecilia"),
    RandomController("Darius"),
]

from .bow_strategy import BowStrategy
from .sword_strategy import SwordStrategy
from .axe_strategy import AxeStrategy

from gupb import controller
from gupb.model import arenas
from gupb.model import characters

import numpy as np

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]

WEAPON_RANGE = {
    'bow_loaded': 50,
    'sword': 3,
    'knife': 1
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class FelixBotController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.current_strategy = SwordStrategy()
        self.strategies = [SwordStrategy(), BowStrategy(), AxeStrategy()]
        self.epsilon = 0.04

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FelixBotController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        for strategy in self.strategies:
            strategy.reset(arena_description)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.current_strategy.decide(knowledge)

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW

    # def choose_bandit(self):


    def get_random_strategy(self):
        return np.random.choice(self.strategies)


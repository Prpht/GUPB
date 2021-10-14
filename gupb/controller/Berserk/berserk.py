import random
import numpy as np

from gupb.model import arenas
from gupb.model import characters


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BerserkBot:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self._possible_actions = [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.ATTACK,
        ]
        self.probabilities = [0.2, 0.2, 0.1, 0.5]

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BerserkBot):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.update_probabilities(knowledge)
        return np.random.choice(self._possible_actions, 1, p=self.probabilities)

    @property
    def name(self) -> str:
        return f'BerserkBot{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY

    def update_probabilities(self, knowledge: characters.ChampionKnowledge) -> None:
        pass


POTENTIAL_CONTROLLERS = [
    BerserkBot("Ragnar")
]

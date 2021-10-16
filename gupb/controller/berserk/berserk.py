import numpy as np

from gupb.model import arenas
from gupb.model import characters
from gupb.controller.berserk.knowledge_decoder import KnowledgeDecoder


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BerserkBot:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.knowledge_decoder = KnowledgeDecoder()
        self._possible_actions = [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.ATTACK,
        ]
        self.probabilities = [0.4, 0.4, 0.1, 0.1]
        self.move_counter = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BerserkBot):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.probabilities = [0.4, 0.4, 0.1, 0.1]
        self.move_counter = 0

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.knowledge_decoder.knowledge = knowledge
        enemies_in_sight, cords, *rest = self.knowledge_decoder.decode()
        self.update_probabilities(enemies_in_sight)
        self.move_counter += 1
        return np.random.choice(self._possible_actions, 1, p=self.probabilities)[0]

    @property
    def name(self) -> str:
        return f'BerserkBot{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY

    def update_probabilities(self, enemies_in_sight: list) -> None:
        enemies = len(enemies_in_sight)
        if enemies == 1:
            self.probabilities = [0.2, 0.2, 0.2, 0.4]
        elif enemies > 1:
            self.probabilities = [0.05, 0.05, 0.1, 0.8]
        elif enemies == 0 and self.move_counter >= 10:
            self.probabilities = [0.25, 0.25, 0.4, 0.1]
        else:
            self.probabilities = [0.4, 0.4, 0.1, 0.1]



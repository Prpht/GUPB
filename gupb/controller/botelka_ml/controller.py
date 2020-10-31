import random

from gupb.controller.botelka_ml.brain import POSSIBLE_ACTIONS, get_state, epsilon_greedy_action
from gupb.controller.botelka_ml.models import Wisdom
from gupb.controller.botelka_ml.rewards import calculate_reward
from gupb.model.arenas import ArenaDescription, Arena
from gupb.model.characters import Action, ChampionKnowledge, Tabard

LEARNING_RATE = 0.5  # (alpha)
DISCOUNT_FACTOR = 0.95  # (gamma)


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotElkaController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena = None
        self.q = {}

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

    def reset(self, arena_description: ArenaDescription) -> None:
        self.arena = Arena.load(arena_description.name)

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        wisdom = Wisdom(self.arena, knowledge, self.name)

        state = get_state(wisdom)
        action = epsilon_greedy_action(self.q, state)

        reward = calculate_reward(wisdom, action)

        learned_value = (reward + DISCOUNT_FACTOR * self.q[new_state, action])
        self.q[state, action] = (1 - LEARNING_RATE) * self.q[state, action] + LEARNING_RATE * learned_value

        return random.choice(POSSIBLE_ACTIONS)


POTENTIAL_CONTROLLERS = [
    BotElkaController("Z nami na pewno zdasz")
]

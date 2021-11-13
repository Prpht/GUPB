from .bow_strategy import BowStrategy
from .sword_strategy import SwordStrategy
from .axe_strategy import AxeStrategy

from .strategy_rewards_log import StrategyRewardsLog

from gupb import controller
from gupb.model import arenas
from gupb.model import characters

import numpy as np


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class FelixBotController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.current_strategy = None
        self.strategies = [SwordStrategy(), BowStrategy(), AxeStrategy()]
        self.epsilon = 0.04
        self.rewards_log = StrategyRewardsLog()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FelixBotController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    def praise(self, score: int) -> None:
        self.rewards_log.record_action(self.current_strategy, score)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        for strategy in self.strategies:
            strategy.reset(arena_description)
        self.current_strategy = self.choose_strategy()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.current_strategy.decide(knowledge)

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW

    def choose_strategy(self):
        if np.random.uniform(0, 1, 1) < self.epsilon:
            strategy = self.get_random_strategy()
        else:
            strategy= self.get_current_best_strategy()

        return strategy

    def get_current_best_strategy(self):
        estimates = []
        for strategy in self.strategies:
            strategy_record = self.rewards_log[strategy]
            estimates.append(strategy_record['reward'] / strategy_record['actions'])

        return self.strategies[np.argmax(estimates)]

    def get_random_strategy(self):
        return np.random.choice(self.strategies)


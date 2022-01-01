from .bow_strategy import BowStrategy
from .sword_strategy import SwordStrategy
from .axe_strategy import AxeStrategy
from gupb.model.arenas import Arena

from .strategy_rewards_log import StrategyRewardsLog

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.profiling import profile

import numpy as np


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class FelixBotController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.current_strategy = None
        self.map_strategies = {'fisher_island': [SwordStrategy(), BowStrategy(), AxeStrategy()],
                               'archipelago': [SwordStrategy(), BowStrategy(), AxeStrategy()],
                               'dungeon': [SwordStrategy(), BowStrategy(), AxeStrategy()]}
        self.epsilon = 0.1
        self.rewards_log = {'fisher_island': StrategyRewardsLog(),
                            'archipelago': StrategyRewardsLog(),
                            'dungeon': StrategyRewardsLog()}

        self.current_rewards_log = None
        self.current_strategies = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, FelixBotController):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    def praise(self, score: int) -> None:
        self.current_rewards_log.record_action(self.current_strategy, score)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.current_strategies = self.map_strategies[arena_description.name]
        self.current_rewards_log = self.rewards_log[arena_description.name]
        self.current_strategy = self.choose_strategy()
        self.current_strategy.reset(arena_description)

    @profile
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
            strategy = self.get_current_best_strategy()

        return strategy

    def get_current_best_strategy(self):
        estimates = []
        for strategy in self.current_strategies:
            strategy_record = self.current_rewards_log[strategy]
            estimates.append(strategy_record['reward'] / strategy_record['actions'])

        return self.current_strategies[np.argmax(estimates)]

    def get_random_strategy(self):
        return np.random.choice(self.current_strategies)

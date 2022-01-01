import random
from collections import Counter, defaultdict
from gupb import controller
from gupb.controller.berserk.knowledge_decoder import KnowledgeDecoder

from gupb.controller.berserk.strategies import AggressiveStrategy, FastMenhirStrategy, GoodWeaponMenhirStrategy, RunawayStrategy
from gupb.model.weapons import *
from gupb.controller.berserk.utilities import epsilon_desc
from gupb.model.profiling import profile


POSSIBLE_STRATEGY = {
    'runawaystrategy': RunawayStrategy,
    'aggressivestrategy': AggressiveStrategy,
    'fastmenhirstrategy': FastMenhirStrategy,
    'goodweaponmenhirstrategy': GoodWeaponMenhirStrategy
}


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BerserkBot(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.knowledge_decoder = KnowledgeDecoder()
        self.strategy = None
        self.move_counter = 0
        self.round_id = 0
        self.knowledge_base = defaultdict(lambda: dict())
        self.epsilon = self.get_epsilon()
        self.strategy_counter = Counter()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BerserkBot):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def praise(self, score: int) -> None:
        reward = score * 5 + self.move_counter * 1
        if self.strategy.name() in self.knowledge_base[self.knowledge_decoder.map_name].keys():
            runs_no = self.strategy_counter[self.strategy.name()]
            old_reward = self.knowledge_base[self.knowledge_decoder.map_name][self.strategy.name()]
            self.knowledge_base[self.knowledge_decoder.map_name][self.strategy.name()] = (reward + old_reward * (runs_no - 1))/runs_no
        else:
            self.knowledge_base[self.knowledge_decoder.map_name][self.strategy.name()] = reward

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.knowledge_decoder.reset()
        self.knowledge_decoder.map = self.knowledge_decoder.load_map(arena_description.name)
        self.move_counter = 0
        self.round_id += 1
        self.epsilon = self.get_epsilon()
        if random.random() <= self.epsilon:
            strategy_name = random.choice(list(POSSIBLE_STRATEGY.keys()))
        else:
            sorted_results = sorted(self.knowledge_base[self.knowledge_decoder.map_name].items(), key=lambda tup: tup[1])[::-1]
            strategy_name = sorted_results[0][0]
        self.strategy = POSSIBLE_STRATEGY[strategy_name](self.knowledge_decoder)
        self.strategy_counter[self.strategy.name()] += 1
        # print("\nPicked up strategy: ", self.strategy.name())

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.knowledge_decoder.knowledge = knowledge
            return self.strategy.pick_action()
        except Exception as e:
            # print(e)
            # print(self.knowledge_decoder.knowledge.position)
            return characters.Action.STEP_FORWARD

    @property
    def name(self) -> str:
        return f'BerserkBot{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED

    def get_epsilon(self):
        return epsilon_desc(self.round_id)

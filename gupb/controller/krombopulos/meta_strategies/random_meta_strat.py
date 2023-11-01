from gupb.model import characters

from .meta_strategy import MetaStrategy
from ..knowledge_sources import KnowledgeSources
from ..micro_strategies import RandomMicroStrat


class RandomMetaStrat(MetaStrategy):
    def __init__(self, knowledge_sources: KnowledgeSources):
        super().__init__(knowledge_sources)
        self.next_micro_strat = RandomMicroStrat(knowledge_sources)

    def decide(self) -> characters.Action:
        a, self.next_micro_strat = self.next_micro_strat.decide_and_get_next()
        return a

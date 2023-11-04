from typing import Literal

from gupb.model import characters

from .meta_strategy import MetaStrategy
from ..knowledge_sources import KnowledgeSources
from ..micro_strategies import ExploreMicroStrat, RouteMicroStrat


class ExploreHideRunMetaStrat(MetaStrategy):
    def __init__(self, knowledge_sources: KnowledgeSources):
        super().__init__(knowledge_sources)
        self.next_micro_strat = ExploreMicroStrat(self.knowledge_sources)
        self.mode: Literal['route', 'fight'] = 'route'



    def decide(self) -> characters.Action:
        if self.knowledge_sources.epoch % 10 == 0:
            self.mode = 'fight' if self.mode == 'route' and self.knowledge_sources.epoch % 20 == 0 else 'route'
            if self.mode == 'route':
                self.next_micro_strat = RouteMicroStrat(self.knowledge_sources)
            else:
                self.next_micro_strat = ExploreMicroStrat(self.knowledge_sources)
        a, self.next_micro_strat = self.next_micro_strat.decide_and_get_next()
        return a


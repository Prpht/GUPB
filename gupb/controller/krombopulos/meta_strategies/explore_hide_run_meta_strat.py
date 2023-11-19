from typing import Literal

from gupb.model import characters

from .meta_strategy import MetaStrategy
from ..knowledge_sources import KnowledgeSources
from ..micro_strategies import ExploreMicroStrat, RouteMicroStrat


class ExploreHideRunMetaStrat(MetaStrategy):
    def __init__(self, knowledge_sources: KnowledgeSources):
        super().__init__(knowledge_sources)
        self.current_micro_strat = ExploreMicroStrat(self.knowledge_sources)
        self.mode: Literal['route', 'fight'] = 'route'
        self.previous_action: characters.Action | None = None


    def decide(self) -> characters.Action:
        # switch mode every 20 epochs or if route is complete
        if self.knowledge_sources.epoch % 20 == 0 or self.previous_action == characters.Action.DO_NOTHING:
            self._switch_mode()
        action, _ = self.current_micro_strat.decide_and_get_next()
        self.previous_action = action
        return action

    def _switch_mode(self):
        if self.mode == 'route':
            self.mode == 'fight'
            self.current_micro_strat = ExploreMicroStrat(self.knowledge_sources)
        else:
            self.mode == 'route'
            self.current_micro_strat = RouteMicroStrat(self.knowledge_sources)



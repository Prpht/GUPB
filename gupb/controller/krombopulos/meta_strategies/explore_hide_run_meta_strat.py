from typing import Literal
from random import choices

from gupb.model import characters

from .meta_strategy import MetaStrategy
from ..knowledge_sources import KnowledgeSources
from ..micro_strategies import ExploreMicroStrat, RouteMicroStrat


class ExploreHideRunMetaStrat(MetaStrategy):
    microstrat_ratings: dict[str, float] = {k: .001 for k in ['route', 'explore']}

    def __init__(self, knowledge_sources: KnowledgeSources):
        super().__init__(knowledge_sources)
        self.current_micro_strat = ExploreMicroStrat(self.knowledge_sources)
        self.mode: Literal['route', 'explore'] = 'route'
        self.previous_action: characters.Action | None = None
        self.mode_rounds: dict[str, int] = {k: 0 for k in ['route', 'explore']}
        self.current_mode_rounds: int = 0


    def decide(self) -> characters.Action:
        self.mode_rounds[self.mode] += 1
        self.current_mode_rounds += 1
        # switch mode every x epochs or if route is complete

        if self.previous_action == characters.Action.DO_NOTHING:
            self._switch_mode()
        elif self.knowledge_sources.epoch < 10:
            self.mode = 'explore'
            self.current_micro_strat = ExploreMicroStrat(self.knowledge_sources)
        elif self.current_mode_rounds > 5:
            microstrats = list(self.microstrat_ratings.keys())
            weights = list(self.microstrat_ratings.values())
            new_mode = choices(microstrats, weights=weights, k=1)[0]
            if self.mode != new_mode:
                self._switch_mode()

        action, continue_micro_strat = self.current_micro_strat.decide_and_get_next()
        self.previous_action = action
        return action

    def praise(self, score: int):
        try:
            total_rounds = sum(list(self.mode_rounds.values()))
            for mode in self.microstrat_ratings:
                self.microstrat_ratings[mode] += score * (self.mode_rounds[mode] / total_rounds)
        except ZeroDivisionError:
            for mode in self.microstrat_ratings:
                self.microstrat_ratings[mode] += score

    def _switch_mode(self):
        if self.mode == 'route':
            self.mode = 'explore'
            self.current_micro_strat = ExploreMicroStrat(self.knowledge_sources)
        else:
            self.mode = 'route'
            self.current_micro_strat = RouteMicroStrat(self.knowledge_sources)
        self.current_mode_rounds = 0

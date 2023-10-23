from gupb import controller
from gupb.model import arenas, characters

from .knowledge_sources import KnowledgeSources
from .meta_strategies import MetaStrategy, RandomMetaStrat, ExploreHideRunMetaStrat


class KrombopulosMichaelController(controller.Controller):
    """
    Oh boy, here I go killing again!

    https://www.youtube.com/watch?v=5OWdwiU1W7g
    """
    def __init__(self):
        self._name: str = 'krombopulos-michael'
        self.epoch: int = 0

        self.knowledge_sources: KnowledgeSources = KnowledgeSources()
        self.meta_strategy: MetaStrategy = self._get_initial_meta_strategy()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.epoch += 1
        self.knowledge_sources.update(knowledge, self.epoch)
        a = self.meta_strategy.decide()
        return a

    def praise(self, score: int) -> None:
        pass  # todo: adjust strategies after a match: self.knowledge_sources.praise(score)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.knowledge_sources.reset(arena_description)

    def _get_initial_meta_strategy(self) -> MetaStrategy:
        return ExploreHideRunMetaStrat(self.knowledge_sources)

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET

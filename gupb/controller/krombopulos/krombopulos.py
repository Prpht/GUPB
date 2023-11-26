from random import choices

from gupb import controller
from gupb.model import arenas, characters
# from gupb.controller.krombopulos.trainer import Trainer

from .knowledge_sources import KnowledgeSources
from .meta_strategies import MetaStrategy, ExploreHideRunMetaStrat


class KrombopulosMichaelController(controller.Controller):
    """
    Oh boy, here I go killing again!

    https://www.youtube.com/watch?v=5OWdwiU1W7g
    """
    def __init__(self):
        self._name: str = 'krombopulos-michael'
        self.epoch: int = 0
        self.game_no: int = 0

        self.knowledge_sources: KnowledgeSources = KnowledgeSources(own_name=self._name)
        self.meta_strategy: MetaStrategy = self._get_initial_meta_strategy()
        
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """What happens at every turn."""
        self.epoch += 1
        self.knowledge_sources.update(knowledge, self.epoch)
        a = self.meta_strategy.decide()
        return a

    def praise(self, score: int) -> None:
        """What happens after the end of the game."""
        # praise based on micro strategy chosen by meta strategy
        # can easily be changed to meta strategy appraisal
        self.knowledge_sources.praise(score, self.meta_strategy)
        self.meta_strategy = self._get_next_meta_strategy()(self.knowledge_sources)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        """What happens before the beginning of a new game."""
        self.knowledge_sources.reset(arena_description)
        self.game_no = game_no
    
    def _get_next_meta_strategy(self) -> MetaStrategy:
        strats = list(self.knowledge_sources.metastrat_ratings.keys())
        weights = list(self.knowledge_sources.metastrat_ratings.values())
        return choices(strats, weights=weights, k=1)[0]

    def _get_initial_meta_strategy(self) -> MetaStrategy:
        return ExploreHideRunMetaStrat(self.knowledge_sources)

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KROMBOPULOS

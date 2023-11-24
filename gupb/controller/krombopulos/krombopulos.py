from gupb import controller
from gupb.model import arenas, characters
# from gupb.controller.krombopulos.trainer import Trainer

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
        self.game_no: int = 0

        self.knowledge_sources: KnowledgeSources = KnowledgeSources(own_name=self._name)
        self.meta_strategy: MetaStrategy = self._get_initial_meta_strategy()

        # stuff needed to use DQN
        # self.trainer = Trainer(self, './gupb/controller/krombopulos/trainer/model.zip')

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """What happens at every turn."""
        self.epoch += 1
        self.knowledge_sources.update(knowledge, self.epoch)
        a = self.meta_strategy.decide()
        return a

    def praise(self, score: int) -> None:
        """What happens after the end of the game."""
        # todo: adjust strategies after a match: self.knowledge_sources.praise(score)
        # self.knowledge_sources.praise(score, self.meta_strategy)
        ...
        # trainer is stopped
        # (optionally, save model, every 10 games)
        # self.trainer.stop(self.game_no % 10 == 0)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        """What happens before the beginning of a new game."""
        self.knowledge_sources.reset(arena_description)
        self.game_no = game_no

    def _get_initial_meta_strategy(self) -> MetaStrategy:
        return ExploreHideRunMetaStrat(self.knowledge_sources)

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KROMBOPULOS

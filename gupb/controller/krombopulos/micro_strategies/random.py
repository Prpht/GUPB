import random

from gupb.model import characters
from .micro_strategy import MicroStrategy, StrategyPrecedence
from ..knowledge_sources import KnowledgeSources
from ..utils import POSSIBLE_ACTIONS


class RandomMicroStrat(MicroStrategy):
    def __init__(self, knowledge_sources: KnowledgeSources, precedence: StrategyPrecedence | None = None):
        super().__init__(knowledge_sources, precedence)
        if precedence is None:
            self.precedence = StrategyPrecedence.LOWEST

    def decide_and_get_next(self) -> tuple[characters.Action, bool]:
        # move if champion has not moved in 5 epochs
        if action := self.avoid_afk():
            return action, False
        return random.choice(POSSIBLE_ACTIONS), True

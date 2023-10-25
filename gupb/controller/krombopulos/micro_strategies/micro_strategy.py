import abc
import enum

from gupb.model import characters

from ..knowledge_sources import KnowledgeSources


class StrategyPrecedence(enum.IntEnum):
    LOWEST = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    HIGHEST = 5


class MicroStrategy(abc.ABC):
    def __init__(self, knowledge_sources: KnowledgeSources, precedence: StrategyPrecedence | None):
        self.knowledge_sources: KnowledgeSources = knowledge_sources
        self.precedence: StrategyPrecedence = precedence

    @abc.abstractmethod
    def decide_and_get_next(self) -> tuple[characters.Action, bool]:
        """Return a tuple: (chosen_action, continue_using_this_strategy)."""
        pass

    def __gt__(self, other) -> bool:
        assert isinstance(other, MicroStrategy)
        return self.precedence > other.precedence

    def __eq__(self, other) -> bool:
        if not isinstance(other, MicroStrategy):
            return False
        return self.precedence == other.precedence

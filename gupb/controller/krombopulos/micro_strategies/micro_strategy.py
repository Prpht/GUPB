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
    def __init__(self, knowledge_sources: KnowledgeSources, precedence: StrategyPrecedence | None=None):
        self.knowledge_sources: KnowledgeSources = knowledge_sources
        self.precedence: StrategyPrecedence = precedence

    @abc.abstractmethod
    def decide_and_get_next(self) -> tuple[characters.Action, bool]:
        """Return a tuple: (chosen_action, continue_using_this_strategy)."""
        pass

    def avoid_afk(self) -> characters.Action | None:
        history = self.knowledge_sources.players.players_history[self.knowledge_sources.players._own_name]
        history = sorted(history.items(), reverse=True)
        if len(history) < 10:
            return None
        history = list([el[1] for el in history[:10]])
        facings = [el[0].facing for el in history]
        coords = [el[1] for el in history]
        if all([facings[0] == facing for facing in facings]) and all([coords[0] == coord for coord in coords]):
            return characters.Action.STEP_FORWARD
        return None

    def __gt__(self, other) -> bool:
        assert isinstance(other, MicroStrategy)
        return self.precedence > other.precedence

    def __eq__(self, other) -> bool:
        if not isinstance(other, MicroStrategy):
            return False
        return self.precedence == other.precedence

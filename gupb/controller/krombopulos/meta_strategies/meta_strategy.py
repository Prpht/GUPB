import abc

from gupb.model import characters

from ..knowledge_sources import KnowledgeSources


class MetaStrategy(abc.ABC):
    def __init__(self, knowledge_sources: KnowledgeSources):
        self.knowledge_sources: KnowledgeSources = knowledge_sources

    @abc.abstractmethod
    def decide(self) -> characters.Action:
        pass

    @abc.abstractmethod
    def praise(self, score: int) -> None:
        pass

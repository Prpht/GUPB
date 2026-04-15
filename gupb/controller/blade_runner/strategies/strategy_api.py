# strategy api
from abc import ABC, abstractmethod

from gupb.model import arenas, characters

class Strategy(ABC):
    @abstractmethod
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pass

    @abstractmethod
    def praise(self, score: int) -> None:
        pass

    @abstractmethod
    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass
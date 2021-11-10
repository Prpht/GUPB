import random
from abc import ABC, abstractmethod

from gupb.model import characters


class BB8Strategy(ABC):
    @abstractmethod
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pass


class RandomStrategy(BB8Strategy):
    def __init__(self):
        self.ACTIONS_WITH_WEIGHTS = {
            characters.Action.TURN_LEFT: 0.2,
            characters.Action.TURN_RIGHT: 0.2,
            characters.Action.STEP_FORWARD: 0.5,
            characters.Action.ATTACK: 0.1,
        }

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return random.choices(population=list(self.ACTIONS_WITH_WEIGHTS.keys()),
                              weights=list(self.ACTIONS_WITH_WEIGHTS.values()),
                              k=1)[0]


class EscapeToMenhirStrategy(BB8Strategy):
    def __init__(self):
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pass


class FindBestWeaponStrategy(BB8Strategy):
    def __init__(self):
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        pass

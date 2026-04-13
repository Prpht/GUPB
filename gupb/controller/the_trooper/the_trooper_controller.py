from gupb import controller
from gupb.model import arenas, characters

from .strategies.q_learning import QLearningStrategy

class TheTrooper(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name = first_name
        self.strategy = QLearningStrategy()

    def __hash__(self):
        return hash(self.first_name)

    def __eq__(self, value):
        return isinstance(value, TheTrooper) and self.first_name == value.first_name

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.strategy.decide(knowledge)

    def praise(self, score: int) -> None:
        self.strategy.praise(score)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.strategy.reset(game_no, arena_description)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.THE_TROOPER
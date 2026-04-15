from gupb import controller
from gupb.model import arenas
from gupb.model import characters

from .strategies.q_strategy import QStrategy

class BladeRunner(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.strategy = QStrategy()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BladeRunner):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

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
        return characters.Tabard.RED
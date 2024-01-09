from gupb import controller
from gupb.model import arenas
from gupb.model import characters

from gupb.controller.ares.ares_base import KnowledgeBase

# adding the same version
# and again for the last round

class AresController(controller.Controller):

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.knBase = KnowledgeBase()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AresController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.knBase.update(knowledge)
        action = self.knBase.choice()
        return action

    def praise(self, score: int) -> None:
        self.knBase.praise(score)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.knBase.reset(arena_description)

    @property
    def name(self) -> str:
        return f'AresController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.LIME


POTENTIAL_CONTROLLERS = [
    AresController("Nike")
]

from gupb import controller
from gupb.model import arenas, coordinates, weapons
from gupb.model import characters

from gupb.controller.aragorn.brain import Brain
from gupb.controller.aragorn.constants import OUR_BOT_NAME


class AragornController(controller.Controller):
    def __init__(self, first_name :str):
        self.first_name = first_name
        self.brain = Brain()
    
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.brain.decide(knowledge)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.brain.reset(arena_description)
    
    @property
    def name(self) -> str:
        return OUR_BOT_NAME

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ARAGORN

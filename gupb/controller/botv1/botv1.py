from gupb import controller
from gupb.model import arenas, coordinates, weapons
from gupb.model import characters

from gupb.controller.botv1.brain import Brain


class Botv1Controller(controller.Controller):
    def __init__(self, first_name :str):
        self.first_name = first_name
        self.brain = Brain()
    
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.brain.decide(knowledge)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass
    
    @property
    def name(self) -> str:
        return 'BotV1_' + self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BLUE

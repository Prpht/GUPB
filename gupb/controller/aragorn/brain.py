from gupb.model import arenas, coordinates, weapons
from gupb.model import characters

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.actions import *



class Brain:
    def __init__(self):
        self.memory = Memory()
        self.actions = {
            'spin': SpinAction(),
        }

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.memory.update(knowledge)
        actionToPerform = self.actions['spin']
        return actionToPerform.perform(self.memory)
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.memory.reset(arena_description)

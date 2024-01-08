from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model.profiling import profile

from .action import Action
from gupb.controller.aragorn.memory import Memory



class AttackAction(Action):
    @profile
    def perform(self, memory: Memory) -> Action:
        return characters.Action.ATTACK

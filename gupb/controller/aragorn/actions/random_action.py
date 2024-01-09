import random

from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model.profiling import profile

from .action import Action
from gupb.controller.aragorn.memory import Memory



class RandomAction(Action):
    @profile
    def perform(self, memory: Memory) -> characters.Action:
        available_actions = [characters.Action.STEP_FORWARD, characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
        random_action = random.choice(available_actions)
        return random_action

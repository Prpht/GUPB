from abc import abstractmethod

from gupb.model import arenas, coordinates, weapons
from gupb.model import characters

from gupb.controller.botv1.memory import Memory


class Action:
    @abstractmethod
    def perform(self, memory :Memory) -> characters.Action:
        raise NotImplementedError

class SpinAction(Action):
    def perform(self, memory :Memory) -> characters.Action:
        return characters.Action.TURN_RIGHT

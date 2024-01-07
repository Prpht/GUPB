from abc import abstractmethod

from gupb.model.coordinates import *
from gupb.model import characters

from gupb.controller.aragorn.memory import Memory



class Action:
    @abstractmethod
    def perform(self, memory :Memory) -> characters.Action:
        raise NotImplementedError

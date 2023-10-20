from abc import abstractmethod

from gupb.model import arenas, coordinates, weapons
from gupb.model import characters

from gupb.controller.aragorn.memory import Memory


class Action:
    @abstractmethod
    def perform(self, memory :Memory) -> characters.Action:
        raise NotImplementedError

class SpinAction(Action):
    def perform(self, memory :Memory) -> characters.Action:
        return characters.Action.TURN_RIGHT

class GoToAction(Action):
    def __init__(self) -> None:
        super().__init__()

        self.destination: coordinates.Coords = None
    
    def setDestination(self, destination: coordinates.Coords) -> None:
        self.destination = destination

    def perform(self, memory :Memory) -> characters.Action:
        """
        Calculates shortest path from memory.position to self.destination
        and returns the first step of the path.
        """
        
        return characters.Action.TURN_RIGHT

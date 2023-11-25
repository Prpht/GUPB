from abc import ABC, abstractmethod
from gupb.controller.r2d2.knowledge import R2D2Knowledge

from gupb.controller.r2d2.r2d2_state_machine import R2D2StateMachine
from gupb.model.characters import Action 

class Strategy(ABC):
    @abstractmethod
    def decide(self, knowledge: R2D2Knowledge, state_machine: R2D2StateMachine) -> Action:
        """
        Decides what to do next and updates the state machine accordingly.
        """
        
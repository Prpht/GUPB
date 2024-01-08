from gupb.model.coordinates import *
from gupb.model.profiling import profile

from .action import Action
from .go_to_action import GoToAction
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2
from gupb.controller.aragorn import utils



class GoToAroundAction(GoToAction):
    @profile
    def perform(self, memory: Memory) -> Action:
        if memory.position == self.destination:    
            return None
        
        if self.destination in memory.map.terrain and memory.map.terrain[self.destination].terrain_passable():
            actionToPerform = super().perform(memory)
        else:
            actionToPerform = None

        
        limit = 25
        destinationsGenerator = utils.aroundTileGenerator(self.destination)

        while actionToPerform is None and limit > 0:
            limit -= 1
            
            try:
                self.setDestination(destinationsGenerator.__next__())
            except StopIteration:
                pass

            if self.destination in memory.map.terrain and memory.map.terrain[self.destination].terrain_passable():
                actionToPerform = super().perform(memory)
            else:
                actionToPerform = None
        
        return actionToPerform

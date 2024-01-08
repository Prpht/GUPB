from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model.profiling import profile

from .action import Action
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2
from gupb.controller.aragorn import pathfinding



class GoToAction(Action):
    def __init__(self) -> None:
        super().__init__()
        self.destination: Coords = None
        self.dstFacing: characters.Facing = None
        self.useAllMovements: bool = False
        self.allowDangerous: bool = False
        self.avoidCells: list = []

        self.last_path_cost = None

    def setDestination(self, destination: Coords) -> None:
        if isinstance(destination, Coords):
            self.destination = destination
        else:
            if DEBUG:
                print("Trying to set destination to non Coords object (" + str(destination) + " of type " + str(type(destination)) + ")")

    def setDestinationFacing(self, dstFacing: characters.Facing) -> None:
        if isinstance(dstFacing, characters.Facing):
            self.dstFacing = dstFacing
        else:
            if DEBUG:
                print("Trying to set destination facing to non Facing object (" + str(dstFacing) + " of type " + str(type(dstFacing)) + ")")

    def setUseAllMovements(self, useAllMovements: bool) -> None:
        if isinstance(useAllMovements, bool):
            self.useAllMovements = useAllMovements
        else:
            if DEBUG: print("Trying to set use all movements to non bool object (" + str(useAllMovements) + " of type " + str(type(useAllMovements)) + ")")
    
    def setAllowDangerous(self, allowDangerous: bool) -> None:
        if isinstance(allowDangerous, bool):
            self.allowDangerous = allowDangerous
        else:
            if DEBUG: print("Trying to set allow dangerous to non bool object (" + str(allowDangerous) + " of type " + str(type(allowDangerous)) + ")")

    def setAvoidCells(self, avoidCells: list) -> None:
        if isinstance(avoidCells, list):
            self.avoidCells = avoidCells
        else:
            if DEBUG: print("Trying to set avoid cells to non list object (" + str(avoidCells) + " of type " + str(type(avoidCells)) + ")")
    
    def get_last_path_cost(self):
        return self.last_path_cost

    @profile
    def perform(self, memory :Memory) -> characters.Action:        
        if not self.destination:
            return None
        
        current_position = memory.position
        
        if current_position == self.destination:
            if self.dstFacing is not None and memory.facing != self.dstFacing:
                # TODO: not always turning right is optimal
                return characters.Action.TURN_RIGHT
            return None
        
        [path, cost] = pathfinding.find_path(
            memory=memory,
            start=current_position,
            end=self.destination,
            facing=memory.facing,
            useAllMovements=self.useAllMovements,
            avoid_cells=self.avoidCells
        )

        self.last_path_cost = cost
        
        # if DEBUG2 and len(self.avoidCells) > 0: memory.debugCoords = self.avoidCells
        # if DEBUG2: memory.debugCoords = path

        if DEBUG2: print("[ARAGORN|GOTO] Got path with cost:", cost)

        if path is None or len(path) <= 1:
            return None
        
        if not self.allowDangerous and cost > 200:
            return None

        nextCoord = path[1]
        
        return self.get_action_to_move_in_path(memory, nextCoord)

    def get_action_to_move_in_path(self, memory: Memory, destination: Coords) -> characters.Action:
        return pathfinding.get_action_to_move_in_path(memory.position, memory.facing, destination, self.useAllMovements)

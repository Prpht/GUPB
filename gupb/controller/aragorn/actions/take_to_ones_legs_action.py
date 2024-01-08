from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model.profiling import profile

from .action import Action
from .go_to_around_action import GoToAroundAction
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY
from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn import utils



class TakeToOnesLegsAction(Action):
    def __init__(self):
        self.dangerSourcePos = None
    
    def setDangerSourcePos(self, dangerSourcePos: Coords) -> None:
        if not isinstance(dangerSourcePos, Coords):
            if DEBUG: print("[ARAGORN|TAKE_TO_ONES_LEGS] Trying to set danger source pos to non Coords object (" + str(dangerSourcePos) + " of type " + str(type(dangerSourcePos)) + ")")
            return

        self.dangerSourcePos = dangerSourcePos
    
    @profile
    def perform(self, memory: Memory) -> Action:
        if self.dangerSourcePos is None:
            if DEBUG: print("[ARAGORN|TAKE_TO_ONES_LEGS] Danger source pos is None")
            return None
        
        runToAnySafeTileAction = self.runToAnySafeTile(memory)

        if runToAnySafeTileAction is not None:
            return runToAnySafeTileAction
        
        runAwayAction = self.runAway(memory)

        if runAwayAction is not None:
            return runAwayAction
        
        return None
    
    def runAway(self, memory: Memory) -> Action:
        # get vector from danger source to our position
        moveTowardsVector = sub_coords(memory.position, self.dangerSourcePos)
        # multiply it * 4
        moveTowardsVector = add_coords(moveTowardsVector, moveTowardsVector)
        # add it to our position
        moveTowardsPos = add_coords(memory.position, moveTowardsVector)

        # go to that position
        goToAroundAction = GoToAroundAction()
        goToAroundAction.setDestination(moveTowardsPos)
        goToAroundAction.setUseAllMovements(True)
        res = goToAroundAction.perform(memory)
        return res
    
    def howManySafeTilesAround(self, coords: Coords, memory: Memory, dangerousTiles, watchOutForPossibleOpponents: bool = False) -> int:
        possibleTiles = [
            add_coords(coords, Coords(1, 0)),
            add_coords(coords, Coords(-1, 0)),
            add_coords(coords, Coords(0, 1)),
            add_coords(coords, Coords(0, -1)),
        ]
        safeTiles = 0

        for coords in possibleTiles:
            if self.isTileGood(coords, memory, dangerousTiles):
                safeTiles += 1

                safeTiles -= self.getTileSuspiciousness(memory, coords)
        
        return safeTiles

    def isTileGood(self, coords: Coords, memory: Memory, dangerousTiles) -> bool:
        if coords not in memory.map.terrain:
            return False
        
        if not memory.map.terrain[coords].terrain_passable():
            return False
        
        if coords in dangerousTiles:
            return False
        
        if coords == memory.position:
            return False
        
        if memory.map.terrain[coords].character is not None and coords != memory.position:
            return False

        return True
    
    def getTileSuspiciousness(self, memory: Memory, coords: Coords):
        suspiciousness = 0
        
        if coords in memory.map.enemiesPositionsApproximation.getEnemiesTiles():
            suspiciousness += 0.1
        
        neighbors = [
            add_coords(coords, Coords(1, 0)),
            add_coords(coords, Coords(-1, 0)),
            add_coords(coords, Coords(0, 1)),
            add_coords(coords, Coords(0, -1)),
        ]

        for neighbor in neighbors:
            if neighbor in memory.map.enemiesPositionsApproximation.getEnemiesTiles():
                suspiciousness += 0.1
        
        return suspiciousness

    def runToAnySafeTile(self, memory: Memory) -> Action:
        dangerousTiles = list(memory.map.getDangerousTilesWithDangerSourcePos(memory.tick).keys())
        
        possibleTiles = [
            add_coords(memory.position, Coords(1, 0)),
            add_coords(memory.position, Coords(-1, 0)),
            add_coords(memory.position, Coords(0, 1)),
            add_coords(memory.position, Coords(0, -1)),
        ]
        safeTiles = {}

        farAwayCoords = memory.getSectionCenterPos(memory.getOppositeSection())
        path,cost = pathfinding.find_path(memory=memory, start=memory.position, end=farAwayCoords, facing=memory.facing, useAllMovements=True)

        destinationsGenerator = utils.aroundTileGenerator(farAwayCoords)
        limit = 25

        while path is None and limit > 0:
            limit -= 1
            
            try:
                farAwayCoords = destinationsGenerator.__next__()
            except StopIteration:
                pass

            path,cost = pathfinding.find_path(memory=memory, start=memory.position, end=farAwayCoords, facing=memory.facing, useAllMovements=True)
        
        if cost is not None and cost is not INFINITY and len(path) >= 2:
            goFarAwayCoord = path[1]
        else:
            goFarAwayCoord = None

        for coords in possibleTiles:
            if not self.isTileGood(coords, memory, dangerousTiles):
                continue
            
            safeTiles[coords] = self.howManySafeTilesAround(coords, memory, dangerousTiles, True)
            
            safeTiles[coords] -= self.getTileSuspiciousness(memory, coords)

            safeTiles[coords] += 3 if goFarAwayCoord == coords else 0

        # get coords from safeTiles key with maximum value
        maxSafeTile = None
        maxSafeTileValue = -INFINITY

        for coords in safeTiles:
            if safeTiles[coords] > maxSafeTileValue:
                maxSafeTileValue = safeTiles[coords]
                maxSafeTile = coords
            
        # IF THERES NEARBY SAFE TILE, GO TO IT
        if maxSafeTile is None:
            return None
        
        if maxSafeTile == add_coords(memory.position, memory.facing.value):
            return characters.Action.STEP_FORWARD
        elif maxSafeTile == add_coords(memory.position, memory.facing.turn_left().value):
            return characters.Action.STEP_LEFT
        elif maxSafeTile == add_coords(memory.position, memory.facing.turn_right().value):
            return characters.Action.STEP_RIGHT
        elif maxSafeTile == add_coords(memory.position, memory.facing.turn_left().turn_left().value):
            return characters.Action.STEP_BACKWARD
        
        return None

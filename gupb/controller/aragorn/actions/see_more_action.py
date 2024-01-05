from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model import weapons
from gupb.model.profiling import profile

from .action import Action
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY
from gupb.controller.aragorn import utils



class SeeMoreAction(Action):
    def isGoingToSomeDirection(self, memory: Memory) -> bool:
        last2Actions = memory.getLastActions()[-2:]
        
        if len(last2Actions) < 2:
            return False
        
        return (
            last2Actions[0] == last2Actions[1]
            and last2Actions[0] in [
                characters.Action.STEP_LEFT,
                characters.Action.STEP_RIGHT,
                characters.Action.STEP_BACKWARD,
            ]
        )
    
    def getForwardDirection(self, memory: Memory) -> Coords:
        return sub_coords(memory.position, memory.lastPosition)
    
    def directionWithMostVisibleCoords(self, memory: Memory) -> Coords:
        amountOfVisibleCoords = {
            characters.Facing.UP: 0,
            characters.Facing.RIGHT: 0,
            characters.Facing.DOWN: 0,
            characters.Facing.LEFT: 0,
        }

        for facing in amountOfVisibleCoords:
            amountOfVisibleCoords[facing] = len(memory.map.visible_coords(facing, memory.position, memory.getCurrentWeaponClass()))
        
        maxVisibleCoords = -INFINITY
        maxVisibleCoordsFacing = None

        for facing in amountOfVisibleCoords:
            if amountOfVisibleCoords[facing] > maxVisibleCoords:
                maxVisibleCoords = amountOfVisibleCoords[facing]
                maxVisibleCoordsFacing = facing
        
        return maxVisibleCoordsFacing.value
    
    def getNearbyOpponentPos(self, memory: Memory) -> Coords:
        nearbyOponentDistance = INFINITY
        nearbyOponentPos = None
        
        r = 3

        for x in range(memory.position.x - r, memory.position.x + r + 1):
            for y in range(memory.position.x - r, memory.position.x + r + 1):
                coords = Coords(x, y)

                if coords not in memory.map.terrain:
                    continue

                if memory.map.terrain[coords].character is None or coords == memory.position:
                    continue
                
                distance = utils.manhattanDistance(memory.position, coords)

                if distance < nearbyOponentDistance:
                    nearbyOponentDistance = distance
                    nearbyOponentPos = coords

        return nearbyOponentPos, nearbyOponentDistance
    
    def getNearbyPossibleOponentPos(self, memory: Memory) -> Coords:
        possibleEnemiesTiles = memory.map.enemiesPositionsApproximation.getEnemiesTiles()
        minDist = 2
        minPos = None

        for peTile in possibleEnemiesTiles:
            dist = utils.manhattanDistance(memory.position, peTile)

            if dist < minDist:
                minDist = dist
                minPos = peTile
        
        if minPos is None:
            return None, INFINITY

        return minPos, minDist
    
    def getNearbyDangerPos(self, memory: Memory):
        nearbyOpponentPos, nearbyOpponentDist = self.getNearbyOpponentPos(memory)
        nearbyPossibleOpponentPos, nearbyPossibleOpponentDist = self.getNearbyPossibleOponentPos(memory)

        nearbyDangerPos = None
        nearbyDangerDist = INFINITY

        if nearbyOpponentPos is not None:
            nearbyDangerPos = nearbyOpponentPos
            nearbyDangerDist = nearbyOpponentDist
        
        if nearbyPossibleOpponentPos is not None and nearbyPossibleOpponentDist < nearbyDangerDist:
            nearbyDangerPos = nearbyPossibleOpponentPos
            nearbyDangerDist = nearbyPossibleOpponentDist
        
        return nearbyDangerPos

    
    def getMostDefensiveDirection(self, memory :Memory, nearbyOpponentPos :Coords) -> Coords:
        # get vector to closest enemy
        opponentDirection = sub_coords(nearbyOpponentPos, memory.position)

        # normalize its coords
        maxC = max(abs(opponentDirection.x), abs(opponentDirection.y))
        opponentDirection = Coords(opponentDirection.x // maxC, opponentDirection.y // maxC)
        
        # if both coords are 1s or -1s, set one of them to 0
        if opponentDirection.x != 0 and opponentDirection.y != 0:
            opponentDirection = Coords(opponentDirection.x, 0)

        return opponentDirection
    
    def lookAtTile(self, memory: Memory, tile: Coords) -> Action:
        if tile == memory.facing.value:
            # seems OK - do other actions
            return None
        
        if tile == memory.facing.turn_left().value:
            return characters.Action.TURN_LEFT
        
        if tile == memory.facing.turn_right().value:
            return characters.Action.TURN_RIGHT
        
        if tile == memory.facing.turn_left().turn_left().value:
            return characters.Action.TURN_RIGHT

    @profile
    def perform(self, memory: Memory) -> Action:
        nearbyDangerPos = self.getNearbyDangerPos(memory)

        if nearbyDangerPos is not None:
            defensiveDirection = self.getMostDefensiveDirection(memory, nearbyDangerPos)
            return self.lookAtTile(memory, defensiveDirection)

        if not memory.getCurrentWeaponClass() != weapons.Amulet and self.isGoingToSomeDirection(memory):
            forwardDirection = self.getForwardDirection(memory)
            return self.lookAtTile(memory, forwardDirection)
        
        # bestDirection = self.directionWithMostVisibleCoords(memory)
        # return self.lookAtTile(memory, bestDirection)

        return None

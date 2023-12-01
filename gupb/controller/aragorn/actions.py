from abc import abstractmethod
import random
from typing import NamedTuple, Optional, List, Tuple
from collections import defaultdict

from gupb.model.coordinates import *
from gupb.model import characters
from gupb.model import consumables
from gupb.model import weapons
from gupb.model.profiling import profile

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2, INFINITY, OUR_BOT_NAME
from gupb.controller.aragorn import pathfinding
from gupb.controller.aragorn import utils



class Action:
    @abstractmethod
    def perform(self, memory :Memory) -> characters.Action:
        raise NotImplementedError

class SpinAction(Action):
    def __init__(self) -> None:
        super().__init__()
        self.spin = characters.Action.TURN_RIGHT
    
    @profile
    def perform(self, memory :Memory) -> characters.Action:
        return self.spin
    
    def setSpin(self, spin: characters.Action) -> None:
        if spin not in [
            characters.Action.TURN_RIGHT,
            characters.Action.TURN_LEFT
        ]:
            return
        
        self.spin = spin

class RandomAction(Action):
    @profile
    def perform(self, memory: Memory) -> characters.Action:
        available_actions = [characters.Action.STEP_FORWARD, characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
        random_action = random.choice(available_actions)
        return random_action

class AttackAction(Action):
    @profile
    def perform(self, memory: Memory) -> Action:
        return characters.Action.ATTACK

class GoToAction(Action):
    def __init__(self) -> None:
        super().__init__()
        self.destination: Coords = None
        self.dstFacing: characters.Facing = None
        self.useAllMovements: bool = False
        self.allowDangerous: bool = False

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
        
        [path, cost] = pathfinding.find_path(memory=memory, start=current_position, end=self.destination, facing=memory.facing, useAllMovements=self.useAllMovements)

        if path is None or len(path) <= 1:
            return None
        
        if not self.allowDangerous and cost > 40:
            return None

        nextCoord = path[1]
        
        return self.get_action_to_move_in_path(memory, nextCoord)

    def get_action_to_move_in_path(self, memory: Memory, destination: Coords) -> characters.Action:
        return pathfinding.get_action_to_move_in_path(memory.position, memory.facing, destination)
    
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

class ExploreAction(Action):
    MIN_DISTANCE_TO_SECTION_CENTER_TO_MARK_IT_AS_EXPLORED = 4

    def __init__(self) -> None:
        self.is_section_explored = [False, False, False, False, False]
        self.firstPerform = True
        self.plan = [1, 2, 3, 4, 0]
        self.minDistanceToSectionCenterToMarkItAsExplored = 7
        self.regeneratePlanTimes = 0
    
    def __markSectionAsExplored(self, section: int) -> None:
        if section < len(self.is_section_explored):
            self.is_section_explored[section] = True
        else:
            for _ in range(section - len(self.is_section_explored) + 1):
                self.is_section_explored.append(False)
            self.is_section_explored[section] = True
    
    def __getNextSectionFromPlan(self):
        for section in self.plan:
            if not self.is_section_explored[section]:
                return section
        
        self.regeneratePlanTimes += 1

        if self.regeneratePlanTimes > 5:
            return None

        for i in range(len(self.is_section_explored)):
            self.is_section_explored[i] = False
        
        return self.plan[0]

    @profile
    def perform(self, memory: Memory) -> Action:
        currentSection = memory.getCurrentSection()

        if self.firstPerform:
            self.__markSectionAsExplored(currentSection)
            self.minDistanceToSectionCenterToMarkItAsExplored = (memory.map.size[0] + memory.map.size[1]) / 2 / 5
            self.firstPerform = False
            oppositeSection = memory.getOppositeSection()

            remainingSections = [section for section in range(len(self.is_section_explored)) if section not in [currentSection, oppositeSection]]
            random.shuffle(remainingSections)

            self.plan = [currentSection, oppositeSection] + remainingSections

        exploreToSection = self.__getNextSectionFromPlan()

        if exploreToSection is None:
            return None
        
        exploreToPos = memory.getSectionCenterPos(exploreToSection)

        if exploreToPos is None:
            return None

        if utils.coordinatesDistance(memory.position, exploreToPos) <= self.MIN_DISTANCE_TO_SECTION_CENTER_TO_MARK_IT_AS_EXPLORED:
            self.__markSectionAsExplored(exploreToSection)
            return self.perform(memory)
        
        # if center outside of safe mehhir ring, mark it as explored
        [menhirPos, prob] = memory.map.menhirCalculator.approximateMenhirPos(memory.tick)

        if menhirPos is not None and utils.coordinatesDistance(exploreToPos, menhirPos) > memory.map.mist_radius / 2:
            self.__markSectionAsExplored(exploreToSection)
            return self.perform(memory)

        gotoAroundAction = GoToAroundAction()
        gotoAroundAction.setDestination(exploreToPos)
        gotoAroundAction.setAllowDangerous(True)
        res = gotoAroundAction.perform(memory)

        if res is None:
            if DEBUG: print("[ARAGORN|EXPLORE] Cannot reach section", exploreToSection, "at", exploreToPos, ", marking it as explored")
            self.__markSectionAsExplored(exploreToSection)
            return self.perform(memory)
        
        if DEBUG: print("[ARAGORN|EXPLORE] Going to section", exploreToSection, "at", exploreToPos)
        return res

class AdvancedExploreAction(ExploreAction):
    def __init__(self) -> None:
        super().__init__()
        
        self.visitedCenter = False
        self.seenAllTiles = False

        self.standableCenter = None
    
    def __findStandableCenter(self, memory: Memory):
        center = coordinates.Coords(round(memory.map.size[0] / 2), round(memory.map.size[1] / 2))
        
        destinationsGenerator = utils.aroundTileGenerator(center)
        limit = 25

        while self.standableCenter is None and limit > 0:
            limit -= 1
            
            try:
                center = destinationsGenerator.__next__()
            except StopIteration:
                pass

            if center in memory.map.terrain and memory.map.terrain[center].terrain_passable():
                self.standableCenter = center
    
    def __seen(self, memory: Memory, coords: Coords):
        if self.standableCenter not in memory.map.terrain:
            return True
        
        if not hasattr(memory.map.terrain[self.standableCenter], 'seen'):
            return True
        
        return memory.map.terrain[self.standableCenter].seen
    
    def __getNextUnseenTileCoords(self, memory: Memory) -> Coords:
        for r in range(1, 15):
            for x in range(-r, r + 1):
                for y in range(-r, r + 1):
                    coords = add_coords(memory.position, Coords(x, y))

                    if not self.__seen(memory, coords):
                        return coords

        return None

    def __goto(self, memory: Memory, coords: Coords) -> Action:
        goToAroundAction = GoToAroundAction()
        goToAroundAction.setDestination(coords)
        goToAroundAction.setAllowDangerous(False)
        return goToAroundAction.perform(memory)
    
    @profile
    def perform(self, memory: Memory) -> Action:
        if self.standableCenter is None:
            self.__findStandableCenter(memory)
        

        
        # go to center first

        if self.__seen(memory, self.standableCenter):
            self.visitedCenter = True
        
        if not self.visitedCenter:
            self.visitedCenter = True
            return self.__goto(memory, self.standableCenter)
        
        # explore unseen tiles

        nextTileToExplore = self.__getNextUnseenTileCoords(memory)

        if nextTileToExplore is None:
            self.seenAllTiles = True
        
        if not self.seenAllTiles:
            return self.__goto(memory, nextTileToExplore)
        
        # default to normal explore
        
        return super().perform(memory)

class AttackClosestEnemyAction(Action):
    OUTDATED_DATA_TICKS = 16

    @profile
    def perform(self, memory: Memory) -> Action:
        # GET CLOSEST ENEMY
        closestEnemy = None
        closestEnemyDistance = INFINITY

        if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Searching for closest enemy")

        for coords in memory.map.terrain:
            if (
                # tile has character
                memory.map.terrain[coords].character is not None
                # ignore if data is outdated
                and (not hasattr(memory.map.terrain[coords], 'tick') or memory.map.terrain[coords].tick >= memory.tick - self.OUTDATED_DATA_TICKS)
                # ignore ourselfs
                and memory.map.terrain[coords].character.controller_name != OUR_BOT_NAME
                # ignore our position
                and memory.position != coords
                # ignore enemies with greater health
                # and memory.map.terrain[coords].character.health <= memory.health
                # ignore enemies with health greater than reward of killing (potion restore)
                # and memory.map.terrain[coords].character.health <= consumables.POTION_RESTORED_HP
            ):
                distance = utils.coordinatesDistance(memory.position, coords)
                
                if distance < closestEnemyDistance:
                    closestEnemy = coords
                    closestEnemyDistance = distance
        
        if closestEnemy is None:
            if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] No closest enemy found")
            return None
        
        if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Closest enemy found at", closestEnemy, "with distance", closestEnemyDistance)
        
        # CLOSEST ENEMY IS TOO FAR
        # just approach him
        if closestEnemyDistance > 3:
            if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Closest enemy is too far, going closer")
            goToAttackAction = GoToAction()
            goToAttackAction.setDestination(closestEnemy)
            goToAttackAction.setUseAllMovements(True)
            ret = goToAttackAction.perform(memory)
            if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Closest enemy is too far, going closer, result:", ret)
            return ret

        # IF CLOSEST ENEMY IS NEARBY
        # GET CLOSEST FIELD YOU CAN ATTACK FROM
        # BY CALCULATING DETAILED PATHS COSTS
        if DEBUG2: print("[ARAGORN|ATTACK_CLOSEST_ENEMY] Closest enemy is nearby, calculating detailed paths costs")
        currentWeapon :weapons.Weapon = memory.getCurrentWeaponClass()

        if currentWeapon is None:
            return None
        
        positionsToAttackFrom = {}
        minNormalDistance = INFINITY

        for facing in [
            characters.Facing.UP,
            characters.Facing.DOWN,
            characters.Facing.LEFT,
            characters.Facing.RIGHT,
        ]:
            for pos in currentWeapon.cut_positions(memory.map.terrain, closestEnemy, facing.turn_left().turn_left()):
                tmpDistance = utils.coordinatesDistance(memory.position, pos)
                
                if tmpDistance < minNormalDistance:
                    minNormalDistance = tmpDistance
                
                if tmpDistance > minNormalDistance + 1:
                    # do not add positions that are too far
                    continue

                positionsToAttackFrom[(pos, facing)] = INFINITY
        
        for (pos, facing) in positionsToAttackFrom:
            tmpDistance = utils.coordinatesDistance(memory.position, pos)
            
            if tmpDistance > minNormalDistance + 1:
                # do not add positions that are too far
                # - leave them as INFINITY
                continue

            positionsToAttackFrom[(pos, facing)] = pathfinding.get_path_cost(memory, memory.position, pos, facing)
        
        minCost = INFINITY
        minCostPos = None
        minCostFacing = None

        for (pos, facing) in positionsToAttackFrom:
            if positionsToAttackFrom[(pos, facing)] < minCost:
                minCost = positionsToAttackFrom[(pos, facing)]
                minCostPos = pos
                minCostFacing = facing
        
        if minCostPos is None:
            return None
        
        # GO TO CLOSEST FIELD YOU CAN ATTACK FROM

        goToAttackAction = GoToAction()
        goToAttackAction.setDestination(minCostPos)
        goToAttackAction.setDestinationFacing(minCostFacing)
        goToAttackAction.setUseAllMovements(True)
        return goToAttackAction.perform(memory)

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
    
    def howManySafeTilesAround(self, coords: Coords, memory: Memory, dangerousTiles) -> int:
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
        
        if memory.map.terrain[coords].character is not None and memory.map.terrain[coords].character.controller_name != OUR_BOT_NAME:
            return False

        return True
    
    def runToAnySafeTile(self, memory: Memory) -> Action:
        dangerousTiles = list(memory.map.getDangerousTilesWithDangerSourcePos(memory.tick).keys())
        
        possibleTiles = [
            add_coords(memory.position, Coords(1, 0)),
            add_coords(memory.position, Coords(-1, 0)),
            add_coords(memory.position, Coords(0, 1)),
            add_coords(memory.position, Coords(0, -1)),
        ]
        safeTiles = {}

        for coords in possibleTiles:
            if not self.isTileGood(coords, memory, dangerousTiles):
                continue
            
            safeTiles[coords] = self.howManySafeTilesAround(coords, memory, dangerousTiles)

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
    
    def getNearbyOpponentPos(self, memory: Memory) -> bool:
        nearbyOponentDistance = INFINITY
        nearbyOponentPos = None
        
        r = 3

        for x in range(memory.position.x - r, memory.position.x + r + 1):
            for y in range(memory.position.x - r, memory.position.x + r + 1):
                coords = Coords(x, y)

                if coords not in memory.map.terrain:
                    continue

                if memory.map.terrain[coords].character is None or memory.map.terrain[coords].character.controller_name == OUR_BOT_NAME:
                    continue
                
                distance = utils.coordinatesDistance(memory.position, coords)

                if distance < nearbyOponentDistance:
                    nearbyOponentDistance = distance
                    nearbyOponentPos = coords

        return nearbyOponentPos
    
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
        nearbyOpponentPos = self.getNearbyOpponentPos(memory)

        if nearbyOpponentPos is not None:
            defensiveDirection = self.getMostDefensiveDirection(memory, nearbyOpponentPos)
            return self.lookAtTile(memory, defensiveDirection)

        if self.isGoingToSomeDirection(memory):
            forwardDirection = self.getForwardDirection(memory)
            return self.lookAtTile(memory, forwardDirection)
        
        # bestDirection = self.directionWithMostVisibleCoords(memory)
        # return self.lookAtTile(memory, bestDirection)

        return None

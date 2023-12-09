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
from gupb.controller.aragorn.constants import DEBUG, INFINITY, OUR_BOT_NAME
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

        gotoAroundAction = GoToAroundAction()
        gotoAroundAction.setDestination(exploreToPos)
        res = gotoAroundAction.perform(memory)

        if res is None:
            if DEBUG: print("[ARAGORN|EXPLORE] Cannot reach section", exploreToSection, "at", exploreToPos, ", marking it as explored")
            self.__markSectionAsExplored(exploreToSection)
            return self.perform(memory)
        
        if DEBUG: print("[ARAGORN|EXPLORE] Going to section", exploreToSection, "at", exploreToPos)
        return res
    
class BasicExploreAction(Action):
    @profile
    def perform(self, memory: Memory) -> Action:
        currentSection = memory.getCurrentSection()
        
        if currentSection == 0:
            gotoVector = Coords(-1, -1)
        elif currentSection == 1:
            gotoVector = Coords(1, 0)
        elif currentSection == 2:
            gotoVector = Coords(-1, -1)
        elif currentSection == 3:
            gotoVector = Coords(1, 0)
        else:
            gotoVector = Coords(-1, -1)
        
        mul = 3
        gotoVector = Coords(gotoVector.x * mul, gotoVector.y * mul)
        exploreToPos = add_coords(memory.position, gotoVector)


        gotoAroundAction = GoToAroundAction()
        gotoAroundAction.setDestination(exploreToPos)
        res = gotoAroundAction.perform(memory)

        if res is not None:
            return res
        
        gotoVector = Coords(random.randint(-1, 1), random.randint(-1, 1))
        gotoVector = Coords(gotoVector.x * mul, gotoVector.y * mul)
        exploreToPos = add_coords(memory.position, gotoVector)

        gotoAroundAction.setDestination(exploreToPos)
        res = gotoAroundAction.perform(memory)

        return res

class AttackClosestEnemyAction(Action):
    OUTDATED_DATA_TICKS = 16

    @profile
    def perform(self, memory: Memory) -> Action:
        # GET CLOSEST ENEMY
        closestEnemy = None
        closestEnemyDistance = INFINITY

        for coords in memory.map.terrain:
            if (
                # tile has character
                memory.map.terrain[coords].character is not None
                # ignore if data is outdated
                and (hasattr(memory.map.terrain[coords], 'tick') and memory.map.terrain[coords].tick >= memory.tick - self.OUTDATED_DATA_TICKS)
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
            return None
        
        # CLOSEST ENEMY IS TOO FAR
        # just approach him
        if closestEnemyDistance > 3:
            goToAttackAction = GoToAction()
            goToAttackAction.setDestination(closestEnemy)
            return goToAttackAction.perform(memory)

        # IF CLOSEST ENEMY IS NEARBY
        # GET CLOSEST FIELD YOU CAN ATTACK FROM
        # BY CALCULATING DETAILED PATHS COSTS
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

    def runToAnySafeTile(self, memory: Memory) -> Action:
        dangerousTiles = memory.map.getDangerousTiles()
        
        possibleTiles = [
            memory.position,
            add_coords(memory.position, Coords(1, 0)),
            add_coords(memory.position, Coords(-1, 0)),
            add_coords(memory.position, Coords(0, 1)),
            add_coords(memory.position, Coords(0, -1)),
        ]
        safeTiles = {}

        for coords in possibleTiles:
            if coords not in memory.map.terrain:
                continue
            
            if not memory.map.terrain[coords].terrain_passable():
                continue
            
            if coords in dangerousTiles:
                continue
            
            safeTiles[coords] = utils.coordinatesDistance(coords, self.dangerSourcePos)

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
        
        goToAction = GoToAction()
        goToAction.setDestination(maxSafeTile)
        return goToAction.perform(memory)

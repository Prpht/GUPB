from abc import abstractmethod
import random
from typing import NamedTuple, Optional, List, Tuple

from gupb.model.coordinates import *
from gupb.model import characters

from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, INFINITY
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
    def perform(self, memory: Memory) -> characters.Action:
        available_actions = [characters.Action.STEP_FORWARD, characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
        random_action = random.choice(available_actions)
        return random_action

class AttackAction(Action):
    def perform(self, memory: Memory) -> Action:
        return characters.Action.ATTACK

class GoToAction(Action):
    def __init__(self) -> None:
        super().__init__()
        self.destination: Coords = None
        self.dstFacing: characters.Facing = None

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

    def perform(self, memory :Memory) -> characters.Action:        
        if not self.destination:
            return None
        
        current_position = memory.position
        
        if current_position == self.destination:
            if self.dstFacing is not None and memory.facing != self.dstFacing:
                # TODO: not always turning right is optimal
                return characters.Action.TURN_RIGHT
            return None
        
        [path, cost] = pathfinding.find_path(memory=memory, start=current_position, end=self.destination, facing = memory.facing)

        if path is None or len(path) <= 1:
            return None

        nextCoord = path[1]
        
        return self.get_action_to_move_in_path(memory, nextCoord)

    def get_action_to_move_in_path(self, memory: Memory, destination: Coords) -> characters.Action:
        return pathfinding.get_action_to_move_in_path(memory.position, memory.facing, destination)
    
class GoToAroundAction(GoToAction):
    def perform(self, memory: Memory) -> Action:
        if memory.position == self.destination:    
            return None

        actionToPerform = super().perform(memory)
        
        limit = 25
        destinationsGenerator = utils.aroundTileGenerator(self.destination)

        while actionToPerform is None and limit > 0:
            limit -= 1
            
            try:
                self.setDestination(destinationsGenerator.__next__())
            except StopIteration:
                pass

            actionToPerform = super().perform(memory)
        
        return actionToPerform

class ExploreAction(Action):
    MIN_DISTANCE_TO_SECTION_CENTER_TO_MARK_IT_AS_EXPLORED = 4

    def __init__(self) -> None:
        self.is_section_explored = [False, False, False, False, False]
        self.firstPerform = True
        self.plan = [1, 2, 3, 4, 0]
        self.minDistanceToSectionCenterToMarkItAsExplored = 7
    
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

    def perform(self, memory: Memory) -> Action:
        currentSection = memory.getCurrentSection()

        if self.firstPerform:
            self.__markSectionAsExplored(currentSection)
            self.minDistanceToSectionCenterToMarkItAsExplored = (memory.map.size[0] + memory.map.size[1]) / 2 / 5
            self.firstPerform = False
            oppositeSection = memory.getOppositeSection()

            remainingSections = [section for section in range(len(self.is_section_explored)) if section not in [currentSection, oppositeSection]]
            random.shuffle(remainingSections)

            self.plan = [oppositeSection] + remainingSections

        exploreToSection = self.__getNextSectionFromPlan()
        exploreToPos = memory.getSectionCenterPos(exploreToSection)

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

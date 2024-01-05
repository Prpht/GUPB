import random

from gupb.model.profiling import profile

from .action import Action
from .go_to_around_action import GoToAroundAction
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2
from gupb.controller.aragorn import utils



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
        gotoAroundAction.setAllowDangerous(False)
        gotoAroundAction.setUseAllMovements(False)
        res = gotoAroundAction.perform(memory)

        if res is None:
            if DEBUG: print("[ARAGORN|EXPLORE] Cannot reach section", exploreToSection, "at", exploreToPos, ", marking it as explored")
            self.__markSectionAsExplored(exploreToSection)
            return self.perform(memory)
        
        if DEBUG: print("[ARAGORN|EXPLORE] Going to section", exploreToSection, "at", exploreToPos)
        return res

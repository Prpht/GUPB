from gupb.model.coordinates import *
from gupb.model.profiling import profile

from .action import Action
from .explore_action import ExploreAction
from .go_to_around_action import GoToAroundAction
from gupb.controller.aragorn.memory import Memory
from gupb.controller.aragorn.constants import DEBUG, DEBUG2
from gupb.controller.aragorn import utils



class AdvancedExploreAction(ExploreAction):
    def __init__(self) -> None:
        super().__init__()
        
        self.visitedCenter = False
        self.seenAllTiles = False

        self.standableCenter = None
        self.nextTileToExplore = None
    
    def __findStandableCenter(self, memory: Memory):
        center = Coords(round(memory.map.size[0] / 2), round(memory.map.size[1] / 2))
        
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
        if coords not in memory.map.terrain:
            return True
        
        if not hasattr(memory.map.terrain[coords], 'seen'):
            return False
        
        return memory.map.terrain[coords].seen
    
    def __getNextUnseenTileCoords(self, memory: Memory) -> Coords:
        for r in range(1, max(memory.map.size[0], memory.map.size[1])):
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
        goToAroundAction.setUseAllMovements(False)
        ret = goToAroundAction.perform(memory)
        if DEBUG2: print("[ARAGORN|ADVANCED_EXPLORE] Going to around action, coords:", coords, "action:", ret)
        return ret
    
    @profile
    def perform(self, memory: Memory) -> Action:
        if DEBUG2: print("[ARAGORN|ADVANCED_EXPLORE] Advanced explore")

        if not self.visitedCenter and self.standableCenter is None:
            if DEBUG2: print("[ARAGORN|ADVANCED_EXPLORE] Finding standable center")
            self.__findStandableCenter(memory)
        
        if self.standableCenter is None:
            # if we cannot find standable center, just do normal explore
            self.visitedCenter = True

        
        # go to center first

        if self.__seen(memory, self.standableCenter):
            if DEBUG2: print("[ARAGORN|ADVANCED_EXPLORE] Seen center")
            self.visitedCenter = True
        
        if not self.visitedCenter:
            if DEBUG2: print("[ARAGORN|ADVANCED_EXPLORE] Going towards center")
            return self.__goto(memory, self.standableCenter)
        
        # explore unseen tiles
        
        if self.nextTileToExplore is not None and self.__seen(memory, self.nextTileToExplore):
            self.nextTileToExplore = None
        
        if self.nextTileToExplore is None:
            self.nextTileToExplore = self.__getNextUnseenTileCoords(memory)

        if self.nextTileToExplore is None:
            if DEBUG2: print("[ARAGORN|ADVANCED_EXPLORE] Seen all tiles")
            self.seenAllTiles = True
        
        if not self.seenAllTiles:
            if DEBUG2: print("[ARAGORN|ADVANCED_EXPLORE] Going towards unseen tile, coords:", self.nextTileToExplore)
            return self.__goto(memory, self.nextTileToExplore)
        
        # default to normal explore

        if DEBUG2: print("[ARAGORN|ADVANCED_EXPLORE] Defaulting to normal explore")
        return super().perform(memory)

from gupb.model import coordinates, effects
from gupb.model.profiling import profile

from gupb.controller.aragorn.constants import DEBUG, INFINITY



class MenhirCalculator:
    def __init__(self, map: 'Map') -> None:
        self.map = map

        self.menhirPos = None
        self.mistCoordinates = []
        self.lastChangeTick = -INFINITY
        self.lastResult = None

    def setMenhirPos(self, menhirPos: coordinates.Coords) -> None:
        if not isinstance(menhirPos, coordinates.Coords):
            print("[MenhirCalculator] Trying to set menhir pos to non Coords object (" + str(menhirPos) + " of type " + str(type(menhirPos)) + ")")
        self.menhirPos = menhirPos
    
    def addMist(self, mistPos: coordinates.Coords, tick :int) -> None:
        if mistPos not in self.mistCoordinates:
            self.lastChangeTick = tick
            self.mistCoordinates.append(mistPos)
    
    def isMenhirPosFound(self) -> bool:
        return self.menhirPos is not None
    
    @profile
    def approximateMenhirPos(self, tick :int) -> coordinates.Coords:
        mistRadius = self.map.mist_radius

        if self.menhirPos is not None:
            return self.menhirPos, 1
        
        mistCoordinates = self.mistCoordinates
        if len(mistCoordinates) == 0:
            return None, None
        
        if self.lastChangeTick >= tick - 13 and self.lastResult is not None:
            return self.lastResult
        
        bestMenhirPos = None
        bestMistAmount = 0

        for try_menhir_y in range(self.map.size[1]):
            for try_menhir_x in range(self.map.size[0]):
                try_menhir = coordinates.Coords(try_menhir_x, try_menhir_y)

                if try_menhir in mistCoordinates:
                    continue

                mistFound = 0
                mistMax = 0

                for coords in self.map.terrain:
                    if hasattr(self.map.terrain[coords], 'tick'):
                        if self.map.terrain[coords].tick < tick - 16:
                            continue
                    
                    distance = int(((coords.x - try_menhir.x) ** 2 +
                                    (coords.y - try_menhir.y) ** 2) ** 0.5)
                    
                    if distance >= mistRadius:
                        mistMax += 1

                        if effects.Mist in self.map.terrain[coords].effects:
                            mistFound += 1
                    
                    if distance < mistRadius:
                        if effects.Mist in self.map.terrain[coords].effects:
                            mistFound -= 1
                
                if mistMax == 0:
                    # no mist should be found = it was not seen yet
                    # -> make proportion = 0 (this case doesnt give any information)
                    mistMax = 1
                    mistFound = 0

                if mistFound < 0:
                    mistFound = 0
                
                if mistFound/mistMax > bestMistAmount:
                    bestMenhirPos = try_menhir
                    bestMistAmount = mistFound/mistMax
        
        self.lastChangeTick = tick
        self.lastResult = (bestMenhirPos, bestMistAmount)
        return self.lastResult

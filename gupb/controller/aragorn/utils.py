from gupb.model import coordinates

def coordinatesDistance(coordA, coordB):
    return ((coordA.x - coordB.x) ** 2 + (coordA.y - coordB.y) ** 2) ** (1/2)

def aroundTileGenerator(aroundDestination :coordinates.Coords):
    if not isinstance(aroundDestination, coordinates.Coords):
        return None
    
    wantedR = 1

    for r in range(1, 7):
        hadAnything = False

        for x in range(-r, r + 1):
            for y in range(-r, r + 1):
                if coordinatesDistance(coordinates.Coords(x, y), coordinates.Coords(0, 0)) == wantedR:
                    hadAnything = True
                    yield coordinates.add_coords(aroundDestination, coordinates.Coords(x, y))
        
        if not hadAnything:
            wantedR += 1

def closestTileFromWithCondition(aroundDestination :coordinates.Coords, condition, limit = 25, resultIfNotFound = None):
    if condition(aroundDestination):
        return aroundDestination
    
    destinationsGenerator = aroundTileGenerator(aroundDestination)

    while limit > 0:
        try:
            nextDestination = destinationsGenerator.__next__()

            if condition(nextDestination):
                return nextDestination
        except StopIteration:
            pass

        limit -= 1

    return resultIfNotFound

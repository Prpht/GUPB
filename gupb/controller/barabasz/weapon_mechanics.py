from gupb.model import arenas, coordinates
from gupb.model import characters
from gupb.model.tiles import TileDescription



def deathzone(weapon: str, position: coordinates.Coords, facing: coordinates.Coords):
    death_coords = []

    if weapon == 'axe':
        if facing == coordinates.Coords(0, -1):  # UP
            death_coords.append(coordinates.add_coords(position, facing))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,-1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,-1)))
        if facing == coordinates.Coords(0, 1):  # DOWN
            death_coords.append(coordinates.add_coords(position, facing))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,1)))
        if facing == coordinates.Coords(-1, 0):  # LEFT
            death_coords.append(coordinates.add_coords(position, facing))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,-1)))
        if facing == coordinates.Coords(1, 0):  # RIGHT
            death_coords.append(coordinates.add_coords(position, facing))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,-1)))
    
    # TODO: Implement bow mechanics properly
    if weapon == 'sword' or weapon == 'bow':
        if facing == coordinates.Coords(0, -1):  # UP
            death_coords.append(coordinates.add_coords(position, facing))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(0,-2)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(0,-3)))
        if facing == coordinates.Coords(0, 1):  # DOWN
            death_coords.append(coordinates.add_coords(position, facing))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(0,2)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(0,3)))
        if facing == coordinates.Coords(-1, 0):  # LEFT
            death_coords.append(coordinates.add_coords(position, facing))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-2,0)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-3,0)))
        if facing == coordinates.Coords(1, 0):  # RIGHT
            death_coords.append(coordinates.add_coords(position, facing))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(2,0)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(3,0)))
    if weapon == 'amulet':
        if facing == coordinates.Coords(0, -1):  # UP
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,-1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(2,-1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,-1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-2,-1)))
        if facing == coordinates.Coords(0, 1):  # DOWN
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(2,1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-2,1)))
        if facing == coordinates.Coords(-1, 0):  # LEFT
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,2)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,-1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(-1,-2)))
        if facing == coordinates.Coords(1, 0):  # RIGHT
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,2)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,-1)))
            death_coords.append(coordinates.add_coords(position, coordinates.Coords(1,-2)))

    return death_coords

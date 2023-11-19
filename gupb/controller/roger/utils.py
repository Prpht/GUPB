from gupb.model.coordinates import Coords


def get_distance(coords1: Coords, coords2: Coords):
    return ((coords1.x - coords2.x) ** 2 + (coords1.y - coords2.y) ** 2) ** 0.5
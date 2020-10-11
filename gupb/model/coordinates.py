from typing import NamedTuple

Coords = NamedTuple('Coords', [('x', int), ('y', int)])


def add_coords(self: Coords, other: Coords) -> Coords:
    return Coords(self[0] + other[0], self[1] + other[1])


def sub_coords(self: Coords, other: Coords) -> Coords:
    return Coords(self[0] - other[0], self[1] - other[1])


Coords.__add__ = add_coords
Coords.__sub__ = sub_coords

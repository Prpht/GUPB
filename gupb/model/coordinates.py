from typing import NamedTuple

Coords = NamedTuple('Coords', [('x', int), ('y', int)])


def add_coords(self: Coords, other: Coords) -> Coords:
    return Coords(self[0] + other[0], self[1] + other[1])


def sub_coords(self: Coords, other: Coords) -> Coords:
    return Coords(self[0] - other[0], self[1] - other[1])

def mul_coords(self: Coords, other: int) -> Coords:
    return Coords(self[0] * other, self[1] * other)

def eq_coords(self: Coords, other: Coords) -> bool:
    return self[0] == other[0] and self[1] == other[1]

def mul_coords(self: Coords, other) -> Coords:
    if isinstance(other, int):
        return Coords(self[0] * other, self[1] * other)
    else:
        raise NotImplementedError


Coords.__add__ = add_coords
Coords.__sub__ = sub_coords
Coords.__mul__ = mul_coords
Coords.__eq__ = eq_coords

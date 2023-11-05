from typing import NamedTuple

Coords = NamedTuple('Coords', [('x', int), ('y', int)])


def add_coords(self: Coords, other: Coords) -> Coords:
    return Coords(self[0] + other[0], self[1] + other[1])


def sub_coords(self: Coords, other: Coords) -> Coords:
    return Coords(self[0] - other[0], self[1] - other[1])


def mul_coords(self: Coords, other) -> Coords:
    if isinstance(other, int):
        return Coords(self[0] * other, self[1] * other)
    # ? mogę tu dodać opcję dla mnozenia przez float? przydaje się czasem ~WS
    elif isinstance(other, float):
        return Coords(int(self[0] * other), int(self[1] * other))
    # * i w ogóle mozna by z tego zrobic porzadna klase, z __add__, __sub__, etc.
    # * zrobie to w kolejnej kolejce rozgrywek
    else:
        raise NotImplementedError


Coords.__add__ = add_coords
Coords.__sub__ = sub_coords
Coords.__mul__ = mul_coords

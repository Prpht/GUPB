from typing import List

from gupb.model import coordinates
from gupb.model import weapons

class Facing:
    # Here we simulate the Facing enum with associated coordinate values.
    UP = (0, -1)
    DOWN = (0, 1)
    LEFT = (-1, 0)
    RIGHT = (1, 0)
    
    @staticmethod
    def turn_left(facing: tuple) -> tuple:
        # For simplicity assume:
        mapping = {
            (0, -1): (-1, 0),
            (0, 1): (1, 0),
            (-1, 0): (0, 1),
            (1, 0): (0, -1),
        }
        return mapping[facing]

    @staticmethod
    def turn_right(facing: tuple) -> tuple:
        mapping = {
            (0, -1): (1, 0),
            (0, 1): (-1, 0),
            (-1, 0): (0, -1),
            (1, 0): (0, 1),
        }
        return mapping[facing]


# Coordinates is assumed to be a NamedTuple with operator overloads.
from typing import NamedTuple

class Coords(NamedTuple):
    x: int
    y: int

    def __add__(self, other: tuple) -> coordinates.Coords:
        dx, dy = other
        return Coords(self.x + dx, self.y + dy)

# -----------------------------------------------------------------------------
# Dummy Terrain

class DummyCell:
    def __init__(self, transparent: bool = True):
        self.transparent = transparent

class DummyTerrain(dict):
    """
    A dummy implementation of arenas.Terrain that treats every coordinate
    as valid and always transparent—i.e. an open field.
    """
    def __contains__(self, key):
        # Every coordinate exists in this open field.
        return True

    def __getitem__(self, key):
        # Every cell is transparent.
        return DummyCell()

# -----------------------------------------------------------------------------
# The function to compute attack positions

def get_attack_positions(position: Coords, weapon_name: str, facing: tuple) -> List[Coords]:
    """
    Returns a list of coordinates that can be attacked given a starting position,
    a weapon (by name) and a facing direction.

    Parameters:
      • position: The starting Coords.
      • weapon_name: A string representing the weapon ("knife", "sword", "bow", "axe", "amulet", "scroll").
      • facing: A tuple representing the direction (e.g. Facing.UP, Facing.DOWN, etc.)
                In your code, this would be characters.Facing.
    """
    # Map weapon names (in lowercase) to the corresponding classes.
    weapon_mapping = {
        "knife": weapons.Knife,
        "sword": weapons.Sword,
        "bow": weapons.Bow,
        "axe": weapons.Axe,
        "amulet": weapons.Amulet,
        "scroll": weapons.Scroll,
    }

    key = weapon_name.lower()
    weapon_class = weapon_mapping.get(key)
    if weapon_class is None:
        return []

    # Create a dummy terrain which simulates an open field.
    terrain = DummyTerrain()

    # Call the class method cut_positions. It takes (terrain, position, facing)
    return weapon_class.cut_positions(terrain, position, facing)


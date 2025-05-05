from typing import NamedTuple

from gupb.controller.rustler.utils import transparent
from gupb.model import coordinates, tiles, weapons


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


class TileKnowledgeTerrain:
    """
    A terrain interface built from a tile_knowledge dict where:
      • Each key is a Coords and its value is a tuple (TileDescription, int).
      • When retrieving a cell, if the coordinate is known, we use its TileDescription
        to determine if the cell is transparent. Otherwise, the cell defaults to being transparent.
    """

    def __init__(
        self, tile_knowledge: dict[coordinates.Coords, tuple[tiles.TileDescription, int]],
    ):
        self.tile_knowledge = tile_knowledge

    def __contains__(self, key: Coords) -> bool:
        return key[0] >= 0 and key[1] >= 0

    def __getitem__(self, key: Coords):
        if key in self.tile_knowledge:
            tile_desc, _ = self.tile_knowledge[key]
            return DummyCell(transparent=transparent(tile_desc))
        else:
            # For unknown coordinates, assume an open (transparent) terrain
            return DummyCell(transparent=True)


def get_attack_positions_with_dummy(
    position: Coords, weapon_name: str, facing: Facing, terrain=DummyTerrain(),
) -> list[tuple[int, int]]:
    """
    Returns a list of coordinates that can be attacked given a starting position,
    a weapon (by name) and a facing direction.

    Parameters:
      • position: The starting Coords.
      • weapon_name: A string representing the weapon ("knife", "sword", "bow", "axe", "amulet", "scroll").
      • facing: Direction (e.g. Facing.UP, Facing.DOWN, etc.) which should be characters.Facing.
    """
    # Map weapon names (in lowercase) to the corresponding classes.
    weapon_mapping = {
        'knife': weapons.Knife,
        'sword': weapons.Sword,
        'bow': weapons.Bow,
        'bow_loaded': weapons.Bow,
        'bow_unloaded': weapons.Bow,
        'axe': weapons.Axe,
        'amulet': weapons.Amulet,
        'scroll': weapons.Scroll,
    }

    key = weapon_name.lower()
    weapon_class = weapon_mapping.get(key)
    if weapon_class is None:
        return []

    # Call the class method cut_positions. It takes (terrain, position, facing)
    return weapon_class.cut_positions(terrain, position, facing)


# -----------------------------------------------------------------------------
# The function to compute attack positions using tile_knowledge


def get_attack_positions(
    position: Coords,
    weapon_name: str,
    facing: Facing,
    tile_knowledge: dict[coordinates.Coords, tuple[tiles.TileDescription, int]],
) -> list[tuple[int, int]]:
    """
    Returns a list of coordinates that can be attacked given a starting position,
    a weapon (by name) and a facing direction. Instead of a pre-built terrain, this
    version constructs terrain on the fly from tile_knowledge.

    Parameters:
      • position: The starting position.
      • weapon_name: A string representing the weapon ("knife", "sword", "bow", "axe", "amulet", "scroll").
      • facing: A tuple representing the direction (e.g. Facing.UP, Facing.DOWN, etc.)
      • tile_knowledge: A dict with keys as Coords and values as (TileDescription, int),
                        where transparency is determined by the TileDescription.
    """
    # Create a terrain object based on the provided tile knowledge.
    terrain = TileKnowledgeTerrain(tile_knowledge)

    # Delegate to the weapon's cut_positions method, which uses the terrain.
    return get_attack_positions_with_dummy(position, weapon_name, facing, terrain)

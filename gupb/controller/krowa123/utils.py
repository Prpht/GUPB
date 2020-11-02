import inspect
from typing import List, Optional, TypeVar, Dict

from gupb.model import tiles, weapons
from gupb.model.arenas import Terrain
from gupb.model.characters import Facing, Action
from gupb.model.coordinates import Coords

__all__ = ["neighboring_coords", "facing_from_value", "turn_actions", "path_to_actions", "get_champion_positions"]

W = TypeVar("W", bound=weapons.Weapon)
T = TypeVar("T", bound=tiles.Tile)

weapons_dict: Dict[str, W] = \
    {name.lower(): clazz for name, clazz in
     inspect.getmembers(weapons, lambda o: inspect.isclass(o) and issubclass(o, weapons.Weapon) and not inspect.isabstract(o))}

tiles_dict: Dict[str, T] = \
    {name.lower(): clazz for name, clazz in
     inspect.getmembers(tiles, lambda o: inspect.isclass(o) and issubclass(o, tiles.Tile) and not inspect.isabstract(o))}


def neighboring_coords(coord: Coords) -> List[Coords]:
    return [coord + Facing.UP.value, coord + Facing.DOWN.value, coord + Facing.LEFT.value, coord + Facing.RIGHT.value]


def facing_from_value(coord: Coords) -> Facing:
    return {
        Facing.UP.value: Facing.UP,
        Facing.DOWN.value: Facing.DOWN,
        Facing.LEFT.value: Facing.LEFT,
        Facing.RIGHT.value: Facing.RIGHT
    }[coord]


def turn_actions(start: Facing, end: Facing) -> List[Action]:
    return {
        start: [],
        start.turn_right(): [Action.TURN_RIGHT],
        start.turn_right().turn_right(): [Action.TURN_RIGHT, Action.TURN_RIGHT],
        start.turn_left(): [Action.TURN_LEFT]
    }[end]


def path_to_actions(position: Coords, facing: Facing, path: List[Coords]) -> List[Action]:
    actions = []
    for coord in path:
        desired_facing = facing
        if coord - position != (0, 0):
            desired_facing = facing_from_value(coord - position)
            actions += turn_actions(facing, desired_facing)
            actions.append(Action.STEP_FORWARD)
        else:
            actions.append(Action.DO_NOTHING)
        position = coord
        facing = desired_facing
    return actions


def get_champion_positions(terrain: Terrain, coords: Optional[List[Coords]] = None) -> List[Coords]:
    return [coord for coord, tile in terrain.items() if tile.character and (not coords or coord in coords)]


def distance(a: Coords, b: Coords):
    diff = b - a
    return int((diff.x ** 2 + diff.y ** 2) ** 0.5)

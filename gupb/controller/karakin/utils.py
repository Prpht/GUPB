from __future__ import annotations

from typing import Iterable

from gupb.model import characters
from gupb.model import coordinates

PASSABLE_TILE_TYPES = {"land", "forest", "menhir"}
TRANSPARENT_TILE_TYPES = {"land", "sea", "menhir"}
HAZARD_EFFECT_TYPES = {"mist", "fire"}

CARDINAL_DIRECTIONS = (
    coordinates.Coords(0, -1),
    coordinates.Coords(1, 0),
    coordinates.Coords(0, 1),
    coordinates.Coords(-1, 0),
)

MOVEMENT_ACTIONS = (
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.STEP_BACKWARD,
)

TACTICAL_ACTIONS = (
    characters.Action.ATTACK,
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.STEP_BACKWARD,
)


def to_coords(raw: coordinates.Coords | tuple[int, int]) -> coordinates.Coords:
    if isinstance(raw, coordinates.Coords):
        return raw
    return coordinates.Coords(raw[0], raw[1])


def manhattan(a: coordinates.Coords, b: coordinates.Coords) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def chebyshev(a: coordinates.Coords, b: coordinates.Coords) -> int:
    return max(abs(a.x - b.x), abs(a.y - b.y))


def direction_to_facing(direction: coordinates.Coords) -> characters.Facing | None:
    for facing in characters.Facing:
        if facing.value == direction:
            return facing
    return None


def facing_towards(origin: coordinates.Coords, target: coordinates.Coords) -> characters.Facing | None:
    delta = coordinates.Coords(target.x - origin.x, target.y - origin.y)
    if abs(delta.x) > abs(delta.y):
        return characters.Facing.RIGHT if delta.x > 0 else characters.Facing.LEFT
    if delta.y != 0:
        return characters.Facing.DOWN if delta.y > 0 else characters.Facing.UP
    return None


def movement_direction(action: characters.Action, facing: characters.Facing) -> coordinates.Coords | None:
    if action == characters.Action.STEP_FORWARD:
        return facing.value
    if action == characters.Action.STEP_BACKWARD:
        return facing.opposite().value
    if action == characters.Action.STEP_LEFT:
        return facing.turn_left().value
    if action == characters.Action.STEP_RIGHT:
        return facing.turn_right().value
    return None


def movement_action_for_direction(
    direction: coordinates.Coords,
    facing: characters.Facing,
) -> characters.Action | None:
    if direction == facing.value:
        return characters.Action.STEP_FORWARD
    if direction == facing.opposite().value:
        return characters.Action.STEP_BACKWARD
    if direction == facing.turn_left().value:
        return characters.Action.STEP_LEFT
    if direction == facing.turn_right().value:
        return characters.Action.STEP_RIGHT
    return None


def rotated_facing(action: characters.Action, facing: characters.Facing) -> characters.Facing:
    if action == characters.Action.TURN_LEFT:
        return facing.turn_left()
    if action == characters.Action.TURN_RIGHT:
        return facing.turn_right()
    return facing


def effect_types(tile) -> set[str]:
    if tile is None:
        return set()
    return {effect.type for effect in tile.effects}


def has_any_effect(tile, effect_names: Iterable[str]) -> bool:
    names = set(effect_names)
    return bool(effect_types(tile) & names)

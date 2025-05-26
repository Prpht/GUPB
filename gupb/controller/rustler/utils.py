import random

from gupb.model import characters, coordinates, tiles


def norm(coords: coordinates.Coords) -> int:
    return abs(coords.x) + abs(coords.y)


def misted(tile_description: tiles.TileDescription) -> bool:
    return (
        sum([1 if effect.type == 'mist' else 0 for effect in tile_description.effects])
        > 0
    )


def passable(tile_description: tiles.TileDescription) -> bool:
    return tile_description.type in ['land', 'forest', 'menhir']


def transparent(tile_description: tiles.TileDescription) -> bool:
    return tile_description.type in ['land', 'sea', 'menhir']


def on_fire(tile_description: tiles.TileDescription) -> bool:
    return (
        sum([1 if effect.type == 'fire' else 0 for effect in tile_description.effects])
        > 0
    )


def facing_to_cords(facing: characters.Facing) -> coordinates.Coords:
    if facing == characters.Facing.UP:
        return coordinates.Coords(0, -1)
    if facing == characters.Facing.DOWN:
        return coordinates.Coords(0, 1)
    if facing == characters.Facing.RIGHT:
        return coordinates.Coords(1, 0)
    if facing == characters.Facing.LEFT:
        return coordinates.Coords(-1, 0)


def cords_to_facing(coords: coordinates.Coords) -> characters.Facing:
    if coords.x > coords.y and coords.x > 0:
        return characters.Facing.RIGHT
    if coords.x < coords.y and coords.x < 0:
        return characters.Facing.LEFT
    if coords.y > coords.x and coords.y > 0:
        return characters.Facing.DOWN
    if coords.y < coords.x and coords.y < 0:
        return characters.Facing.UP


def str_to_facing(str: str) -> characters.Facing:
    if str == 'UP':
        return characters.Facing.UP
    if str == 'DOWN':
        return characters.Facing.DOWN
    if str == 'LEFT':
        return characters.Facing.LEFT
    if str == 'RIGHT':
        return characters.Facing.RIGHT
    return characters.Facing.UP


def quickselect(arr, n):
    if not arr:
        return None  # Handle empty set case
    pivot = random.choice(list(arr))
    left = {x for x in arr if x < pivot}
    right = {x for x in arr if x > pivot}

    if n < len(left):
        return quickselect(left, n)
    elif n == len(left):
        return pivot
    else:
        return quickselect(right, n - len(left) - 1)


def move_up(facing: characters.Facing) -> characters.Action:
    if facing == characters.Facing.UP:
        return characters.Action.STEP_FORWARD
    elif facing == characters.Facing.DOWN:
        return characters.Action.STEP_BACKWARD
    elif facing == characters.Facing.LEFT:
        return characters.Action.STEP_RIGHT
    elif facing == characters.Facing.RIGHT:
        return characters.Action.STEP_LEFT


def move_down(facing: characters.Facing) -> characters.Action:
    if facing == characters.Facing.DOWN:
        return characters.Action.STEP_FORWARD
    elif facing == characters.Facing.UP:
        return characters.Action.STEP_BACKWARD
    elif facing == characters.Facing.LEFT:
        return characters.Action.STEP_LEFT
    elif facing == characters.Facing.RIGHT:
        return characters.Action.STEP_RIGHT


def move_left(facing: characters.Facing) -> characters.Action:
    if facing == characters.Facing.LEFT:
        return characters.Action.STEP_FORWARD
    elif facing == characters.Facing.RIGHT:
        return characters.Action.STEP_BACKWARD
    elif facing == characters.Facing.UP:
        return characters.Action.STEP_LEFT
    elif facing == characters.Facing.DOWN:
        return characters.Action.STEP_RIGHT


def move_right(facing: characters.Facing) -> characters.Action:
    if facing == characters.Facing.RIGHT:
        return characters.Action.STEP_FORWARD
    elif facing == characters.Facing.LEFT:
        return characters.Action.STEP_BACKWARD
    elif facing == characters.Facing.UP:
        return characters.Action.STEP_RIGHT
    elif facing == characters.Facing.DOWN:
        return characters.Action.STEP_LEFT

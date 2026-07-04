import functools
from gupb.model import characters, coordinates, tiles
from .constants import PASSABLE_TILE_TYPES, LOS_TRANSPARENT_TYPES, FACINGS


_DELTA_TO_FACING: dict[tuple[int, int], characters.Facing] = {
    (f.value[0], f.value[1]): f for f in FACINGS
}


@functools.lru_cache(maxsize=100_000)
def _neighbors(pos: coordinates.Coords) -> tuple[coordinates.Coords, ...]:
    return (
        coordinates.Coords(pos[0], pos[1] - 1),
        coordinates.Coords(pos[0] + 1, pos[1]),
        coordinates.Coords(pos[0], pos[1] + 1),
        coordinates.Coords(pos[0] - 1, pos[1]),
    )


def is_passable_tile_type(tile_type: str) -> bool:
    return tile_type in PASSABLE_TILE_TYPES


def is_walkable_tile(tile: tiles.TileDescription | None) -> bool:
    return tile is not None and is_passable_tile_type(tile.type)


def blocks_line_of_sight(tile: tiles.TileDescription) -> bool:
    if tile.character is not None:
        return True
    return tile.type not in LOS_TRANSPARENT_TYPES


@functools.lru_cache(maxsize=100_000)
def forward_pos(
    pos: coordinates.Coords, facing: characters.Facing
) -> coordinates.Coords:
    delta = facing.value
    return coordinates.Coords(pos[0] + delta[0], pos[1] + delta[1])


def _move_facing(facing: characters.Facing, kind: str) -> characters.Facing:
    if kind == "forward":
        return facing
    if kind == "opposite":
        return facing.opposite()
    if kind == "turn_left":
        return facing.turn_left()
    return facing.turn_right()


def delta_to_facing(delta: tuple[int, int]) -> characters.Facing:
    return _DELTA_TO_FACING[delta]


def next_cell_on_path(
    parents: dict[coordinates.Coords, coordinates.Coords],
    start: coordinates.Coords,
    target: coordinates.Coords,
) -> coordinates.Coords | None:
    if target == start:
        return None
    cell = target
    while True:
        parent = parents.get(cell)
        if parent is None:
            return None
        if parent == start:
            return cell
        cell = parent


def step_action_non_omni(
    facing: characters.Facing, target_facing: characters.Facing
) -> characters.Action:
    if facing == target_facing:
        return characters.Action.STEP_FORWARD
    if facing.turn_left() == target_facing:
        return characters.Action.TURN_LEFT
    return characters.Action.TURN_RIGHT


def step_action_omni(
    facing: characters.Facing, target_facing: characters.Facing
) -> characters.Action:
    if target_facing == facing:
        return characters.Action.STEP_FORWARD
    if target_facing == facing.turn_left():
        return characters.Action.STEP_LEFT
    if target_facing == facing.turn_right():
        return characters.Action.STEP_RIGHT
    return characters.Action.STEP_BACKWARD


def first_step_to_cell(
    parents: dict[coordinates.Coords, coordinates.Coords],
    start: coordinates.Coords,
    target: coordinates.Coords,
    facing: characters.Facing,
    omnidirectional: bool,
) -> characters.Action | None:
    nxt = next_cell_on_path(parents, start, target)
    if nxt is None:
        return None
    target_facing = delta_to_facing((nxt[0] - start[0], nxt[1] - start[1]))
    if omnidirectional:
        return step_action_omni(facing, target_facing)
    return step_action_non_omni(facing, target_facing)

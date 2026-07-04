import collections
import functools

import bresenham
from gupb.model import characters, coordinates

AMULET_PRESCIENCE_RADIUS = 3

# Bounded LRU: (size, target, prescience, pos, facing) -> bool. Training draws
# episodes from a pool of 10k generated arenas, so most keys are never reused;
# without a cap this dict grows without bound for the lifetime of the worker.
_CAN_SEE_CACHE_MAXSIZE = 200_000
_CAN_SEE_CACHE: "collections.OrderedDict[tuple[tuple[int, int], coordinates.Coords, bool, coordinates.Coords, characters.Facing], bool]" = (collections.OrderedDict())


def _can_see_cache_get(
    key: tuple[
        tuple[int, int], coordinates.Coords, bool, coordinates.Coords, characters.Facing
    ],
) -> bool | None:
    value = _CAN_SEE_CACHE.get(key)
    if value is not None:
        _CAN_SEE_CACHE.move_to_end(key)
    return value


def _can_see_cache_put(
    key: tuple[
        tuple[int, int], coordinates.Coords, bool, coordinates.Coords, characters.Facing
    ],
    value: bool,
) -> None:
    _CAN_SEE_CACHE[key] = value
    _CAN_SEE_CACHE.move_to_end(key)
    if len(_CAN_SEE_CACHE) > _CAN_SEE_CACHE_MAXSIZE:
        _CAN_SEE_CACHE.popitem(last=False)


def uses_prescience_vision(weapon: str) -> bool:
    return weapon == "amulet"


def static_los_transparent(known_map: dict) -> frozenset[coordinates.Coords]:
    from ..bfs.constants import LOS_TRANSPARENT_TYPES

    return frozenset(
        pos for pos, tile in known_map.items() if tile.type in LOS_TRANSPARENT_TYPES
    )


def static_map_fingerprint(known_map: dict) -> frozenset[coordinates.Coords]:
    from ..bfs.constants import LOS_TRANSPARENT_TYPES

    return frozenset(
        pos for pos, tile in known_map.items() if tile.type not in LOS_TRANSPARENT_TYPES
    )


def map_size_from_coords(
    coords: frozenset[coordinates.Coords] | dict,
) -> tuple[int, int]:
    if not coords:
        return (1, 1)
    return (max(c[0] for c in coords) + 1, max(c[1] for c in coords) + 1)


@functools.lru_cache(maxsize=100_000)
def _get_rays(
    pos: coordinates.Coords,
    facing: characters.Facing,
    size: tuple[int, int],
) -> tuple[tuple[coordinates.Coords, ...], ...]:
    size_x, size_y = size
    if facing == characters.Facing.UP:
        border, distance = coordinates.Coords(pos[0], 0), pos[1]
    elif facing == characters.Facing.RIGHT:
        border, distance = coordinates.Coords(size_x - 1, pos[1]), size_x - pos[0]
    elif facing == characters.Facing.DOWN:
        border, distance = coordinates.Coords(pos[0], size_y - 1), size_y - pos[1]
    else:
        border, distance = coordinates.Coords(0, pos[1]), pos[0]

    left = facing.turn_left().value
    targets = [
        border + coordinates.Coords(i * left[0], i * left[1])
        for i in range(-distance, distance + 1)
    ]

    rays = []
    for coords in targets:
        ray = bresenham.bresenham(pos[0], pos[1], coords[0], coords[1])
        next(ray)
        rays.append(tuple(coordinates.Coords(rc[0], rc[1]) for rc in ray))
    return tuple(rays)


@functools.lru_cache(maxsize=100_000)
def is_visible(
    pos: coordinates.Coords,
    facing: characters.Facing,
    target: coordinates.Coords,
    transparent: frozenset[coordinates.Coords],
    size: tuple[int, int] | None = None,
    omnidirectional: bool = False,
) -> bool:
    if pos == target:
        return True

    if omnidirectional:
        for px, py in bresenham.bresenham(pos[0], pos[1], target[0], target[1]):
            p = coordinates.Coords(px, py)
            if p != pos and p != target:
                if p not in transparent:
                    return False
        return True

    if facing in (characters.Facing.UP, characters.Facing.DOWN):
        if target[1] == pos[1] and abs(target[0] - pos[0]) == 1:
            return True
    else:
        if target[0] == pos[0] and abs(target[1] - pos[1]) == 1:
            return True

    if not transparent:
        return False

    if size is None:
        size_x = max(c[0] for c in transparent) + 1
        size_y = max(c[1] for c in transparent) + 1
        size = (size_x, size_y)

    rays = _get_rays(pos, facing, size)
    for ray in rays:
        for rc in ray:
            if rc == target:
                return True
            if rc not in transparent:
                break
    return False


def visible_coords_on_map(
    pos: coordinates.Coords,
    facing: characters.Facing,
    known_map: dict,
    size: tuple[int, int] | None = None,
) -> set[coordinates.Coords]:
    from ..bfs.helpers import blocks_line_of_sight

    if size is None:
        size = map_size_from_coords(known_map)

    visible: set[coordinates.Coords] = {pos}

    if facing in (characters.Facing.UP, characters.Facing.DOWN):
        sides = (
            coordinates.Coords(pos[0] + 1, pos[1]),
            coordinates.Coords(pos[0] - 1, pos[1]),
        )
    else:
        sides = (
            coordinates.Coords(pos[0], pos[1] + 1),
            coordinates.Coords(pos[0], pos[1] - 1),
        )
    for s in sides:
        if s in known_map:
            visible.add(s)

    rays = _get_rays(pos, facing, size)
    for ray in rays:
        for rc in ray:
            tile = known_map.get(rc)
            if tile is None:
                break
            visible.add(rc)
            if blocks_line_of_sight(tile):
                break
    return visible


def _prescience_can_see(
    pos: coordinates.Coords,
    target: coordinates.Coords,
    radius: int = AMULET_PRESCIENCE_RADIUS,
) -> bool:
    dx = pos[0] - target[0]
    dy = pos[1] - target[1]
    return dx * dx + dy * dy <= radius * radius


def _side_adjacent_visible(
    pos: coordinates.Coords,
    facing: characters.Facing,
    target: coordinates.Coords,
    static_transparent: frozenset[coordinates.Coords],
) -> bool:
    if facing in (characters.Facing.UP, characters.Facing.DOWN):
        if target[1] == pos[1] and abs(target[0] - pos[0]) == 1:
            return target in static_transparent
    else:
        if target[0] == pos[0] and abs(target[1] - pos[1]) == 1:
            return target in static_transparent
    return False


def _in_vision_wedge(
    pos: coordinates.Coords,
    facing: characters.Facing,
    target: coordinates.Coords,
) -> bool:
    if facing == characters.Facing.UP:
        depth = pos[1] - target[1]
        if depth <= 0:
            return False
        return abs(target[0] - pos[0]) <= depth
    if facing == characters.Facing.DOWN:
        depth = target[1] - pos[1]
        if depth <= 0:
            return False
        return abs(target[0] - pos[0]) <= depth
    if facing == characters.Facing.LEFT:
        depth = pos[0] - target[0]
        if depth <= 0:
            return False
        return abs(target[1] - pos[1]) <= depth
    if facing == characters.Facing.RIGHT:
        depth = target[0] - pos[0]
        if depth <= 0:
            return False
        return abs(target[1] - pos[1]) <= depth
    return False


def _ray_clear_to_target(
    pos: coordinates.Coords,
    target: coordinates.Coords,
    static_transparent: frozenset[coordinates.Coords],
) -> bool:
    for px, py in bresenham.bresenham(pos[0], pos[1], target[0], target[1]):
        rc = coordinates.Coords(px, py)
        if rc == target:
            return True
        if rc != pos and rc not in static_transparent:
            return False
    return False


def can_see_target_static(
    pos: coordinates.Coords,
    facing: characters.Facing,
    target: coordinates.Coords,
    static_transparent: frozenset[coordinates.Coords],
    size: tuple[int, int],
    *,
    use_prescience: bool = False,
) -> bool:
    """One ray to target inside vision wedge — O(map diameter), not O(cone area)."""
    del size
    if pos == target:
        return True
    if use_prescience:
        return _prescience_can_see(pos, target)
    if _side_adjacent_visible(pos, facing, target, static_transparent):
        return True
    if not _in_vision_wedge(pos, facing, target):
        return False
    return _ray_clear_to_target(pos, target, static_transparent)


class TargetVisibilityLookup:
    """Lazy cache: can fixed target be seen from (pos, facing)? No full cone."""

    __slots__ = (
        "target",
        "use_prescience",
        "static_transparent",
        "size",
        "_session",
    )

    def __init__(
        self,
        target: coordinates.Coords,
        known_map: dict,
        *,
        use_prescience: bool = False,
    ) -> None:
        self.target = target
        self.use_prescience = use_prescience
        self.static_transparent = static_los_transparent(known_map)
        self.size = map_size_from_coords(known_map)
        self._session: dict[tuple[coordinates.Coords, characters.Facing], bool] = {}

    def can_see(
        self,
        pos: coordinates.Coords,
        facing: characters.Facing,
        target: coordinates.Coords,
    ) -> bool:
        if target != self.target:
            return False
        key = (pos, facing)
        cached = self._session.get(key)
        if cached is not None:
            return cached

        global_key = (self.size, self.target, self.use_prescience, pos, facing)
        result = _can_see_cache_get(global_key)
        if result is None:
            result = can_see_target_static(
                pos,
                facing,
                self.target,
                self.static_transparent,
                self.size,
                use_prescience=self.use_prescience,
            )
            _can_see_cache_put(global_key, result)
        self._session[key] = result
        return result


def build_target_visibility_cache(
    known_map: dict,
    target: coordinates.Coords,
    *,
    use_prescience: bool = False,
) -> TargetVisibilityLookup:
    return TargetVisibilityLookup(target, known_map, use_prescience=use_prescience)

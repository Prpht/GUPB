from gupb.model import coordinates, tiles

from ..bfs.constants import FACINGS, State
from ..bfs.helpers import is_walkable_tile
from ..memory import MapMemory
from .arena import build_combat_arena, _attack_cells

_BOW_AXES_TO_FACING = {
    (-f.value[0], -f.value[1]): f
    for f in FACINGS
}
_BOW_MAX_RANGE = 50
# Manhattan span scanned for melee/point firing positions. Must cover the
# longest non-bow reach: the amulet fires diagonally up to 2 tiles, i.e. a
# manhattan offset of 4 (sword 3, axe/knife/scroll <= 1 fit within it).
_MELEE_RADIUS = 4
_FIRING_SENTINEL = coordinates.Coords(-1, -1)


def firing_states(
    target: coordinates.Coords,
    weapon: str,
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    memory: MapMemory,
) -> list[State]:
    if weapon == "bow_unloaded":
        weapon = "bow_loaded"
    arena = build_combat_arena(memory, _FIRING_SENTINEL, _FIRING_SENTINEL)
    states: list[State] = []
    if weapon == "bow_loaded":
        # Bow fires in a straight axis-aligned line over transparent (incl. sea)
        # tiles. Walking outward from the target, line-of-sight stays clear until
        # the first opaque or champion-occupied tile, so every walkable tile until
        # that break is a valid firing spot (facing back at the target). No need
        # for per-facing _attack_cells nor diagonal directions.
        terrain_transparent = arena.terrain_transparent
        other_champions = arena.other_champions
        for (dx, dy), facing in _BOW_AXES_TO_FACING.items():
            for dist in range(1, _BOW_MAX_RANGE + 1):
                pos = coordinates.Coords(target[0] + dx * dist, target[1] + dy * dist)
                tile = known_map.get(pos)
                if tile is None:
                    break
                if is_walkable_tile(tile):
                    states.append((pos, facing))
                if pos not in terrain_transparent or pos in other_champions:
                    break
        return states
    for dx in range(-_MELEE_RADIUS, _MELEE_RADIUS + 1):
        for dy in range(-_MELEE_RADIUS, _MELEE_RADIUS + 1):
            if abs(dx) + abs(dy) > _MELEE_RADIUS:
                continue
            pos = coordinates.Coords(target[0] + dx, target[1] + dy)
            tile = known_map.get(pos)
            if tile is None or not is_walkable_tile(tile):
                continue
            blocking = {pos, target} | arena.other_champions
            for facing in FACINGS:
                if target in _attack_cells(weapon, pos, facing, arena, blocking):
                    states.append((pos, facing))
    return states


def firing_positions(
    target: coordinates.Coords,
    weapon: str,
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    memory: MapMemory,
) -> list[coordinates.Coords]:
    seen: set[coordinates.Coords] = set()
    result: list[coordinates.Coords] = []
    for pos, _ in firing_states(target, weapon, known_map, memory):
        if pos not in seen:
            seen.add(pos)
            result.append(pos)
    return result

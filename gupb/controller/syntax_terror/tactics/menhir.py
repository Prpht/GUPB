import random

from gupb.model import characters, coordinates, tiles

from ..bfs.cache import DistanceMap
from ..bfs.constants import FACINGS
from ..bfs.helpers import (
    delta_to_facing,
    is_walkable_tile,
    next_cell_on_path,
    step_action_non_omni,
    step_action_omni,
    _neighbors,
)
from ..bfs.turn_nav import TurnNavigation
from ..memory import MapMemory
from ..mist import is_pos_mist_at
from ..utils.visibility import map_size_from_coords, visible_coords_on_map

def _is_on_fire(tile: tiles.TileDescription) -> bool:
    return any(e.type == "fire" for e in tile.effects)


def _closest_safe_neighbor(
    menhir_pos: coordinates.Coords,
    bot_pos: coordinates.Coords,
    memory: MapMemory,
) -> coordinates.Coords | None:
    best: coordinates.Coords | None = None
    best_distance: int | None = None
    for neighbor in _neighbors(menhir_pos):
        tile = memory.map_data.get(neighbor)
        if tile is None or _is_on_fire(tile):
            continue
        d = abs(neighbor[0] - bot_pos[0]) + abs(neighbor[1] - bot_pos[1])
        if best_distance is None or d < best_distance:
            best_distance = d
            best = neighbor
    return best


def _target_position(
    menhir_pos: coordinates.Coords,
    bot_pos: coordinates.Coords,
    memory: MapMemory,
) -> coordinates.Coords:
    menhir_tile = memory.map_data.get(menhir_pos)
    if menhir_tile and _is_on_fire(menhir_tile):
        neighbor = _closest_safe_neighbor(menhir_pos, bot_pos, memory)
        return neighbor if neighbor else menhir_pos
    return menhir_pos


def menhir_reachable(
    memory: MapMemory,
    position: coordinates.Coords,
    distances: DistanceMap,
) -> bool:
    menhir_pos = memory.menhir_pos
    if menhir_pos is None:
        return False
    target = _target_position(menhir_pos, position, memory)
    if position == target:
        return True
    return next_cell_on_path(distances.parents, position, target) is not None


def _camp_turn(
    memory: MapMemory,
    position: coordinates.Coords,
    facing: characters.Facing,
) -> tuple[characters.Action, str]:
    """Decide how to look around while standing on the menhir.

    Only turn toward a facing that would reveal tiles we do not currently see
    (i.e. never spin into a wall for no gain). Among the useful facings pick one
    at random. If no facing reveals anything new, stay put (DO_NOTHING) — the
    brain's anti-idle guard will inject a random turn if we sit too long.
    """
    known = memory.map_data
    size = map_size_from_coords(known)

    def fields(facing_dir: characters.Facing) -> set[coordinates.Coords]:
        # Only walkable tiles count as "fields" worth scanning (enemies can only
        # stand on them); seeing the wall tile in front of us is not new vision.
        return {
            p
            for p in visible_coords_on_map(position, facing_dir, known, size)
            if is_walkable_tile(known.get(p))
        }

    current = fields(facing)
    useful: list[characters.Facing] = []
    for candidate in FACINGS:
        if candidate == facing:
            continue
        if fields(candidate) - current:
            useful.append(candidate)

    if not useful:
        return characters.Action.DO_NOTHING, "MENHIR camp (no new view)"

    goal = random.choice(useful)
    return step_action_non_omni(facing, goal), "MENHIR camp (scan)"


def handle_menhir(
    memory: MapMemory,
    position: coordinates.Coords,
    facing: characters.Facing,
) -> tuple[characters.Action | None, str]:
    menhir_pos = memory.menhir_pos
    if menhir_pos is None:
        return None, "MENHIR -> None"

    target = _target_position(menhir_pos, position, memory)
    if position == target:
        return _camp_turn(memory, position, facing)

    turn_nav = TurnNavigation.get(memory)
    nxt = next_cell_on_path(turn_nav.forward.parents, position, target)
    if nxt is None:
        return None, f"MENHIR -> {target} (blocked)"

    target_facing = delta_to_facing((nxt[0] - position[0], nxt[1] - position[1]))
    if facing == target_facing:
        return characters.Action.STEP_FORWARD, f"MENHIR -> {target}"
    is_omni = is_pos_mist_at(memory.mist_info, position, 1) or memory.my_weapon == "amulet"
    if is_omni:
        return step_action_omni(facing, target_facing), f"MENHIR -> {target} (dodge)"
    return step_action_non_omni(facing, target_facing), f"MENHIR -> {target}"

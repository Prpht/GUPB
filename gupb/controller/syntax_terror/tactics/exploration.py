from gupb.model import characters, coordinates, tiles

from ..bfs.constants import FACINGS
from ..bfs.helpers import (
    first_step_to_cell,
    step_action_non_omni,
    step_action_omni,
)
from ..bfs.turn_nav import TurnNavigation
from ..memory import MapMemory
from ..mist import _has_mist, is_pos_mist_at

_UNREACHABLE = 999999


def _neighbors(pos: coordinates.Coords) -> tuple[coordinates.Coords, ...]:
    return (
        coordinates.Coords(pos[0], pos[1] - 1),
        coordinates.Coords(pos[0] + 1, pos[1]),
        coordinates.Coords(pos[0], pos[1] + 1),
        coordinates.Coords(pos[0] - 1, pos[1]),
    )


def _frontier_anchors(
    raw_map: dict[coordinates.Coords, tiles.TileDescription],
) -> list[coordinates.Coords]:
    return [q for q in raw_map if any(n not in raw_map for n in _neighbors(q))]


def _is_safe_explore_tile(
    q: coordinates.Coords,
    raw: dict[coordinates.Coords, tiles.TileDescription],
    mist_info,
    ticks_ahead: int,
) -> bool:
    tile = raw.get(q)
    if not tile or _has_mist(tile):
        return False
    if any(e.type == "fire" for e in tile.effects):
        return False
    if tile.character is not None:
        return False
    return not is_pos_mist_at(mist_info, q, ticks_ahead)


def has_safe_exploration_targets(
    memory: MapMemory,
    distances: dict[coordinates.Coords, int],
) -> bool:
    raw = memory.map_data
    mist_info = memory.mist_info
    times = distances.times
    for q, dist in distances.items():
        if dist <= 0:
            continue
        if _is_safe_explore_tile(q, raw, mist_info, times.get(q, dist)):
            return True
    return False


def _facing_into_unknown_from(
    q: coordinates.Coords,
    raw_map: dict[coordinates.Coords, tiles.TileDescription],
    prefer: characters.Facing,
) -> characters.Facing | None:
    order = (prefer, *(f for f in FACINGS if f != prefer))
    for facing in order:
        n = coordinates.Coords(q[0] + facing.value[0], q[1] + facing.value[1])
        if n not in raw_map:
            return facing
    return None


def _menhir_usable(turn_nav: TurnNavigation, position: coordinates.Coords) -> bool:
    """Whether return-to-menhir cost is meaningful for ranking explore targets.

    When the menhir is unknown, or known but unreachable through currently
    explored terrain, every cell scores ``_UNREACHABLE`` as a return target.
    In that case ranking by return cost paralyses exploration, so we fall back
    to plain forward (reach) cost instead.
    """
    if turn_nav.return_map is None:
        return False
    return turn_nav.nav_score(position) < _UNREACHABLE


def _explore_cost(
    turn_nav: TurnNavigation, q: coordinates.Coords, menhir_usable: bool
) -> int:
    if menhir_usable:
        return turn_nav.nav_score(q)
    return turn_nav.forward.get(q, _UNREACHABLE)


def _touches_mist_seen(
    q: coordinates.Coords,
    mist_seen: set[coordinates.Coords],
) -> bool:
    if q in mist_seen:
        return True
    return any(
        coordinates.Coords(q[0] + dx, q[1] + dy) in mist_seen
        for dx, dy in ((0, -1), (1, 0), (0, 1), (-1, 0))
    )


def _select_best_anchor(
    memory: MapMemory,
    position: coordinates.Coords,
    turn_nav: TurnNavigation,
    self_hp: int,
    menhir_usable: bool,
    mist_seen: set[coordinates.Coords] | None = None,
) -> tuple[coordinates.Coords, int] | None:
    raw = memory.map_data
    mist_info = memory.mist_info
    forward = turn_nav.forward
    candidates = []
    for q in _frontier_anchors(raw):
        if q == position or q not in forward:
            continue
        if forward.hp_lost.get(q, 0) >= self_hp:
            continue
        if mist_seen and _touches_mist_seen(q, mist_seen):
            continue
        if not _is_safe_explore_tile(q, raw, mist_info, forward.times.get(q, 0)):
            continue
        cost = _explore_cost(turn_nav, q, menhir_usable)
        if cost < _UNREACHABLE:
            candidates.append((cost, q[0], q[1], q))
    if not candidates:
        return None
    best = min(candidates)
    return best[3], best[0]


def _select_oldest_target(
    memory: MapMemory,
    position: coordinates.Coords,
    turn_nav: TurnNavigation,
    self_hp: int,
    menhir_usable: bool,
    mist_seen: set[coordinates.Coords] | None = None,
) -> tuple[coordinates.Coords, int, int] | None:
    raw = memory.map_data
    mist_info = memory.mist_info
    forward = turn_nav.forward
    candidates = []
    for q in forward:
        if q == position or q not in raw:
            continue
        hp_lost = forward.hp_lost.get(q, 0)
        if hp_lost >= self_hp:
            continue
        if mist_seen and _touches_mist_seen(q, mist_seen):
            continue
        if not _is_safe_explore_tile(q, raw, mist_info, forward.times.get(q, 0)):
            continue
        cost = _explore_cost(turn_nav, q, menhir_usable)
        if cost < _UNREACHABLE:
            candidates.append((memory.last_seen.get(q, 0), hp_lost, cost, q[0], q[1], q))
    if not candidates:
        return None
    best = min(candidates)
    return best[5], best[2], best[0]


def explore(
    memory: MapMemory,
    position: coordinates.Coords,
    facing: characters.Facing,
    self_hp: int,
) -> tuple[characters.Action | None, str]:
    turn_nav = TurnNavigation.get(memory)
    menhir_usable = _menhir_usable(turn_nav, position)

    in_mist = (
        _has_mist(memory.map_data[position]) if position in memory.map_data else False
    )
    mist_seen = memory.mist_seen if in_mist else None

    reason = ""
    anchor_result = _select_best_anchor(
        memory, position, turn_nav, self_hp, menhir_usable, mist_seen
    )
    if anchor_result is not None:
        target, cost = anchor_result
        reason = f"frontier cost={cost} last_seen={memory.last_seen.get(target, 0)}"
    else:
        oldest_result = _select_oldest_target(
            memory, position, turn_nav, self_hp, menhir_usable, mist_seen
        )
        if oldest_result is not None:
            target, cost, last_seen = oldest_result
            reason = f"oldest last_seen={last_seen} cost={cost}"
        else:
            target = None

    if target is None:
        return None, "EXPLORE -> None (no safe targets)"

    # While standing in mist, strafe (omni) toward the target so we leave the
    # mist immediately instead of spending turns rotating in the damage zone.
    is_omni = in_mist or memory.my_weapon == "amulet"

    act = first_step_to_cell(
        turn_nav.forward.parents, position, target, facing, is_omni
    )
    if act is not None:
        return act, f"EXPLORE -> {target} [{reason}]"

    want = _facing_into_unknown_from(target, memory.map_data, facing)
    if want is None:
        return None, f"EXPLORE -> {target} [{reason}] (blocked)"
    step = step_action_omni if is_omni else step_action_non_omni
    return step(facing, want), f"EXPLORE -> {target} [{reason}] (face {want.name})"

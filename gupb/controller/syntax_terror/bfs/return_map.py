import math
from collections import deque
from dataclasses import dataclass

import numpy as np
from gupb.model import coordinates, tiles
from .helpers import is_walkable_tile, _neighbors
from .damage import _enemy_attack_cells
from ..weapons import attack_damage
from ..mist import predict_mist_radius

_INF = 999999.0

# The return DP is expressed in "ticks ahead of now". Because the mist schedule
# is anchored to ``mist_tick_counter`` (which advances by exactly one per turn),
# a DP built on an earlier turn can be reused by shifting the time index by the
# elapsed counter delta and correcting the (linear) travel-time term. The mist
# damage along every return path stays bit-exact under this shift, and the cache
# is invalidated outright whenever the observed mist radius changes. Enemy damage
# is no longer baked into the DP at all (only mist + fire), so the sole staleness
# left within the window is the fire snapshot and the enemy-impassability edges;
# both are minor for a long-horizon strategic feature, which lets us reuse for
# many turns. Reuse is the dominant turn-time lever on large arenas (e.g. island
# with a corner menhir), where the needed horizon grows ~1 tick per turn as the
# frontier expands and would otherwise force a full rebuild almost every turn.
_CACHE_MAX_REUSE = 12
# Extra geodesic slack (beyond the farthest forward-reachable cell) kept around
# the menhir so obstacle detours and the bot's own movement during the reuse
# window stay inside the retained cell set. Validated to reproduce the full DP
# bit-exactly on the test arenas.
_KEEP_MARGIN = 18
# Extra horizon slack on top of the analytic (forward-time + return-length)
# bound. Sized so the cache survives the per-turn horizon growth across the full
# reuse window before a rebuild is forced.
_HORIZON_MARGIN = 30


class ReturnCostMap:
    def __init__(self, dp, pos_to_idx, self_hp, T_max, tick_offset: int = 0):
        self.dp = dp
        self.pos_to_idx = pos_to_idx
        self.self_hp = self_hp
        self.T_max = T_max
        self.tick_offset = tick_offset

    def view(self, tick_offset: int) -> "ReturnCostMap":
        if tick_offset == self.tick_offset:
            return self
        return ReturnCostMap(
            self.dp, self.pos_to_idx, self.self_hp, self.T_max, tick_offset
        )

    def query(self, pos, facing, t_arrive, hp_lost):
        del facing
        pos_idx = self.pos_to_idx.get(pos)
        if pos_idx is None:
            return 999999
        if hp_lost >= self.self_hp:
            return 999999
        t = t_arrive + self.tick_offset
        if t < 0 or t > self.T_max:
            return 999999
        val = self.dp[t, pos_idx, hp_lost]
        if val >= _INF:
            return 999999
        return int(val) - self.tick_offset


@dataclass
class _PersistentReturnMap:
    rmap: ReturnCostMap
    build_counter: int
    menhir: coordinates.Coords
    radius: int | None
    alive: int
    n_walkable: int
    keep_radius: int


def _note_forward_times(memory, times: dict) -> None:
    if not times:
        return
    new_max = max(times.values())
    if new_max > memory._return_map_max_forward_time:
        memory._return_map_max_forward_time = new_max


def _menhir_geodesic(
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    menhir: coordinates.Coords,
    start: coordinates.Coords,
) -> dict[coordinates.Coords, int]:
    """Geodesic walking distance from the menhir, treating enemies as impassable.

    This is exactly the connectivity the return DP uses, so the resulting
    distances bound every cell that can lie on a return path to the menhir.
    """
    dist = {menhir: 0}
    queue: deque[coordinates.Coords] = deque((menhir,))
    while queue:
        pos = queue.popleft()
        d = dist[pos]
        for nxt in _neighbors(pos):
            if nxt in dist:
                continue
            tile = known_map.get(nxt)
            if tile is None or not is_walkable_tile(tile):
                continue
            if tile.character is not None and nxt != start and nxt != menhir:
                continue
            dist[nxt] = d + 1
            queue.append(nxt)
    return dist


def _unique_radius_indices(mist_info, t_count: int) -> tuple[np.ndarray, list[int]]:
    t_to_r = np.empty(t_count, dtype=np.int32)
    radii: list[int] = []
    r_map: dict[int, int] = {}
    for t in range(t_count):
        r = predict_mist_radius(mist_info, t)
        if r not in r_map:
            r_map[r] = len(radii)
            radii.append(r)
        t_to_r[t] = r_map[r]
    return t_to_r, radii


def _build_edges(
    walkable_positions: list[coordinates.Coords],
    pos_to_idx: dict[coordinates.Coords, int],
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    start_pos: coordinates.Coords,
    memory,
) -> tuple[list[np.ndarray], list[np.ndarray]]:
    n_cells = len(walkable_positions)
    next_pos_idx = np.full((n_cells, 4), -1, dtype=np.int32)
    for pos_idx, pos in enumerate(walkable_positions):
        for k, nxt_pos in enumerate(_neighbors(pos)):
            j = pos_to_idx.get(nxt_pos)
            if j is None:
                continue
            tile_nxt = known_map.get(nxt_pos)
            menhir_pos = memory.mist_info.menhir_pos
            has_seen_enemy = (
                tile_nxt is not None
                and tile_nxt.character is not None
                and nxt_pos != start_pos
                and nxt_pos != menhir_pos
                and memory.last_seen.get(nxt_pos) == memory.game_tick
            )
            if has_seen_enemy:
                continue
            next_pos_idx[pos_idx, k] = j

    edge_s: list[np.ndarray] = []
    edge_nxt: list[np.ndarray] = []
    for k in range(4):
        nxt = next_pos_idx[:, k]
        valid = nxt != -1
        edge_s.append(np.flatnonzero(valid).astype(np.int32))
        edge_nxt.append(nxt[valid].astype(np.int32))
    return edge_s, edge_nxt


# A single relaxation group: move from sources `s_m` to neighbours `n_m`, each
# incurring `d` damage at the destination (so the hp index shifts by `d`).
_RelaxGroup = tuple[int, np.ndarray, np.ndarray, int]


def _precompute_relax_groups(
    fog_hp: np.ndarray,
    edge_s: list[np.ndarray],
    edge_nxt: list[np.ndarray],
    self_hp: int,
) -> list[list[_RelaxGroup]]:
    """Per distinct mist radius, the relaxation groups for the backward DP.

    The per-step damage map only depends on the (small) set of distinct mist
    radii, while the backward DP visits hundreds of time steps. Precomputing the
    damage masks once per radius (instead of once per time step) removes the bulk
    of the repeated boolean-indexing work, with identical numerical results.
    """
    groups_by_radius: list[list[_RelaxGroup]] = []
    for step_row in fog_hp:
        groups: list[_RelaxGroup] = []
        for a in range(len(edge_s)):
            s_idx = edge_s[a]
            if s_idx.size == 0:
                continue
            nxt_s = edge_nxt[a]
            dmg = step_row[nxt_s]
            max_d = int(dmg.max())
            for d in range(max_d + 1):
                valid_h = self_hp - d
                if valid_h <= 0:
                    continue
                mask = dmg == d
                if not np.any(mask):
                    continue
                groups.append(
                    (valid_h, s_idx[mask], nxt_s[mask], d)
                )
        groups_by_radius.append(groups)
    return groups_by_radius


def _run_backward_dp(
    dp: np.ndarray,
    t_to_r: np.ndarray,
    groups_by_radius: list[list[_RelaxGroup]],
    T_max: int,
    self_hp: int,
) -> None:
    for t in range(T_max - 1, -1, -1):
        dp_cur = dp[t]
        dp_next = dp[t + 1]
        for valid_h, s_m, n_m, d in groups_by_radius[t_to_r[t + 1]]:
            cur = dp_cur[s_m, :valid_h]
            np.minimum(cur, dp_next[n_m, d:self_hp], out=cur)
            dp_cur[s_m, :valid_h] = cur


def _build_dp(
    start_pos: coordinates.Coords,
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    self_hp: int,
    memory,
    walkable_positions: list[coordinates.Coords],
    T_max: int,
) -> ReturnCostMap:
    menhir_pos = memory.mist_info.menhir_pos
    pos_to_idx = {pos: i for i, pos in enumerate(walkable_positions)}
    n_cells = len(walkable_positions)
    menhir_idx = pos_to_idx[menhir_pos]

    mist_info = memory.mist_info

    # Return-path HP loss accounts for mist + fire only. Enemy-inflicted damage
    # is intentionally excluded here (enemies move, so baking their current
    # attack range into the long-horizon return DP is both stale and, per the
    # global policy, no longer treated as real HP loss). To re-enable enemy
    # damage on the return path, flip `if False:` below back on.
    base_dmg = np.zeros(n_cells, dtype=np.int32)
    dist_sq = np.empty(n_cells, dtype=np.int32)
    menhir_x, menhir_y = menhir_pos[0], menhir_pos[1]
    for pos_idx, pos in enumerate(walkable_positions):
        tile = known_map.get(pos)
        hp_base = 0
        if tile is not None:
            effect_types = {e.type for e in tile.effects}
            if "fire" in effect_types:
                hp_base += 3
            elif "mist" in effect_types:
                hp_base += 1
        if False:  # noqa: SIM223 - enemy attack damage on return path (disabled)
            if memory._cached_attacked_cells is None:
                memory._cached_attacked_cells = _enemy_attack_cells(
                    start_pos, known_map
                )
            attacked_cells = memory._cached_attacked_cells
            if tile is not None and tile.character is not None and pos != start_pos:
                hp_base += attack_damage(tile.character.weapon.name)
            if pos in attacked_cells:
                hp_base += attacked_cells[pos]
        base_dmg[pos_idx] = hp_base
        dx = pos[0] - menhir_x
        dy = pos[1] - menhir_y
        dist_sq[pos_idx] = dx * dx + dy * dy

    t_to_r, radii = _unique_radius_indices(mist_info, T_max + 2)
    fog_hp = np.empty((len(radii), n_cells), dtype=np.int32)
    for ri, r in enumerate(radii):
        r_sq = r * r
        fog_hp[ri] = base_dmg + (dist_sq >= r_sq).astype(np.int32)

    penalty = np.array(
        [
            0.0 if H == 0 else 100.0 * (math.exp(4.0 * H / max(1, self_hp)) - 1.0)
            for H in range(self_hp)
        ],
        dtype=np.float32,
    )

    edge_s, edge_nxt = _build_edges(
        walkable_positions, pos_to_idx, known_map, start_pos, memory
    )
    groups_by_radius = _precompute_relax_groups(fog_hp, edge_s, edge_nxt, self_hp)

    dp = np.full((T_max + 1, n_cells, self_hp), _INF, dtype=np.float32)
    times = np.arange(T_max + 1, dtype=np.float32)
    dp[:, menhir_idx, :] = times[:, None] + penalty[None, :]

    _run_backward_dp(dp, t_to_r, groups_by_radius, T_max, self_hp)

    return ReturnCostMap(dp, pos_to_idx, self_hp, T_max)


def build_return_cost_map(
    start_pos: coordinates.Coords,
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    omnidirectional: bool,
    self_hp: int,
    memory,
    T_max: int = 370,
    *,
    adaptive_horizon: bool = True,
    forward=None,
) -> ReturnCostMap | None:
    del omnidirectional
    menhir_pos = memory.mist_info.menhir_pos
    if menhir_pos is None:
        return None

    cap = T_max
    counter = memory.mist_tick_counter
    radius = memory.mist_radius
    alive = memory.alive_count
    n_walkable = sum(1 for tile in known_map.values() if is_walkable_tile(tile))
    max_fwd_time = (
        max(forward.times.values())
        if forward is not None and forward.times
        else memory._return_map_max_forward_time
    )

    persistent = memory._return_map_persistent
    if persistent is not None:
        delta = counter - persistent.build_counter
        if (
            persistent.menhir == menhir_pos
            and persistent.radius == radius
            and persistent.alive == alive
            and 0 <= delta <= _CACHE_MAX_REUSE
            and n_walkable <= persistent.n_walkable
            and start_pos in persistent.rmap.pos_to_idx
            and max_fwd_time + persistent.keep_radius + delta <= persistent.rmap.T_max
        ):
            return persistent.rmap.view(delta)

    dist = _menhir_geodesic(known_map, menhir_pos, start_pos)
    if forward is not None:
        fwd_dists = [dist[c] for c in forward if c in dist]
    else:
        fwd_dists = list(dist.values())
    keep_radius = (max(fwd_dists) if fwd_dists else 0) + _KEEP_MARGIN
    walkable_positions = [pos for pos, d in dist.items() if d <= keep_radius]

    if adaptive_horizon:
        horizon = max_fwd_time + keep_radius + _CACHE_MAX_REUSE + _HORIZON_MARGIN
        T_max_build = min(cap, max(30, horizon))
    else:
        T_max_build = cap

    rmap = _build_dp(
        start_pos, known_map, self_hp, memory, walkable_positions, T_max_build
    )
    memory._return_map_persistent = _PersistentReturnMap(
        rmap=rmap,
        build_counter=counter,
        menhir=menhir_pos,
        radius=radius,
        alive=alive,
        n_walkable=n_walkable,
        keep_radius=keep_radius,
    )
    return rmap

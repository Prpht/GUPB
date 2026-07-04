import math
import numpy as np
from gupb.model import coordinates, tiles
from . import _has_mist

_PASSABLE_TILE_TYPES = frozenset({"land", "forest", "menhir"})


def estimate_menhir_position(
    map_data: dict[coordinates.Coords, tiles.TileDescription],
    mist_seen: set[coordinates.Coords] | frozenset[coordinates.Coords],
    bot_pos: coordinates.Coords,
    seen_positions: (
        set[coordinates.Coords] | frozenset[coordinates.Coords]
    ) = frozenset(),
) -> coordinates.Coords | None:
    if not mist_seen:
        return None

    map_keys = list(map_data.keys())
    if not map_keys:
        return None

    xs_map = [p[0] for p in map_keys]
    ys_map = [p[1] for p in map_keys]
    xs_mist = [p[0] for p in mist_seen]
    ys_mist = [p[1] for p in mist_seen]

    min_x = max(0, min(min(xs_map), min(xs_mist)))
    max_x = max(max(xs_map), max(xs_mist))
    min_y = max(0, min(min(ys_map), min(ys_mist)))
    max_y = max(max(ys_map), max(ys_mist))

    candidates = []
    for x in range(min_x, max_x + 1):
        for y in range(min_y, max_y + 1):
            pos = coordinates.Coords(x, y)
            if pos in mist_seen:
                continue
            if pos in seen_positions:
                continue
            tile = map_data.get(pos)
            if tile is not None:
                if tile.type not in _PASSABLE_TILE_TYPES or _has_mist(tile):
                    continue
            candidates.append(pos)

    if not candidates:
        return None

    cand_arr = np.array(candidates, dtype=np.float32)
    mist_arr = np.array(list(mist_seen), dtype=np.float32)

    diff = cand_arr[:, None, :] - mist_arr[None, :, :]
    dist_sq = (diff**2).sum(axis=2)
    min_dist_sq = dist_sq.min(axis=1)

    best = min_dist_sq.max()
    tied = np.where(min_dist_sq >= best - 1e-6)[0]

    if len(tied) > 1:
        bot_arr = np.array(bot_pos, dtype=np.float32)
        bot_dist_sq = ((cand_arr[tied] - bot_arr) ** 2).sum(axis=1)
        pick = tied[int(np.argmax(bot_dist_sq))]
    else:
        pick = int(tied[0])

    return candidates[pick]


def calculate_confidence(
    estimated_pos: coordinates.Coords,
    mist_seen: set[coordinates.Coords] | frozenset[coordinates.Coords],
) -> float:
    angles = []
    for p in mist_seen:
        dx = p[0] - estimated_pos[0]
        dy = p[1] - estimated_pos[1]
        if dx == 0 and dy == 0:
            continue
        angles.append(math.atan2(dy, dx))

    if len(angles) < 2:
        return 0.0

    angles.sort()
    max_gap = angles[0] + 2 * math.pi - angles[-1]
    for i in range(len(angles) - 1):
        gap = angles[i + 1] - angles[i]
        if gap > max_gap:
            max_gap = gap

    coverage = 1.0 - max_gap / (2 * math.pi)
    return max(0.0, min(1.0, coverage))

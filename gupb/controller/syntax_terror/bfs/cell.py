import collections
import heapq
import itertools
import math

from gupb.model import coordinates, tiles

from ..memory import MapMemory
from ..mist import MistInfo, is_pos_mist_at
from .cache import DistanceMap
from .constants import _INF, _STEP_BASE_COST
from .damage import _enemy_attack_cells, ENEMY_RANGE_PENALTY
from .helpers import is_walkable_tile, _neighbors
from .options import BfsCost


def _hp_penalty_table(self_hp: int) -> list[int]:
    return [
        int(100.0 * (math.exp(4.0 * hp / max(1, self_hp)) - 1.0))
        for hp in range(self_hp + 1)
    ]


def _cell_hp_loss(
    tile: tiles.TileDescription,
    pos: coordinates.Coords,
    ticks_ahead: int,
    cost: BfsCost,
    mist_info: MistInfo | None,
    attacked_cells: dict[coordinates.Coords, int],
) -> int:
    hp_loss = 0
    effect_types = {e.type for e in tile.effects}
    if cost.fire and "fire" in effect_types:
        hp_loss += 3
    if cost.mist and (
        "mist" in effect_types or is_pos_mist_at(mist_info, pos, ticks_ahead)
    ):
        hp_loss += 1
    # Enemy attack range is no longer treated as real HP loss. It is handled as
    # a flat traversal penalty in compute_cell_costs instead (ENEMY_RANGE_PENALTY)
    # so the bot routes around enemies without exponential punishment. To restore
    # HP-based avoidance, flip `if False:` back to `if cost.enemy_range:`.
    if False:  # noqa: SIM223 - enemy attack damage as real HP loss (disabled)
        if cost.enemy_range:
            hp_loss += attacked_cells.get(pos, 0)
    return hp_loss


def compute_cell_costs(
    start: coordinates.Coords,
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    cost: BfsCost,
    self_hp: int,
    memory: MapMemory,
    ignored_enemy_pos: coordinates.Coords | None = None,
) -> DistanceMap:
    distances = DistanceMap({start: 0})
    distances.times = {start: 0}
    distances.hp_lost = {start: 0}
    distances.parents = {}

    penalty = _hp_penalty_table(self_hp)
    mist_info = memory.mist_info if cost.account_hp and cost.mist else None
    attacked_cells = (
        _enemy_attack_cells(start, known_map, ignored_enemy_pos)
        if cost.account_hp and cost.enemy_range
        else {}
    )

    counter = itertools.count()
    queue: list[tuple[int, int, int, coordinates.Coords]] = [
        (0, 0, next(counter), start)
    ]

    while queue:
        current_cost, current_time, _, pos = heapq.heappop(queue)
        if current_cost > distances.get(pos, _INF):
            continue
        current_hp_lost = distances.hp_lost[pos]

        for nxt in _neighbors(pos):
            tile = known_map.get(nxt)
            if tile is None or not is_walkable_tile(tile):
                continue
            if cost.enemy_blocked and tile.character is not None and nxt != start:
                continue

            new_time = current_time + 1
            if cost.account_hp:
                step_hp = _cell_hp_loss(
                    tile, nxt, new_time, cost, mist_info, attacked_cells
                )
                total_hp_lost = current_hp_lost + step_hp
                if total_hp_lost >= self_hp:
                    continue
                enemy_pen = (
                    # ENEMY_RANGE_PENALTY
                    round(ENEMY_RANGE_PENALTY * (0.85 ** (new_time - 1)))
                    if cost.enemy_range and nxt in attacked_cells
                    else 0
                )
                new_cost = (
                    current_cost
                    + _STEP_BASE_COST
                    + penalty[total_hp_lost]
                    - penalty[current_hp_lost]
                    + enemy_pen
                )
            else:
                total_hp_lost = current_hp_lost
                new_cost = current_cost + _STEP_BASE_COST

            if new_cost < distances.get(nxt, _INF):
                distances[nxt] = new_cost
                distances.times[nxt] = new_time
                distances.hp_lost[nxt] = total_hp_lost
                distances.parents[nxt] = pos
                heapq.heappush(queue, (new_cost, new_time, next(counter), nxt))

    return distances


def multi_source_cell_distances(
    sources: list[coordinates.Coords],
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    blocked: frozenset[coordinates.Coords] = frozenset(),
) -> dict[coordinates.Coords, int]:
    # All edges have unit weight, so a plain FIFO breadth-first sweep settles
    # every cell at its shortest distance on first visit. This matches the
    # previous Dijkstra-with-a-heap implementation exactly while avoiding the
    # heap overhead (the dominant cost when run over thousands of cells).
    distances: dict[coordinates.Coords, int] = {}
    queue: collections.deque[coordinates.Coords] = collections.deque()
    for source in sources:
        if source in distances:
            continue
        distances[source] = 0
        queue.append(source)

    while queue:
        pos = queue.popleft()
        new_dist = distances[pos] + 1
        for nxt in _neighbors(pos):
            if nxt in distances or nxt in blocked:
                continue
            tile = known_map.get(nxt)
            if tile is None or not is_walkable_tile(tile):
                continue
            distances[nxt] = new_dist
            queue.append(nxt)

    return distances

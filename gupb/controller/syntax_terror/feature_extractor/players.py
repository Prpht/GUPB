import numpy as np
from gupb.model import coordinates, tiles

from ..memory import MapMemory
from ..bfs.turn_nav import TurnNavigation
from ..bfs.cell import multi_source_cell_distances
from ..combat.firing import firing_positions
from .constants import (
    _MAX_NEAREST_PLAYERS,
    _PLAYER_FEATURE_DIM,
    _PLAYER_WEAPON_DIM,
    _PLAYER_HP_OFFSET,
    _normalize_cost,
    player_slot_offset,
)
from .weapons_encoding import encode_direction, player_weapon_one_hot

PlayerEntry = tuple[float, float, float, int, int, float, str]

_UNREACHABLE = 999999
_FAR = 10000.0


def _default_player_slot(out: np.ndarray, slot: int) -> None:
    base = player_slot_offset(slot)
    out[base : base + _PLAYER_WEAPON_DIM] = player_weapon_one_hot("knife")
    out[base + _PLAYER_HP_OFFSET] = 0.0
    out[base + _PLAYER_HP_OFFSET + 1] = 1.0
    out[base + _PLAYER_HP_OFFSET + 2] = 1.0
    out[base + _PLAYER_HP_OFFSET + 3] = 1.0
    out[base + _PLAYER_HP_OFFSET + 4] = 0.0
    out[base + _PLAYER_HP_OFFSET + 5] = 0.0


def _encode_nearest_players(
    players: list[PlayerEntry],
    start: coordinates.Coords,
) -> np.ndarray:
    out = np.empty(_PLAYER_FEATURE_DIM, dtype=np.float32)
    for i in range(_MAX_NEAREST_PLAYERS):
        _default_player_slot(out, i)
    for i, (d_opp, d_me, return_cost, x, y, hp, weapon_name) in enumerate(
        players[:_MAX_NEAREST_PLAYERS]
    ):
        base = player_slot_offset(i)
        out[base : base + _PLAYER_WEAPON_DIM] = player_weapon_one_hot(weapon_name)
        out[base + _PLAYER_HP_OFFSET] = hp
        out[base + _PLAYER_HP_OFFSET + 1] = _normalize_cost(d_me, _FAR)
        out[base + _PLAYER_HP_OFFSET + 2] = _normalize_cost(d_opp, _FAR)
        out[base + _PLAYER_HP_OFFSET + 3] = _normalize_cost(return_cost, _UNREACHABLE)
        cos_t, sin_t = encode_direction(start, coordinates.Coords(x, y))
        out[base + _PLAYER_HP_OFFSET + 4] = cos_t
        out[base + _PLAYER_HP_OFFSET + 5] = sin_t
    return out


def _collect_raw_players(
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    distances: dict[coordinates.Coords, int],
    start: coordinates.Coords,
) -> list[tuple[int, coordinates.Coords, tiles.TileDescription]]:
    raw_players = []
    for pos, tile in known_map.items():
        if tile.character and pos != start:
            walk_dist = distances.get(pos)
            if walk_dist is None:
                dx = start[0] - pos[0]
                dy = start[1] - pos[1]
                walk_dist = int(np.round(np.sqrt(dx * dx + dy * dy)))
            raw_players.append((walk_dist, pos, tile))
    raw_players.sort(key=lambda x: x[0])
    return raw_players


def _calculate_k_limit(
    raw_players: list,
    memory: MapMemory,
    no_of_champions_alive: int,
) -> int:
    return min(len(memory.players), no_of_champions_alive - 1)


def build_opp_distance_maps(
    start: coordinates.Coords,
    raw_players: list[tuple[int, coordinates.Coords, tiles.TileDescription]],
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    memory: MapMemory,
) -> dict[str, dict[coordinates.Coords, int]]:
    maps: dict[str, dict[coordinates.Coords, int]] = {}
    for _, _, tile in raw_players:
        weapon = tile.character.weapon.name
        if weapon in maps:
            continue
        sources = firing_positions(start, weapon, known_map, memory)
        maps[weapon] = multi_source_cell_distances(sources, known_map)
    return maps


def _calculate_player_costs(
    start: coordinates.Coords,
    pos: coordinates.Coords,
    my_weapon: str,
    memory: MapMemory,
    turn_nav: TurnNavigation,
    d_opp: int | None,
) -> tuple[float, float, float]:
    d_me = None
    best_firing_pos = None
    for firing_pos in firing_positions(pos, my_weapon, memory.map_data, memory):
        cost = turn_nav.forward.get(firing_pos)
        if cost is not None and (d_me is None or cost < d_me):
            d_me = cost
            best_firing_pos = firing_pos

    memory.firing_positions_exist[pos] = d_me is not None

    val_me = float(d_me) if d_me is not None else _FAR
    val_opp = float(d_opp) if d_opp is not None else _FAR

    target_pos = best_firing_pos if best_firing_pos is not None else pos
    return_cost = turn_nav.nav_score(target_pos)
    if return_cost >= _UNREACHABLE:
        if turn_nav.return_map is not None and start in turn_nav.return_map.pos_to_idx:
            return_cost = float(_UNREACHABLE)
        else:
            return_cost = val_me if d_me is not None else float(_UNREACHABLE)

    return val_opp, val_me, return_cost


def indicator_from_costs(
    start: coordinates.Coords,
    turn_nav: TurnNavigation,
    val_opp: float,
    val_me: float,
    return_cost: float,
) -> float:
    m = 0.5
    shift = 0.25
    c = 20.0
    p = 1.0
    a = 2.0

    if val_me >= _FAR and val_opp >= _FAR:
        return -0.5

    if val_me + val_opp == 0.0:
        base_indicator = 0.0
    else:
        base_indicator = (val_opp - val_me) / (val_me + val_opp)

    rc = return_cost
    if rc >= _UNREACHABLE:
        if turn_nav.return_map is not None and start in turn_nav.return_map.pos_to_idx:
            return -0.6
        rc = val_me if val_me < _FAR else float(_UNREACHABLE)

    penalty_factor = a / (1.0 + (rc / c) ** p)
    return -0.5 + (m * base_indicator + shift) * penalty_factor

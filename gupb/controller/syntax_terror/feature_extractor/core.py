import numpy as np
from gupb.model import coordinates, tiles
from ..memory import MapMemory
from ..bfs.turn_nav import TurnNavigation
from .constants import (
    _DEFAULT_MIST_RADIUS,
    _normalize_hp,
)
from .items import ItemEntry, _encode_nearest_items
from .players import (
    PlayerEntry,
    _collect_raw_players,
    _calculate_k_limit,
    _calculate_player_costs,
    _encode_nearest_players,
    build_opp_distance_maps,
)
from .meta import _encode_meta
from .weapons_encoding import tile_item_weapon_type

_UNREACHABLE = 999999


def _on_mist(
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    position: coordinates.Coords,
) -> bool:
    tile = known_map.get(position)
    return bool(tile and any(e.type == "mist" for e in tile.effects))


def _extract_map_entities(
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    distances: dict[coordinates.Coords, int],
    start: coordinates.Coords,
    menhir_pos: coordinates.Coords | None,
    my_weapon: str,
    memory: MapMemory,
    no_of_champions_alive: int,
) -> tuple[list[ItemEntry], list[PlayerEntry], float, float | None]:
    items: list[ItemEntry] = []
    players: list[PlayerEntry] = []
    best_menhir_distance: int | None = None
    if menhir_pos is not None:
        best_menhir_distance = distances.get(menhir_pos)
        if best_menhir_distance is None:
            dx = start[0] - menhir_pos[0]
            dy = start[1] - menhir_pos[1]
            best_menhir_distance = int(np.round(np.sqrt(dx * dx + dy * dy)))

    turn_nav = TurnNavigation.get(memory)
    my_weapon_base = my_weapon.split("_")[0]
    for pos, tile in known_map.items():
        if pos == start:
            continue
        if tile.loot is None and tile.consumable is None:
            continue
        weapon_type = tile_item_weapon_type(tile)
        if tile.loot is not None and tile.loot.name.split("_")[0] == my_weapon_base:
            if my_weapon_base != "scroll" or memory.my_scroll_charges >= 5:
                continue
        distance = turn_nav.nav_score(pos)
        if distance < _UNREACHABLE:
            items.append((distance, pos[0], pos[1], weapon_type))
        if tile.type == "menhir":
            distance = distances.get(pos)
            if distance is not None:
                if best_menhir_distance is None or distance < best_menhir_distance:
                    best_menhir_distance = distance

    raw_players = _collect_raw_players(known_map, distances, start)
    k = _calculate_k_limit(raw_players, memory, no_of_champions_alive)
    opp_maps = build_opp_distance_maps(start, raw_players, known_map, memory)

    for walk_dist, pos, tile in raw_players:
        hp = _normalize_hp(tile.character.health)
        weapon_name = tile.character.weapon.name
        d_opp = opp_maps[tile.character.weapon.name].get(pos)
        d_opp_val, d_me_val, return_cost = _calculate_player_costs(
            start, pos, my_weapon, memory, turn_nav, d_opp
        )
        players.append(
            (d_opp_val, d_me_val, return_cost, pos[0], pos[1], hp, weapon_name)
        )

    players.sort(key=lambda p: (p[0], p[1], p[2]))
    players = players[:k]
    memory.last_extracted_players = [coordinates.Coords(p[3], p[4]) for p in players]

    items.sort(key=lambda item: (item[0], item[1], item[2]))
    menhir_distance = (
        float(best_menhir_distance)
        if best_menhir_distance is not None
        else _DEFAULT_MIST_RADIUS / 2.0
    )
    # Mist proximity is tracked persistently in memory (every mist tile ever
    # seen), so it stays valid even when the menhir is unknown and after the
    # frame filter has trimmed mist out of the trimmed map.
    observed_mist_distance = memory.observed_mist_distance
    memory._turn_extract_snapshot = {
        "items": items,
        "players": players,
        "menhir_distance": menhir_distance,
        "observed_mist_distance": observed_mist_distance,
    }
    return items, players, menhir_distance, observed_mist_distance


def extract_features(
    known_map: dict[coordinates.Coords, tiles.TileDescription],
    distances: dict[coordinates.Coords, int],
    start: coordinates.Coords,
    no_of_champions_alive: int,
    self_hp: int,
    self_weapon: str,
    mist_radius: float | None,
    menhir_pos: coordinates.Coords | None,
    mist_tick_counter: int,
    memory: MapMemory,
) -> np.ndarray:
    items, players, menhir_distance, observed_mist_distance = _extract_map_entities(
        known_map,
        distances,
        start,
        menhir_pos,
        self_weapon,
        memory,
        no_of_champions_alive,
    )
    return np.concatenate(
        (
            _encode_nearest_items(items, start),
            _encode_nearest_players(players, start),
            _encode_meta(
                menhir_distance,
                mist_radius,
                no_of_champions_alive,
                self_hp,
                self_weapon,
                mist_tick_counter,
                observed_mist_distance,
                menhir_pos,
                start,
                _on_mist(known_map, start),
                memory.my_scroll_charges,
            ),
        )
    )

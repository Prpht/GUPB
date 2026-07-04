import math
from collections import deque
from typing import NamedTuple

from gupb.model import characters, coordinates, tiles
from ..bfs.helpers import _neighbors


MIST_TTH_PER_CHAMPION: int = 2
_MIST_KEEP_RADIUS: int = 5
_MIST_SAFE_RADIUS: int = 100
_MENHIR_CONFIDENCE_THRESHOLD: float = 0.7

# Estymacja pozycji menhira z widzianej mgły jest wylaczona. Zweryfikowane na
# stanowisku testowym: estymata (najdalsze pole od mgly) i confidence (pokrycie
# katowe) sa poprawne i bezpieczne tylko gdy bot zobaczyl mgle z wielu stron
# (pelne okrazenie -> err 0, conf ~0.95). Przy obserwacji jednostronnej (typowej
# np. na test-walled-menhir, gdzie sciany zaslaniaja mgle po drugiej stronie, a
# bot ucieka tylko od strony mgly) srodka okregu nie da sie zlokalizowac zadna
# metoda - confidence slusznie zostaje ~0.25 i nigdy nie przekracza progu. Aby
# bot nie marnowal czasu na bezuzyteczne (i kosztowne - skan calej siatki co
# ture) wywolania, caly tor estymacji jest pomijany. Bezposrednie zobaczenie
# menhira dziala niezaleznie. Ustaw na True aby przywrocic estymacje.
_MENHIR_ESTIMATION_ENABLED: bool = False


class MistInfo(NamedTuple):
    menhir_pos: coordinates.Coords | None
    mist_radius: int | None
    mist_tick_counter: int
    alive_count: int
    mist_seen: frozenset[coordinates.Coords] | set[coordinates.Coords] = frozenset()


def _distance_to_menhir(pos: coordinates.Coords, menhir_pos: coordinates.Coords) -> int:
    return int(math.sqrt((pos[0] - menhir_pos[0]) ** 2 + (pos[1] - menhir_pos[1]) ** 2))


def _has_mist(tile: tiles.TileDescription) -> bool:
    for effect in tile.effects:
        if effect.type == "mist":
            return True
    return False


def predict_mist_radius(info, ticks_ahead: int) -> int:
    if info.mist_radius is None:
        return _MIST_SAFE_RADIUS
    ticks_per_step = MIST_TTH_PER_CHAMPION * info.alive_count
    steps_ahead = (info.mist_tick_counter + ticks_ahead) // ticks_per_step
    return max(0, info.mist_radius - steps_ahead)


def is_pos_mist_at(info, pos: coordinates.Coords, ticks_ahead: int) -> bool:
    if pos in info.mist_seen:
        return True
    if info.menhir_pos is None:
        return False
    r = predict_mist_radius(info, ticks_ahead)
    dx = pos[0] - info.menhir_pos[0]
    dy = pos[1] - info.menhir_pos[1]
    return dx * dx + dy * dy >= r * r


def _detect_visible_mist_radius(
    visible_tiles: dict[coordinates.Coords, tiles.TileDescription],
    menhir_pos: coordinates.Coords,
) -> int | None:
    detected: int | None = None
    for pos, tile in visible_tiles.items():
        if not _has_mist(tile):
            continue
        dist = _distance_to_menhir(pos, menhir_pos)
        if detected is None or dist < detected:
            detected = dist
    return detected


def _locate_menhir(
    visible_tiles: dict[coordinates.Coords, tiles.TileDescription],
) -> coordinates.Coords | None:
    for pos, tile in visible_tiles.items():
        if tile.type == "menhir":
            return pos
    return None


def _update_observed_mist_distance(
    memory, knowledge: characters.ChampionKnowledge
) -> None:
    seen = memory.mist_seen
    for coords, tile in knowledge.visible_tiles.items():
        if _has_mist(tile):
            seen.add(coords)
    if not seen:
        memory.observed_mist_distance = None
        return
    px, py = knowledge.position
    memory.observed_mist_distance = float(
        min(abs(c[0] - px) + abs(c[1] - py) for c in seen)
    )


def update_mist_info(memory, knowledge: characters.ChampionKnowledge) -> None:
    _update_observed_mist_distance(memory, knowledge)

    visible_menhir = _locate_menhir(knowledge.visible_tiles)
    if visible_menhir is not None:
        memory.menhir_pos = visible_menhir
        memory.menhir_verified = True
        memory.menhir_estimated_pos = visible_menhir
        memory.menhir_confidence = 1.0
    elif not memory.menhir_verified:
        if _MENHIR_ESTIMATION_ENABLED:
            from .estimation import estimate_menhir_position, calculate_confidence

            estimated = estimate_menhir_position(
                memory.map_data,
                memory.mist_seen,
                knowledge.position,
                set(memory.last_seen.keys()),
            )
            if estimated is not None:
                memory.menhir_estimated_pos = estimated
                confidence = calculate_confidence(estimated, memory.mist_seen)
                memory.menhir_confidence = confidence
                if confidence >= _MENHIR_CONFIDENCE_THRESHOLD:
                    memory.menhir_pos = estimated
                else:
                    memory.menhir_pos = None
            else:
                memory.menhir_estimated_pos = None
                memory.menhir_confidence = 0.0
                memory.menhir_pos = None
        else:
            memory.menhir_estimated_pos = None
            memory.menhir_confidence = 0.0
            memory.menhir_pos = None

    pos = memory.menhir_pos
    if pos is None:
        memory.mist_tick_counter += 1
        return

    if memory.last_menhir_pos_for_mist != pos:
        memory.mist_radius = None
        memory.mist_tick_counter = 0
    memory.last_menhir_pos_for_mist = pos

    detected_radius = _detect_visible_mist_radius(knowledge.visible_tiles, pos)
    if detected_radius is None:
        memory.mist_tick_counter += 1
        return

    if memory.mist_radius is None or detected_radius < memory.mist_radius:
        memory.mist_radius = detected_radius
        memory.mist_tick_counter = 0
    else:
        memory.mist_tick_counter += 1


def _filter_tiles_with_mist_frame(
    all_tiles: dict[coordinates.Coords, tiles.TileDescription],
    keep: frozenset[coordinates.Coords] = frozenset(),
) -> dict[coordinates.Coords, tiles.TileDescription]:
    safe_tiles = [pos for pos, tile in all_tiles.items() if not _has_mist(tile)]
    if not safe_tiles:
        return all_tiles

    keep_set = set(safe_tiles)
    keep_set.update(keep)
    visited = set(keep_set)
    queue: deque[tuple[coordinates.Coords, int]] = deque((pos, 0) for pos in keep_set)

    while queue:
        pos, dist = queue.popleft()
        if dist >= _MIST_KEEP_RADIUS:
            continue
        x, y = pos
        for neighbor in ((x+1, y), (x-1, y), (x, y+1), (x, y-1)):
            if neighbor in all_tiles and neighbor not in visited:
                visited.add(neighbor)
                keep_set.add(neighbor)
                queue.append((neighbor, dist + 1))

    return {k: v for k, v in all_tiles.items() if k in keep_set}


def filter_memory(memory, position: coordinates.Coords | None = None) -> None:
    keep = frozenset({position}) if position is not None else frozenset()
    memory.map_data = _filter_tiles_with_mist_frame(memory.map_data, keep)


def filter_knowledge(
    knowledge: characters.ChampionKnowledge,
) -> characters.ChampionKnowledge:
    filtered = _filter_tiles_with_mist_frame(
        knowledge.visible_tiles, frozenset({knowledge.position})
    )
    return characters.ChampionKnowledge(
        knowledge.position, knowledge.no_of_champions_alive, filtered
    )

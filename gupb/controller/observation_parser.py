"""
Parser obserwacji do stałej długości wektora wejściowego dla sieci.

Zamienia zmienną wiedzę (visible_tiles o zmiennej liczbie pól) na wektor
o stałym rozmiarze INPUT_DIM. Zawiera m.in.:
- pozycję (znormalizowaną),
- liczbę żywych championów,
- pamięć: czy znamy menhir, odległość do menhiru, kąt do menhiru,
- siatkę 5x5 wokół gracza: dla każdego pola typ, czy jest przeciwnik, broń, consumable.
"""

from __future__ import annotations

import math
from typing import Dict, Optional

from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles

# Siatka wokół gracza: promień 2 = 5x5 = 25 pól
GRID_RADIUS = 2
GRID_SIZE = (2 * GRID_RADIUS + 1) ** 2  # 25

# Typy kafelków w kolejności (indeks = wartość dla sieci)
TILE_TYPES = ("land", "sea", "wall", "forest", "menhir")
TILE_TYPE_TO_ID = {t: i for i, t in enumerate(TILE_TYPES)}
NUM_TILE_TYPES = len(TILE_TYPES)

# Zakładana maks. wielkość areny do normalizacji pozycji (bez tej info z gry)
NORM_ARENA_SIZE = 50.0

# Składowe wektora:
# 2   - pozycja (x_norm, y_norm)
# 1   - liczba żywych / 10
# 1   - czy widzieliśmy menhir (0/1)
# 1   - odległość do menhiru (znorm.), 0 jeśli nie znamy
# 1   - kąt do menhiru w radianach / pi ([-1, 1]), 0 jeśli nie znamy
# 25*4 - siatka 5x5: każda komórka (typ_norm, has_character, has_loot, has_consumable)
INPUT_DIM = 2 + 1 + 1 + 1 + 1 + GRID_SIZE * 4  # 110


def _tile_type_to_norm(tile_type: str) -> float:
    """Mapuje typ kafelka na float 0..1."""
    idx = TILE_TYPE_TO_ID.get(tile_type.lower(), 0)
    return idx / max(1, NUM_TILE_TYPES - 1)


def _distance(a: coordinates.Coords, b: coordinates.Coords) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def _angle_to(from_pos: coordinates.Coords, to_pos: coordinates.Coords) -> float:
    """Kąt w radianach od from do to. Zwracamy znormalizowany do [-1, 1] (dzielony przez pi)."""
    dx = to_pos.x - from_pos.x
    dy = to_pos.y - from_pos.y
    if dx == 0 and dy == 0:
        return 0.0
    rad = math.atan2(dy, dx)
    return rad / math.pi


def encode_observation(
    knowledge: characters.ChampionKnowledge,
    menhir_position: Optional[coordinates.Coords],
) -> list[float]:
    """
    Zamienia knowledge + pamięć (pozycja menhiru) na wektor o stałej długości INPUT_DIM.

    menhir_position: zapamiętane współrzędne menhiru (np. po pierwszym zobaczeniu),
                     None jeśli jeszcze nie widzieliśmy.
    """
    pos = knowledge.position
    visible = knowledge.visible_tiles

    out: list[float] = []

    # Pozycja znormalizowana (clip do [0, 1])
    out.append(min(1.0, pos.x / NORM_ARENA_SIZE))
    out.append(min(1.0, pos.y / NORM_ARENA_SIZE))

    # Liczba żywych championów (np. max ~10)
    out.append(min(1.0, knowledge.no_of_champions_alive / 10.0))

    # Pamięć: menhir
    menhir_seen = 1.0 if menhir_position is not None else 0.0
    out.append(menhir_seen)

    if menhir_position is not None:
        dist = _distance(pos, menhir_position)
        out.append(min(1.0, dist / NORM_ARENA_SIZE))
        out.append(_angle_to(pos, menhir_position))
    else:
        out.append(0.0)
        out.append(0.0)

    # Siatka 5x5 wokół gracza (względne współrzędne -2..2)
    for dy in range(-GRID_RADIUS, GRID_RADIUS + 1):
        for dx in range(-GRID_RADIUS, GRID_RADIUS + 1):
            cell_coords = coordinates.Coords(pos.x + dx, pos.y + dy)
            if cell_coords in visible:
                td = visible[cell_coords]
                out.append(_tile_type_to_norm(td.type))
                out.append(1.0 if td.character is not None else 0.0)
                out.append(1.0 if td.loot is not None else 0.0)
                out.append(1.0 if td.consumable is not None else 0.0)
            else:
                # Nie widzimy tego pola (mgła / poza zasięgiem)
                out.append(0.0)
                out.append(0.0)
                out.append(0.0)
                out.append(0.0)

    assert len(out) == INPUT_DIM, f"Expected {INPUT_DIM}, got {len(out)}"
    return out

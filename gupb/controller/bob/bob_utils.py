"""Helpery Boba. Geometria, model broni, Dijkstra po znanej mapie i symulacje akcji
"""

from __future__ import annotations

import heapq
from typing import Callable, Dict, List, Optional, Set, Tuple

from gupb.model import characters
from gupb.model import coordinates

Coords = coordinates.Coords
Facing = characters.Facing
Action = characters.Action

PASSABLE_TYPES: Set[str] = {"land", "forest", "menhir"}
OPAQUE_TYPES: Set[str] = {"wall", "forest"}
BLOCKING_TYPES: Set[str] = {"wall", "sea"}

BOW_MAX_REACH = 50

WEAPON_RANK: Dict[str, int] = {
    "knife": 1,
    "scroll": 3,
    "amulet": 3,
    "axe": 5,
    "sword": 5,
    "bow": 6,
}

WEAPON_DAMAGE: Dict[str, int] = {
    "knife": 2,
    "sword": 2,
    "axe": 3,
    "amulet": 2,
    "bow": 3,
    "scroll": 3,
}

_UNIT_DELTAS: List[Coords] = [
    Coords(0, -1),
    Coords(0, 1),
    Coords(-1, 0),
    Coords(1, 0),
]

ALL_FACINGS = (Facing.UP, Facing.DOWN, Facing.LEFT, Facing.RIGHT)


def safe_getattr(obj, name, default=None):
    """getattr odporny na obiekty bez danego pola"""
    try:
        return getattr(obj, name, default)
    except Exception:
        return default


def to_coords(t) -> Coords:
    """konwersja na Coords"""
    return Coords(int(t[0]), int(t[1]))


def add(a, b) -> Coords:
    return Coords(a[0] + b[0], a[1] + b[1])


def manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def chebyshev(a, b) -> int:
    return max(abs(a[0] - b[0]), abs(a[1] - b[1]))


def base_weapon_name(name: Optional[str]) -> str:
    """Normalizacja nazwy broni"""
    if not name:
        return "knife"
    if name.startswith("bow"):
        return "bow"
    return name


def bow_is_loaded(name: Optional[str]) -> bool:
    return name == "bow_loaded"


def weapon_rank(name: Optional[str]) -> int:
    return WEAPON_RANK.get(base_weapon_name(name), 1)


def weapon_damage(name: Optional[str]) -> int:
    return WEAPON_DAMAGE.get(base_weapon_name(name), 2)


def weapon_value(name: Optional[str], phase: str, hp: int, enemies_visible: int) -> float:
    """
    Kontekstowa wartość broni zależna od fazy, HP i liczby widocznych wrogów
    """
    n = base_weapon_name(name)
    base = {"knife": 1.0, "scroll": 3.0, "amulet": 3.4, "bow": 5.0, "axe": 5.1, "sword": 5.4}.get(n, 1.0)
    v = base
    if hp <= 3:
        if n in ("bow", "scroll", "amulet"):
            v += 1.0
        if n == "axe":
            v -= 0.4
    if phase == "early" and n in ("sword", "axe"):
        v += 0.5
    if phase == "late" and n == "bow":
        v += 0.5
    if enemies_visible >= 2 and n == "bow":
        v += 0.7
    if enemies_visible >= 2 and n in ("axe", "sword"):
        v += 0.3
    return v


def neighbors4(c: Coords) -> List[Coords]:
    return [add(c, d) for d in _UNIT_DELTAS]


def facing_toward(src: Coords, dst: Coords) -> Optional[Facing]:
    """Kierunek kardynalny od src do dst, gdy leza w jednej linii"""
    dx = dst[0] - src[0]
    dy = dst[1] - src[1]
    if abs(dx) >= abs(dy):
        if dx > 0:
            return Facing.RIGHT
        if dx < 0:
            return Facing.LEFT
    if dy > 0:
        return Facing.DOWN
    if dy < 0:
        return Facing.UP
    return None


def simulate_action(pos: Coords, facing: Facing, action: Action) -> Tuple[Coords, Facing]:
    """
    Zwraca (nowa_pozycja, nowy_facing) po lokalnej symulacji akcji.
    STEP zmienia tylko pozycje, TURN tylko facing
    """
    if action == Action.TURN_LEFT:
        return pos, facing.turn_left()
    if action == Action.TURN_RIGHT:
        return pos, facing.turn_right()
    if action == Action.STEP_FORWARD:
        return add(pos, facing.value), facing
    if action == Action.STEP_BACKWARD:
        return add(pos, facing.opposite().value), facing
    if action == Action.STEP_LEFT:
        return add(pos, facing.turn_left().value), facing
    if action == Action.STEP_RIGHT:
        return add(pos, facing.turn_right().value), facing
    return pos, facing


def step_action_for_delta(facing: Facing, delta: Coords) -> Optional[Action]:
    """Dobiera akcje STEP przesuwajaca o delta bez zmiany facingu"""
    if delta == facing.value:
        return Action.STEP_FORWARD
    if delta == facing.opposite().value:
        return Action.STEP_BACKWARD
    if delta == facing.turn_left().value:
        return Action.STEP_LEFT
    if delta == facing.turn_right().value:
        return Action.STEP_RIGHT
    return None


def weapon_hit_tiles(
    weapon_name: Optional[str],
    pos: Coords,
    facing: Facing,
    in_map: Callable[[Coords], bool],
    is_opaque: Callable[[Coords], bool],
    max_reach: Optional[int] = None,
) -> List[Coords]:
    """
    Realne pola rażone przez broń z pozycji pos i kierunku facing.
    Odwzorowuje weapons.py: bronie liniowe zatrzymuja sie na polu nieprzezroczystym,
    axe razi luk 3 pol, amulet 8 pol po skosie. max_reach ogranicza skan luku
    """
    name = base_weapon_name(weapon_name)
    if name == "axe":
        centre = add(pos, facing.value)
        left = add(centre, facing.turn_left().value)
        right = add(centre, facing.turn_right().value)
        return [t for t in (left, centre, right) if in_map(t)]
    if name == "amulet":
        deltas = [(1, 1), (-1, 1), (1, -1), (-1, -1), (2, 2), (-2, 2), (2, -2), (-2, -2)]
        return [add(pos, Coords(dx, dy)) for dx, dy in deltas if in_map(add(pos, Coords(dx, dy)))]
    reach = {"knife": 1, "sword": 3, "scroll": 1, "bow": BOW_MAX_REACH}.get(name, 1)
    if max_reach is not None:
        reach = min(reach, max_reach)
    tiles: List[Coords] = []
    cur = pos
    for _ in range(reach):
        cur = add(cur, facing.value)
        if not in_map(cur):
            break
        tiles.append(cur)
        if is_opaque(cur):
            break
    return tiles


def attack_positions(
    weapon_name: Optional[str],
    enemy_pos: Coords,
    in_map: Callable[[Coords], bool],
    is_opaque: Callable[[Coords], bool],
    passable: Callable[[Coords], bool],
    max_reach: Optional[int] = None,
) -> Set[Coords]:
    """
    Zbiór przechodnich pól, z których dana bronia może trafic enemy_pos.
    Dla broni liniowych uwzglednia blokowanie linii przez pola nieprzezroczyste
    """
    name = base_weapon_name(weapon_name)
    res: Set[Coords] = set()
    if name == "amulet":
        for dx, dy in [(1, 1), (-1, 1), (1, -1), (-1, -1), (2, 2), (-2, 2), (2, -2), (-2, -2)]:
            c = add(enemy_pos, Coords(dx, dy))
            if passable(c):
                res.add(c)
        return res
    if name == "axe":
        for facing in ALL_FACINGS:
            forward = facing.value
            left = facing.turn_left().value
            right = facing.turn_right().value
            for hit_offset in (forward, add(forward, left), add(forward, right)):
                c = add(enemy_pos, Coords(-hit_offset[0], -hit_offset[1]))
                if passable(c):
                    res.add(c)
        return res
    reach = {"knife": 1, "sword": 3, "scroll": 1, "bow": BOW_MAX_REACH}.get(name, 1)
    if max_reach is not None:
        reach = min(reach, max_reach)
    for d in _UNIT_DELTAS:
        for k in range(1, reach + 1):
            c = add(enemy_pos, Coords(d[0] * k, d[1] * k))
            if not in_map(c):
                break
            if k > 1:
                mid = add(enemy_pos, Coords(d[0] * (k - 1), d[1] * (k - 1)))
                if is_opaque(mid):
                    break
            if passable(c):
                res.add(c)
            if is_opaque(c):
                break
    return res


def dijkstra(
    sources: List[Coords],
    passable: Callable[[Coords], bool],
    tile_cost: Callable[[Coords], float],
) -> Tuple[Dict[Coords, float], Dict[Coords, Coords]]:
    """
    Dijkstra po 4-sasiedztwie znanej mapy z kosztem wejscia zaleznym od pola (mgła/ogień/zagrożenie).
    Zwraca (dystans_od_zrodel, poprzednik)
    """
    dist: Dict[Coords, float] = {}
    prev: Dict[Coords, Coords] = {}
    heap: List[Tuple[float, int, int]] = []
    for s in sources:
        if passable(s):
            dist[s] = 0.0
            heapq.heappush(heap, (0.0, s[0], s[1]))
    while heap:
        d, x, y = heapq.heappop(heap)
        cur = Coords(x, y)
        if d > dist.get(cur, float("inf")):
            continue
        for nb in neighbors4(cur):
            if not passable(nb):
                continue
            nd = d + 1.0 + tile_cost(nb)
            if nd < dist.get(nb, float("inf")):
                dist[nb] = nd
                prev[nb] = cur
                heapq.heappush(heap, (nd, nb[0], nb[1]))
    return dist, prev


def reconstruct_next_step(
    prev: Dict[Coords, Coords], start: Coords, target: Coords
) -> Optional[Coords]:
    """Pierwsze pole na scieżce start -> target z drzewa Dijkstry"""
    if target == start:
        return start
    node = target
    while node in prev and prev[node] != start:
        node = prev[node]
    if node in prev and prev[node] == start:
        return node
    return None

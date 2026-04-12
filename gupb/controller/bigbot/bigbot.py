from __future__ import annotations

import heapq
import math
from collections import deque
from typing import Optional

import bresenham

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles

# Teren: None = nie widziane, True = przechodni typ (land/forest/menhir), False = ściana/morze
TerrainWalkable = Optional[bool]
# Znany typ pola (dla promieni miecza/łuku)
TileKind = Optional[str]

STAGNATION_NO_NEW_MAP_MOVES = 8
STAGNATION_VISION_LOOT_MOVES = 4
LIFE_PICKUP_MAX_MANHATTAN = 3
WEAPON_SWITCH_MIN_DAMAGE_DELTA = 1
WEAPON_SWITCH_MIN_STRIKE_DELTA = 2
WEAPON_VISION_MIN_DELTA = 2
MIST_FLEE_GOAL_LEAD = 5
MIST_FLEE_GOAL_CHEB_RADIUS = 2
MIST_FLEE_HALF_PLANE_EPS = 0.15

_CARDINAL: tuple[coordinates.Coords, ...] = (
    coordinates.Coords(0, -1),
    coordinates.Coords(1, 0),
    coordinates.Coords(0, 1),
    coordinates.Coords(-1, 0),
)


def _xy_pair(c: coordinates.Coords | tuple[int, int]) -> tuple[int, int]:
    if isinstance(c, coordinates.Coords):
        return c.x, c.y
    return int(c[0]), int(c[1])


def _terrain_walkable_from_type(type_name: str) -> bool:
    return type_name in ("land", "forest", "menhir")


def _ray_blocked_by_terrain(kind: TileKind) -> bool:
    """Zatrzymanie linii ciosu jak w LineWeapon (nieprzejrzysty teren)."""
    if kind is None:
        return False
    return kind in ("wall", "forest")


def _passable_for_astar(
    x: int,
    y: int,
    width: int,
    height: int,
    terrain: list[list[TerrainWalkable]],
    enemy_cells: set[coordinates.Coords],
) -> bool:
    if not (0 <= x < width and 0 <= y < height):
        return False
    if coordinates.Coords(x, y) in enemy_cells:
        return False
    w = terrain[x][y]
    if w is None:
        return True
    return w


def _multi_goal_astar(
    start: coordinates.Coords,
    goals: set[coordinates.Coords],
    width: int,
    height: int,
    terrain: list[list[TerrainWalkable]],
    enemy_cells: set[coordinates.Coords],
) -> Optional[list[coordinates.Coords]]:
    if start in goals:
        return [start]

    def heuristic(p: coordinates.Coords) -> float:
        return min(abs(p.x - g.x) + abs(p.y - g.y) for g in goals)

    open_heap: list[tuple[float, int, coordinates.Coords]] = []
    heapq.heappush(open_heap, (heuristic(start), 0, start))
    g_score: dict[coordinates.Coords, float] = {start: 0.0}
    came_from: dict[coordinates.Coords, coordinates.Coords] = {}

    while open_heap:
        _, g, current = heapq.heappop(open_heap)
        if g > g_score.get(current, math.inf):
            continue
        if current in goals:
            path = [current]
            while path[-1] != start:
                path.append(came_from[path[-1]])
            path.reverse()
            return path

        for d in _CARDINAL:
            nxt = coordinates.Coords(current.x + d.x, current.y + d.y)
            if not _passable_for_astar(
                nxt.x, nxt.y, width, height, terrain, enemy_cells
            ):
                continue
            tentative = g + 1.0
            if tentative < g_score.get(nxt, math.inf):
                came_from[nxt] = current
                g_score[nxt] = tentative
                f = tentative + heuristic(nxt)
                heapq.heappush(open_heap, (f, tentative, nxt))
    return None


def _unknown_neighbor(
    pos: coordinates.Coords,
    width: int,
    height: int,
    terrain: list[list[TerrainWalkable]],
) -> Optional[coordinates.Coords]:
    for d in _CARDINAL:
        n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
        if 0 <= n.x < width and 0 <= n.y < height and terrain[n.x][n.y] is None:
            return n
    return None


def _frontier_goals(
    width: int,
    height: int,
    terrain: list[list[TerrainWalkable]],
) -> set[coordinates.Coords]:
    goals: set[coordinates.Coords] = set()
    for x in range(width):
        for y in range(height):
            known = terrain[x][y]
            if known is None or not known:
                continue
            for d in _CARDINAL:
                nx, ny = x + d.x, y + d.y
                if 0 <= nx < width and 0 <= ny < height:
                    if terrain[nx][ny] is None:
                        goals.add(coordinates.Coords(x, y))
                        break
    return goals


def _is_frontier_coord(
    pos: coordinates.Coords,
    width: int,
    height: int,
    terrain: list[list[TerrainWalkable]],
) -> bool:
    x, y = pos.x, pos.y
    known = terrain[x][y]
    if known is None or not known:
        return False
    for d in _CARDINAL:
        nx, ny = x + d.x, y + d.y
        if 0 <= nx < width and 0 <= ny < height and terrain[nx][ny] is None:
            return True
    return False


def _first_step_action(
    facing: characters.Facing,
    current: coordinates.Coords,
    nxt: coordinates.Coords,
) -> characters.Action:
    delta = coordinates.Coords(nxt.x - current.x, nxt.y - current.y)
    if facing.value == delta:
        return characters.Action.STEP_FORWARD
    if facing.opposite().value == delta:
        return characters.Action.STEP_BACKWARD
    if facing.turn_left().value == delta:
        return characters.Action.STEP_LEFT
    if facing.turn_right().value == delta:
        return characters.Action.STEP_RIGHT
    return characters.Action.TURN_LEFT


def _cardinals_by_alignment(ix: float, iy: float) -> list[coordinates.Coords]:
    """Kardynały od najlepszego dopasowania do wektora (ix, iy) — kierunek ucieczki / biegu."""
    scored: list[tuple[float, coordinates.Coords]] = []
    for d in _CARDINAL:
        scored.append((d.x * ix + d.y * iy, d))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [d for _, d in scored]


def _facing_matches_move_delta(
    facing: characters.Facing,
    pos: coordinates.Coords,
    nxt: coordinates.Coords,
) -> bool:
    d = coordinates.Coords(nxt.x - pos.x, nxt.y - pos.y)
    return facing.value == d


def _exploration_forward_step_action(
    facing: characters.Facing,
    current: coordinates.Coords,
    nxt: coordinates.Coords,
    spin_locked: bool,
) -> characters.Action:
    """
    Odkrywanie mapy: patrzymy w stronę, w którą idziemy (nóż widzi przed sobą).
    Przy spin-lock zostaje dowolny STEP_* jednym ruchem — bez kolejnych obrotów.
    """
    if spin_locked:
        return _first_step_action(facing, current, nxt)
    delta = coordinates.Coords(nxt.x - current.x, nxt.y - current.y)
    turn = _single_turn_toward_world_delta(facing, delta)
    if turn is not None:
        return turn
    return characters.Action.STEP_FORWARD


def _single_turn_toward_world_delta(
    facing: characters.Facing,
    world_delta: coordinates.Coords,
) -> Optional[characters.Action]:
    if facing.value == world_delta:
        return None
    if facing.turn_left().value == world_delta:
        return characters.Action.TURN_LEFT
    if facing.turn_right().value == world_delta:
        return characters.Action.TURN_RIGHT
    return characters.Action.TURN_LEFT


def _action_peek_blind_adjacent_unknown(
    knowledge: characters.ChampionKnowledge,
    facing: characters.Facing,
    width: int,
    height: int,
    terrain: list[list[TerrainWalkable]],
) -> Optional[characters.Action]:
    pos = knowledge.position
    visible_xy = {_xy_pair(c) for c in knowledge.visible_tiles}
    priority = (
        facing.opposite().value,
        facing.turn_left().value,
        facing.turn_right().value,
        facing.value,
    )
    seen: set[coordinates.Coords] = set()
    for d in priority:
        if d in seen:
            continue
        seen.add(d)
        n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
        if not (0 <= n.x < width and 0 <= n.y < height):
            continue
        if terrain[n.x][n.y] is not None:
            continue
        if (n.x, n.y) in visible_xy:
            continue
        act = _single_turn_toward_world_delta(facing, d)
        if act is not None:
            return act
    return None


def _action_face_adjacent_unknown_for_frontier(
    pos: coordinates.Coords,
    facing: characters.Facing,
    width: int,
    height: int,
    terrain: list[list[TerrainWalkable]],
) -> Optional[characters.Action]:
    unknown_dirs: list[coordinates.Coords] = []
    for d in _CARDINAL:
        n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
        if not (0 <= n.x < width and 0 <= n.y < height):
            continue
        if terrain[n.x][n.y] is None:
            unknown_dirs.append(d)
    for d in unknown_dirs:
        if facing.value != d:
            act = _single_turn_toward_world_delta(facing, d)
            if act is not None:
                return act
    return None


def _tile_at_position(
    knowledge: characters.ChampionKnowledge,
) -> Optional[tiles.TileDescription]:
    px, py = knowledge.position.x, knowledge.position.y
    hit = knowledge.visible_tiles.get(knowledge.position)
    if hit is not None:
        return hit
    for key, desc in knowledge.visible_tiles.items():
        if _xy_pair(key) == (px, py):
            return desc
    return None


def _weapon_base(name: str) -> str:
    return name.split("_", 1)[0].lower()


_LOOT_WEAPON_BASES: frozenset[str] = frozenset(
    ("knife", "sword", "axe", "bow", "amulet", "scroll")
)


def _weapon_cut_damage(weapon_name: str) -> int:
    """Obrażenia ciosu wg typu (WeaponCut / Fire w silniku)."""
    wn = weapon_name.lower()
    base = _weapon_base(wn)
    if base in ("bow", "axe", "scroll"):
        return 3
    return 2


def _weapon_vision_score(weapon_name: str) -> int:
    """Przybliżona „jakość widzenia” do porównań (ankieta / stagnacja)."""
    base = _weapon_base(weapon_name.lower())
    if base == "amulet":
        return 32
    if base == "bow":
        return 24
    if base == "sword":
        return 4
    if base == "axe":
        return 6
    return 1


def _same_weapon_kind(held_name: str, loot_name: str) -> bool:
    return _weapon_base(held_name.lower()) == _weapon_base(loot_name.lower())


def _bow_loaded_from_weapon_name(weapon_name: str) -> Optional[bool]:
    """True/False z opisu silnika; None gdy nie wiemy (nie „bow_*”)."""
    lower = weapon_name.lower()
    if _weapon_base(lower) != "bow":
        return None
    if lower.endswith("_unloaded"):
        return False
    if lower.endswith("_loaded"):
        return True
    return None


def _strike_name_for_max_reach(weapon_name: str) -> str:
    """Łuk: liczymy zasięg jak przy strzale (załadowany)."""
    if _weapon_base(weapon_name.lower()) == "bow":
        return "bow_loaded"
    return weapon_name


def _strike_cells(
    pos: coordinates.Coords,
    facing: characters.Facing,
    weapon_name: str,
    tile_kind: list[list[TileKind]],
    width: int,
    height: int,
) -> set[coordinates.Coords]:
    """Pola, które faktycznie obejmuje cios (zgodnie z typami broni w silniku)."""
    wn = weapon_name.lower()
    base = _weapon_base(wn)
    out: set[coordinates.Coords] = set()

    def inb(c: coordinates.Coords) -> bool:
        return 0 <= c.x < width and 0 <= c.y < height

    if base == "bow" and wn.endswith("unloaded"):
        return out

    if base in ("knife", "scroll"):
        t = coordinates.Coords(pos.x + facing.value.x, pos.y + facing.value.y)
        if inb(t):
            out.add(t)
        return out

    if base == "axe":
        centre = coordinates.Coords(pos.x + facing.value.x, pos.y + facing.value.y)
        for c in (
            centre,
            coordinates.Coords(
                centre.x + facing.turn_left().value.x,
                centre.y + facing.turn_left().value.y,
            ),
            coordinates.Coords(
                centre.x + facing.turn_right().value.x,
                centre.y + facing.turn_right().value.y,
            ),
        ):
            if inb(c):
                out.add(c)
        return out

    if base == "amulet":
        for dx, dy in (
            (1, 1),
            (-1, 1),
            (1, -1),
            (-1, -1),
            (2, 2),
            (-2, 2),
            (2, -2),
            (-2, -2),
        ):
            c = coordinates.Coords(pos.x + dx, pos.y + dy)
            if inb(c):
                out.add(c)
        return out

    if base in ("sword", "bow"):
        reach = 50 if base == "bow" else 3
        cur = pos
        for _ in range(reach):
            cur = coordinates.Coords(cur.x + facing.value.x, cur.y + facing.value.y)
            if not inb(cur):
                break
            out.add(cur)
            k = tile_kind[cur.x][cur.y]
            if _ray_blocked_by_terrain(k):
                break
        return out

    t = coordinates.Coords(pos.x + facing.value.x, pos.y + facing.value.y)
    if inb(t):
        out.add(t)
    return out


_ALL_FACINGS: tuple[characters.Facing, ...] = (
    characters.Facing.UP,
    characters.Facing.RIGHT,
    characters.Facing.DOWN,
    characters.Facing.LEFT,
)


def _turn_one_step_toward_facing(
    cur: characters.Facing, goal: characters.Facing
) -> characters.Action:
    if cur.turn_left() == goal:
        return characters.Action.TURN_LEFT
    if cur.turn_right() == goal:
        return characters.Action.TURN_RIGHT
    return characters.Action.TURN_LEFT


def _vision_blocks_on_tile(kind: TileKind) -> bool:
    """Zgodnie z Arena.visible_coords: las i ściana zatrzymują promień."""
    if kind is None:
        return False
    return kind in ("wall", "forest")


def _approx_visible_coords(
    pos: coordinates.Coords,
    facing: characters.Facing,
    weapon_name: str,
    width: int,
    height: int,
    tile_kind: list[list[TileKind]],
) -> set[coordinates.Coords]:
    """Symulacja widoku jak w Arena.visible_coords (prescience albo klina Bresenhama)."""
    wn = weapon_name.lower()
    base = _weapon_base(wn)
    visible: set[coordinates.Coords] = {pos}
    if base == "amulet":
        r = 3
        for x in range(pos.x - r, pos.x + r + 1):
            for y in range(pos.y - r, pos.y + r + 1):
                if not (0 <= x < width and 0 <= y < height):
                    continue
                if (x - pos.x) ** 2 + (y - pos.y) ** 2 <= r * r + 1e-9:
                    visible.add(coordinates.Coords(x, y))
        return visible

    def estimate_border_point() -> tuple[coordinates.Coords, int]:
        if facing == characters.Facing.UP:
            return coordinates.Coords(pos.x, 0), pos.y
        if facing == characters.Facing.RIGHT:
            return coordinates.Coords(width - 1, pos.y), width - 1 - pos.x
        if facing == characters.Facing.DOWN:
            return coordinates.Coords(pos.x, height - 1), height - 1 - pos.y
        return coordinates.Coords(0, pos.y), pos.x

    def champion_left_and_right() -> list[coordinates.Coords]:
        if facing in (characters.Facing.UP, characters.Facing.DOWN):
            return [
                coordinates.Coords(pos.x + 1, pos.y),
                coordinates.Coords(pos.x - 1, pos.y),
            ]
        return [
            coordinates.Coords(pos.x, pos.y + 1),
            coordinates.Coords(pos.x, pos.y - 1),
        ]

    border, distance = estimate_border_point()
    left = facing.turn_left().value
    targets = [
        coordinates.Coords(border.x + i * left.x, border.y + i * left.y)
        for i in range(-distance, distance + 1)
    ]
    for tcoord in targets:
        ray = bresenham.bresenham(pos.x, pos.y, tcoord.x, tcoord.y)
        next(ray)
        for rx, ry in ray:
            ray_coords = coordinates.Coords(rx, ry)
            if not (0 <= ray_coords.x < width and 0 <= ray_coords.y < height):
                break
            visible.add(ray_coords)
            k = tile_kind[ray_coords.x][ray_coords.y]
            if _vision_blocks_on_tile(k):
                break
    for side in champion_left_and_right():
        if 0 <= side.x < width and 0 <= side.y < height:
            visible.add(side)
    return visible


def _clear_line_to_enemy(
    pos: coordinates.Coords,
    enemy: coordinates.Coords,
    step: coordinates.Coords,
    max_reach: int,
    width: int,
    height: int,
    tile_kind: list[list[TileKind]],
) -> bool:
    cur = pos
    for _ in range(max_reach):
        cur = coordinates.Coords(cur.x + step.x, cur.y + step.y)
        if not (0 <= cur.x < width and 0 <= cur.y < height):
            return False
        if cur == enemy:
            return True
        k = tile_kind[cur.x][cur.y]
        if _ray_blocked_by_terrain(k):
            return False
    return False


class BIGbot(controller.Controller):
    def __init__(self, bot_name: str = "BIGbot") -> None:
        self.bot_name = bot_name
        self._width: int = 0
        self._height: int = 0
        self._terrain: list[list[TerrainWalkable]] = []
        self._tile_kind: list[list[TileKind]] = []
        self._enemy_cells: set[coordinates.Coords] = set()
        self._menhir_position: Optional[coordinates.Coords] = None
        self._spin_pos: Optional[tuple[int, int]] = None
        self._anchor_facing: characters.Facing = characters.Facing.UP
        self._ever_deviated_from_anchor: bool = False
        self._steer_commit_pos: Optional[coordinates.Coords] = None
        self._steer_commit_nxt: Optional[coordinates.Coords] = None
        self._last_action: Optional[characters.Action] = None
        self._last_act_pos: Optional[coordinates.Coords] = None
        self._pre_action_pos: Optional[coordinates.Coords] = None
        self._pre_action_facing: Optional[characters.Facing] = None
        self._hp_last: Optional[int] = None
        self._stagnation_prev_known: int = 0
        self._moves_without_new_map: int = 0
        self._known_cells_count_this_tick: int = 0
        self._last_actions: deque[characters.Action] = deque(maxlen=8)
        self._enemy_info: dict[
            coordinates.Coords, tuple[characters.Facing, str]
        ] = {}
        self._mist_dot_floor: Optional[float] = None
        self._last_held_weapon_base: Optional[str] = None
        self._lifetime_seen_loot_weapon_bases: set[str] = set()
        self._weapon_equipped_transitions_into: dict[str, int] = {}
        self._weapon_seek_suppressed: bool = False

    def _standing_on_menhir(
        self, knowledge: characters.ChampionKnowledge, pos: coordinates.Coords
    ) -> bool:
        if self._menhir_position is not None and pos == self._menhir_position:
            return True
        here = _tile_at_position(knowledge)
        return here is not None and here.type == "menhir"

    def _menhir_spin_free_zone(self, pos: coordinates.Coords) -> bool:
        """Chebyshev ≤ 1 od znanego menhira — jak na menhirze: bez spin-locka."""
        if self._menhir_position is None:
            return False
        m = self._menhir_position
        return max(abs(pos.x - m.x), abs(pos.y - m.y)) <= 1

    def _menhir_ring_passable_goals(self) -> set[coordinates.Coords]:
        if self._menhir_position is None:
            return set()
        m = self._menhir_position
        goals: set[coordinates.Coords] = set()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                c = coordinates.Coords(m.x + dx, m.y + dy)
                if _passable_for_astar(
                    c.x,
                    c.y,
                    self._width,
                    self._height,
                    self._terrain,
                    self._enemy_cells,
                ):
                    goals.add(c)
        return goals

    def _best_menhir_wait_cell(
        self, pos: coordinates.Coords
    ) -> Optional[coordinates.Coords]:
        """
        Czekanie gdy menhir zajęty: możliwie najbliżej menhira; najpierw pola
        poza zasięgiem ciosów wrogów, inaczej najbliższe w ogóle.
        """
        m = self._menhir_position
        if m is None:
            return None
        threat = self._combined_enemy_threat()
        w, h = self._width, self._height
        best_safe: Optional[tuple[tuple[int, int, int, int], coordinates.Coords]] = None
        best_any: Optional[tuple[tuple[int, int, int, int], coordinates.Coords]] = None
        for x in range(w):
            for y in range(h):
                c = coordinates.Coords(x, y)
                if not _passable_for_astar(
                    c.x,
                    c.y,
                    w,
                    h,
                    self._terrain,
                    self._enemy_cells,
                ):
                    continue
                md = abs(c.x - m.x) + abs(c.y - m.y)
                pd = abs(c.x - pos.x) + abs(c.y - pos.y)
                key = (md, pd, c.x, c.y)
                if best_any is None or key < best_any[0]:
                    best_any = (key, c)
                if c not in threat:
                    if best_safe is None or key < best_safe[0]:
                        best_safe = (key, c)
        if best_safe is not None:
            return best_safe[1]
        return best_any[1] if best_any is not None else None

    def _menhir_approach_goal_set(
        self, pos: coordinates.Coords
    ) -> set[coordinates.Coords]:
        m = self._menhir_position
        if m is None:
            return set()
        if (
            m not in self._enemy_cells
            and _passable_for_astar(
                m.x,
                m.y,
                self._width,
                self._height,
                self._terrain,
                self._enemy_cells,
            )
        ):
            return {m}
        wait = self._best_menhir_wait_cell(pos)
        if wait is not None:
            return {wait}
        ring = self._menhir_ring_passable_goals()
        return ring if ring else {m}

    def _orthogonal_adjacent_enemy(
        self, pos: coordinates.Coords
    ) -> Optional[coordinates.Coords]:
        best: Optional[coordinates.Coords] = None
        for e in self._enemy_cells:
            if abs(e.x - pos.x) + abs(e.y - pos.y) != 1:
                continue
            if best is None or (e.x, e.y) < (best.x, best.y):
                best = e
        return best

    def _action_face_orthogonal_foe_then_strike(
        self,
        pos: coordinates.Coords,
        facing: characters.Facing,
    ) -> Optional[characters.Action]:
        foe = self._orthogonal_adjacent_enemy(pos)
        if foe is None:
            return None
        delta = coordinates.Coords(foe.x - pos.x, foe.y - pos.y)
        if facing.value == delta:
            return characters.Action.ATTACK
        return _single_turn_toward_world_delta(facing, delta)

    def _no_progress_since_last_action(
        self, pos: coordinates.Coords, facing: characters.Facing
    ) -> bool:
        if self._pre_action_pos is None or self._pre_action_facing is None:
            return False
        return pos == self._pre_action_pos and facing == self._pre_action_facing

    def _break_idle_after_blocked(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
    ) -> characters.Action:
        if self._last_action == characters.Action.ATTACK:
            if self._should_attack(knowledge, facing):
                side = self._any_passable_step_action(facing, pos)
                if side is not None:
                    return side
            return characters.Action.TURN_LEFT
        step_actions = (
            characters.Action.STEP_FORWARD,
            characters.Action.STEP_BACKWARD,
            characters.Action.STEP_LEFT,
            characters.Action.STEP_RIGHT,
        )
        if self._last_action in step_actions:
            for d in _CARDINAL:
                n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
                if not _passable_for_astar(
                    n.x, n.y, self._width, self._height, self._terrain, self._enemy_cells
                ):
                    continue
                alt = _first_step_action(facing, pos, n)
                if alt != self._last_action:
                    return alt
        return characters.Action.TURN_LEFT

    def _neighbor_ok_for_step(
        self, pos: coordinates.Coords, nxt: coordinates.Coords
    ) -> bool:
        if abs(pos.x - nxt.x) + abs(pos.y - nxt.y) != 1:
            return False
        return _passable_for_astar(
            nxt.x, nxt.y, self._width, self._height, self._terrain, self._enemy_cells
        )

    def _steering_nxt(
        self, pos: coordinates.Coords, astar_next: coordinates.Coords
    ) -> coordinates.Coords:
        """Na jednym polu trzymamy ten sam sąsiad docelowy — A* bywa niedeterministyczny przy remisach."""
        if self._steer_commit_pos != pos:
            self._steer_commit_pos = pos
            self._steer_commit_nxt = astar_next
            return astar_next
        if self._steer_commit_nxt is not None and self._neighbor_ok_for_step(
            pos, self._steer_commit_nxt
        ):
            return self._steer_commit_nxt
        self._steer_commit_nxt = astar_next
        return astar_next

    def _finalize_action(
        self,
        pos: coordinates.Coords,
        facing: characters.Facing,
        action: characters.Action,
        nxt: Optional[coordinates.Coords] = None,
    ) -> characters.Action:
        """Ostatnia obrona: +1 / -1 obrót na tym samym polu → idź bokiem lub w stronę nxt."""
        if (
            nxt is not None
            and action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT)
            and self._last_act_pos == pos
            and self._last_action is not None
        ):
            pair = {self._last_action, action}
            if pair == {characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT}:
                alt = _first_step_action(facing, pos, nxt)
                if alt not in (
                    characters.Action.TURN_LEFT,
                    characters.Action.TURN_RIGHT,
                ):
                    action = alt
                else:
                    step = self._any_passable_step_action(facing, pos)
                    if step is not None:
                        action = step
        self._last_action = action
        self._last_act_pos = pos
        self._pre_action_pos = pos
        self._pre_action_facing = facing
        self._last_actions.append(action)
        return action

    def _menhir_final_phase(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
    ) -> bool:
        """Na polu menhira — immunitet; tu nie liczymy stagnacji ani luksusowej stagnacji."""
        return self._standing_on_menhir(knowledge, pos)

    def _count_known_cells(self) -> int:
        return sum(
            1
            for x in range(self._width)
            for y in range(self._height)
            if self._terrain[x][y] is not None
        )

    def _held_weapon_name(
        self, knowledge: characters.ChampionKnowledge
    ) -> Optional[str]:
        here = _tile_at_position(knowledge)
        if here is None or here.character is None:
            return None
        return here.character.weapon.name

    def _visible_loot_weapon_bases(
        self, knowledge: characters.ChampionKnowledge
    ) -> set[str]:
        out: set[str] = set()
        for _, desc in knowledge.visible_tiles.items():
            if desc.loot is None or desc.character is not None:
                continue
            b = _weapon_base(desc.loot.name.lower())
            if b in _LOOT_WEAPON_BASES:
                out.add(b)
        return out

    def _update_weapon_seek_state(
        self, knowledge: characters.ChampionKnowledge
    ) -> None:
        visible_bases = self._visible_loot_weapon_bases(knowledge)
        new_types = visible_bases - self._lifetime_seen_loot_weapon_bases
        if new_types:
            self._weapon_equipped_transitions_into.clear()
            self._weapon_seek_suppressed = False
        self._lifetime_seen_loot_weapon_bases |= visible_bases

        here = _tile_at_position(knowledge)
        curr: Optional[str] = None
        if here is not None and here.character is not None:
            curr = _weapon_base(here.character.weapon.name.lower())
        if self._last_held_weapon_base is not None and curr is not None:
            if curr != self._last_held_weapon_base:
                n = self._weapon_equipped_transitions_into.get(curr, 0) + 1
                self._weapon_equipped_transitions_into[curr] = n
                if n >= 2:
                    self._weapon_seek_suppressed = True
        if curr is not None:
            self._last_held_weapon_base = curr

    def _weapon_max_strike_cell_count(self, weapon_name: str) -> int:
        """Max |strike cells| po obrocie — na otwartej siatce (bez wcześniejszego tnia lasu)."""
        if self._width == 0 or self._height == 0:
            return 0
        px, py = self._width // 2, self._height // 2
        pos = coordinates.Coords(px, py)
        open_tile: list[list[TileKind]] = [
            [None for _ in range(self._height)] for _ in range(self._width)
        ]
        wn = _strike_name_for_max_reach(weapon_name)
        best = 0
        for gf in _ALL_FACINGS:
            best = max(
                best,
                len(
                    _strike_cells(
                        pos,
                        gf,
                        wn,
                        open_tile,
                        self._width,
                        self._height,
                    )
                ),
            )
        return best

    def _worth_picking_weapon_upgrade(self, held: str, loot: str) -> bool:
        """Sensowna zmiana broni: +obrażenia i/lub +obszar ciosu (próg histerezy)."""
        if _same_weapon_kind(held, loot):
            return False
        dh = _weapon_cut_damage(held)
        dl = _weapon_cut_damage(loot)
        sh = self._weapon_max_strike_cell_count(held)
        sl = self._weapon_max_strike_cell_count(loot)
        dmg_ok = dl >= dh + WEAPON_SWITCH_MIN_DAMAGE_DELTA
        strike_ok = sl >= sh + WEAPON_SWITCH_MIN_STRIKE_DELTA
        return dmg_ok or strike_ok

    def _worth_seeking_vision_weapon(self, held: str, loot: str) -> bool:
        """Stagnacja / droga po miksturę: walka wyraźnie lepsza albo dużo lepsze widzenie."""
        if _same_weapon_kind(held, loot):
            return False
        if self._worth_picking_weapon_upgrade(held, loot):
            return True
        vh = _weapon_vision_score(held)
        vl = _weapon_vision_score(loot)
        return vl >= vh + WEAPON_VISION_MIN_DELTA

    def _visible_vision_weapon_loot_goals(
        self, knowledge: characters.ChampionKnowledge
    ) -> set[coordinates.Coords]:
        """Łuk / miecz / amulet na ziemi — tylko gdy podniesienie ma sens (nie ten sam typ, próg)."""
        goals: set[coordinates.Coords] = set()
        if self._weapon_seek_suppressed:
            return goals
        held = self._held_weapon_name(knowledge)
        if held is None:
            return goals
        for coords, desc in knowledge.visible_tiles.items():
            if desc.loot is None or desc.character is not None:
                continue
            base = _weapon_base(desc.loot.name)
            if base not in ("bow", "sword", "amulet"):
                continue
            if not self._worth_seeking_vision_weapon(held, desc.loot.name):
                continue
            x, y = _xy_pair(coords)
            goals.add(coordinates.Coords(x, y))
        return goals

    def _stagnation_break_action(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
        locked: bool,
        banned: set[characters.Action],
    ) -> tuple[characters.Action, Optional[coordinates.Coords]]:
        candidates: list[tuple[characters.Action, Optional[coordinates.Coords]]] = []
        for d in _CARDINAL:
            n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
            if not _passable_for_astar(
                n.x, n.y, self._width, self._height, self._terrain, self._enemy_cells
            ):
                continue
            candidates.append(
                (
                    _exploration_forward_step_action(facing, pos, n, locked),
                    n,
                )
            )
        candidates.append((characters.Action.TURN_LEFT, None))
        candidates.append((characters.Action.TURN_RIGHT, None))
        peek = self._maybe_peek(knowledge, facing)
        if peek is not None:
            candidates.append((peek, None))
        for act, nxt in candidates:
            if act not in banned:
                return act, nxt
        if candidates:
            return candidates[0]
        return characters.Action.TURN_LEFT, None

    def _combined_enemy_threat(self) -> set[coordinates.Coords]:
        out: set[coordinates.Coords] = set()
        for epos, (ef, wn) in self._enemy_info.items():
            out |= _strike_cells(
                epos,
                ef,
                wn,
                self._tile_kind,
                self._width,
                self._height,
            )
        return out

    def _can_immediate_attack(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
    ) -> bool:
        if self._should_attack(knowledge, facing):
            return True
        if (
            self._action_face_orthogonal_foe_then_strike(pos, facing)
            == characters.Action.ATTACK
        ):
            return True
        if self._holding_bow_needing_reload_before_shot(knowledge):
            return True
        ra = self._try_ranged_face_and_attack(knowledge, pos, facing)
        return ra == characters.Action.ATTACK

    def _took_damage_this_tick(
        self, knowledge: characters.ChampionKnowledge
    ) -> bool:
        here = _tile_at_position(knowledge)
        if (
            here is None
            or here.character is None
            or self._hp_last is None
        ):
            return False
        return here.character.health < self._hp_last

    def _luxury_exploration_ok(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
    ) -> bool:
        if self._took_damage_this_tick(knowledge):
            return False
        if pos in self._combined_enemy_threat():
            return False
        if self._can_immediate_attack(knowledge, pos, facing):
            return False
        return True

    def _try_step_into_next_turn_kill(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
        locked: bool,
    ) -> tuple[Optional[characters.Action], Optional[coordinates.Coords]]:
        if not self._enemy_cells:
            return None, None
        here = _tile_at_position(knowledge)
        if here is None or here.character is None:
            return None, None
        my_wn = here.character.weapon.name
        for d in _CARDINAL:
            n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
            if not _passable_for_astar(
                n.x,
                n.y,
                self._width,
                self._height,
                self._terrain,
                self._enemy_cells,
            ):
                continue
            can_hit = False
            for gf in _ALL_FACINGS:
                strikes = _strike_cells(
                    n,
                    gf,
                    my_wn,
                    self._tile_kind,
                    self._width,
                    self._height,
                )
                if self._enemy_cells & strikes:
                    can_hit = True
                    break
            if can_hit:
                act = _exploration_forward_step_action(facing, pos, n, locked)
                return act, n
        return None, None

    def _nearest_enemy(self) -> Optional[coordinates.Coords]:
        if not self._enemy_cells:
            return None
        return min(self._enemy_cells, key=lambda p: (p.x, p.y))

    def _best_escape_step_outside_threat(
        self,
        pos: coordinates.Coords,
        facing: characters.Facing,
        locked: bool,
        threat: set[coordinates.Coords],
        menhir_ring: bool,
    ) -> tuple[Optional[characters.Action], Optional[coordinates.Coords]]:
        ne = self._nearest_enemy()
        safe: list[tuple[coordinates.Coords, int]] = []
        for d in _CARDINAL:
            n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
            if not _passable_for_astar(
                n.x,
                n.y,
                self._width,
                self._height,
                self._terrain,
                self._enemy_cells,
            ):
                continue
            if n in threat:
                continue
            dist = 0 if ne is None else abs(n.x - ne.x) + abs(n.y - ne.y)
            safe.append((n, dist))
        if safe:
            n_best = max(safe, key=lambda t: t[1])[0]
            return (
                _exploration_forward_step_action(facing, pos, n_best, locked),
                n_best,
            )
        if menhir_ring:
            return None, None
        fallback: list[tuple[coordinates.Coords, tuple[int, int]]] = []
        for d in _CARDINAL:
            n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
            if not _passable_for_astar(
                n.x,
                n.y,
                self._width,
                self._height,
                self._terrain,
                self._enemy_cells,
            ):
                continue
            bad = 1 if n in threat else 0
            dist = 0 if ne is None else abs(n.x - ne.x) + abs(n.y - ne.y)
            fallback.append((n, (bad, -dist)))
        if not fallback:
            return None, None
        n_best = min(fallback, key=lambda t: t[1])[0]
        return (
            _exploration_forward_step_action(facing, pos, n_best, locked),
            n_best,
        )

    def _enemy_danger_response(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
        locked: bool,
    ) -> tuple[Optional[characters.Action], Optional[coordinates.Coords]]:
        threat = self._combined_enemy_threat()
        if pos not in threat:
            return None, None
        sk, sn = self._try_step_into_next_turn_kill(
            knowledge, pos, facing, locked
        )
        if sk is not None:
            return sk, sn
        ring = self._menhir_spin_free_zone(pos)
        bk, bn = self._best_escape_step_outside_threat(
            pos, facing, locked, threat, ring
        )
        if bk is not None:
            return bk, bn
        return None, None

    def _life_pickup_goals_within(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
    ) -> set[coordinates.Coords]:
        goals: set[coordinates.Coords] = set()
        for coords, desc in knowledge.visible_tiles.items():
            cx, cy = _xy_pair(coords)
            c = coordinates.Coords(cx, cy)
            if (
                abs(c.x - pos.x) + abs(c.y - pos.y)
                > LIFE_PICKUP_MAX_MANHATTAN
            ):
                continue
            if desc.consumable is not None:
                goals.add(c)
            if desc.loot is not None and desc.character is None:
                lb = _weapon_base(desc.loot.name.lower())
                if lb in _LOOT_WEAPON_BASES:
                    if self._weapon_seek_suppressed:
                        continue
                    held = self._held_weapon_name(knowledge)
                    if held is None or not self._worth_seeking_vision_weapon(
                        held, desc.loot.name
                    ):
                        continue
                goals.add(c)
        return goals

    def _turn_toward_nearest_enemy(
        self, pos: coordinates.Coords, facing: characters.Facing
    ) -> Optional[characters.Action]:
        ne = self._nearest_enemy()
        if ne is None:
            return None
        adx, ady = ne.x - pos.x, ne.y - pos.y
        if adx == 0 and ady == 0:
            return None
        if abs(adx) >= abs(ady):
            gx = 1 if adx > 0 else (-1 if adx < 0 else 0)
            goal = (
                coordinates.Coords(gx, 0)
                if gx != 0
                else coordinates.Coords(0, 1 if ady > 0 else -1)
            )
        else:
            goal = coordinates.Coords(0, 1 if ady > 0 else -1)
        return _single_turn_toward_world_delta(facing, goal)

    def _path_first_step_action(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
        locked: bool,
        goals: set[coordinates.Coords],
    ) -> tuple[Optional[characters.Action], Optional[coordinates.Coords]]:
        path = _multi_goal_astar(
            pos,
            goals,
            self._width,
            self._height,
            self._terrain,
            self._enemy_cells,
        )
        if path is None or len(path) < 2:
            return None, None
        nxt = self._steering_nxt(pos, path[1])
        gaze = self._gaze_frontier_before_known_step(pos, facing, nxt)
        if gaze is not None:
            return gaze, nxt
        peek = (
            None
            if _facing_matches_move_delta(facing, pos, nxt)
            else self._maybe_peek(knowledge, facing)
        )
        if peek is not None:
            return peek, nxt
        return _exploration_forward_step_action(facing, pos, nxt, locked), nxt

    def _return(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
        action: characters.Action,
        nxt: Optional[coordinates.Coords] = None,
    ) -> characters.Action:
        here = _tile_at_position(knowledge)
        if here is not None and here.character is not None:
            self._hp_last = here.character.health
        out = self._finalize_action(pos, facing, action, nxt)
        self._stagnation_prev_known = self._known_cells_count_this_tick
        return out

    def _track_hp_and_maybe_flee(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
    ) -> Optional[characters.Action]:
        here = _tile_at_position(knowledge)
        if here is None or here.character is None:
            return None
        hp = here.character.health
        if (
            self._hp_last is not None
            and hp < self._hp_last
            and not self._enemy_cells
        ):
            step = self._any_passable_step_action(facing, pos)
            if step is not None:
                return step
        return None

    def _weapon_favors_ranged_priority(self, weapon_name: str) -> bool:
        return _weapon_base(weapon_name.lower()) in ("bow", "sword", "amulet")

    def _holding_bow_needing_reload_before_shot(
        self, knowledge: characters.ChampionKnowledge
    ) -> bool:
        """Tylko gdy silnik mówi bow_unloaded — wtedy blokujemy luksus (przeładunek/ucieczka)."""
        if not self._enemy_cells:
            return False
        here = _tile_at_position(knowledge)
        if here is None or here.character is None:
            return False
        wn = here.character.weapon.name
        if _weapon_base(wn.lower()) != "bow":
            return False
        return _bow_loaded_from_weapon_name(wn) is False

    def _try_bow_reload_before_ranged(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
        locked: bool,
    ) -> Optional[characters.Action]:
        """
        Wyłącznie bow_unloaded: najpierw wyjście spod ciosu wroga, potem ATTACK na sucho.
        Przy nieznanym stanie (None) — pierwszy ATTACK z _try_ranged rozstrzyga.
        """
        if not self._enemy_cells:
            return None
        here = _tile_at_position(knowledge)
        if here is None or here.character is None:
            return None
        wn = here.character.weapon.name
        if _weapon_base(wn.lower()) != "bow":
            return None
        if _bow_loaded_from_weapon_name(wn) is not False:
            return None
        threat = self._combined_enemy_threat()
        ring = self._menhir_spin_free_zone(pos)
        if pos in threat:
            act, _ = self._best_escape_step_outside_threat(
                pos, facing, locked, threat, ring
            )
            if act is not None:
                return act
            return characters.Action.ATTACK
        return characters.Action.ATTACK

    def _try_ranged_face_and_attack(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
    ) -> Optional[characters.Action]:
        if not self._enemy_cells:
            return None
        here = _tile_at_position(knowledge)
        if here is None or here.character is None:
            return None
        wn = here.character.weapon.name
        if not self._weapon_favors_ranged_priority(wn):
            return None
        base = _weapon_base(wn.lower())
        if base == "bow" and _bow_loaded_from_weapon_name(wn) is False:
            return None
        if base == "amulet":
            return (
                characters.Action.ATTACK
                if self._should_attack(knowledge, facing)
                else None
            )
        reach = 50 if base == "bow" else 3
        sorted_enemies = sorted(
            self._enemy_cells, key=lambda e: (abs(e.x - pos.x) + abs(e.y - pos.y), e.x, e.y)
        )
        best_key: Optional[tuple[int, int, int, int, int]] = None
        best_action: Optional[characters.Action] = None
        for e in sorted_enemies:
            md = abs(e.x - pos.x) + abs(e.y - pos.y)
            for fi, goal_f in enumerate(_ALL_FACINGS):
                step = goal_f.value
                if not _clear_line_to_enemy(
                    pos,
                    e,
                    step,
                    reach,
                    self._width,
                    self._height,
                    self._tile_kind,
                ):
                    continue
                if facing == goal_f:
                    key = (0, -md, -e.x, -e.y, -fi)
                elif facing.turn_left() == goal_f:
                    key = (1, -md, -e.x, -e.y, -fi)
                elif facing.turn_right() == goal_f:
                    key = (1, -md, -e.x, -e.y, -fi)
                else:
                    key = (2, -md, -e.x, -e.y, -fi)
                act = (
                    characters.Action.ATTACK
                    if facing == goal_f
                    else (
                        characters.Action.TURN_LEFT
                        if facing.turn_left() == goal_f
                        else (
                            characters.Action.TURN_RIGHT
                            if facing.turn_right() == goal_f
                            else _turn_one_step_toward_facing(facing, goal_f)
                        )
                    )
                )
                if best_key is None or key > best_key:
                    best_key = key
                    best_action = act
        return best_action

    def _menhir_vigil_action(
        self,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
        facing: characters.Facing,
        locked: bool,
        _luxury: bool,
    ) -> characters.Action:
        """Na menhirze: obrót (immunitet). Obok: wejście na menhir lub czekanie blisko poza ciosami."""
        if self._standing_on_menhir(knowledge, pos):
            return characters.Action.TURN_LEFT
        m = self._menhir_position
        if m is None:
            return characters.Action.TURN_LEFT
        threat = self._combined_enemy_threat()
        if self._enemy_cells and pos in threat:
            tw = self._turn_toward_nearest_enemy(pos, facing)
            if tw is not None:
                return tw
            ne = self._nearest_enemy()
            if ne is not None:
                best_n: Optional[coordinates.Coords] = None
                best_md = 10**9
                for d in _CARDINAL:
                    n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
                    if not _passable_for_astar(
                        n.x,
                        n.y,
                        self._width,
                        self._height,
                        self._terrain,
                        self._enemy_cells,
                    ):
                        continue
                    md = abs(n.x - ne.x) + abs(n.y - ne.y)
                    if md < best_md:
                        best_md = md
                        best_n = n
                if best_n is not None:
                    return _exploration_forward_step_action(
                        facing, pos, best_n, locked
                    )
        if (
            m not in self._enemy_cells
            and _passable_for_astar(
                m.x,
                m.y,
                self._width,
                self._height,
                self._terrain,
                self._enemy_cells,
            )
        ):
            if pos != m:
                path = _multi_goal_astar(
                    pos,
                    {m},
                    self._width,
                    self._height,
                    self._terrain,
                    self._enemy_cells,
                )
                if path is not None and len(path) >= 2:
                    nxt = self._steering_nxt(pos, path[1])
                    return _exploration_forward_step_action(
                        facing, pos, nxt, locked
                    )
        wait = self._best_menhir_wait_cell(pos)
        if wait is not None and wait != pos:
            path = _multi_goal_astar(
                pos,
                {wait},
                self._width,
                self._height,
                self._terrain,
                self._enemy_cells,
            )
            if path is not None and len(path) >= 2:
                nxt = self._steering_nxt(pos, path[1])
                return _exploration_forward_step_action(
                    facing, pos, nxt, locked
                )
        if pos in threat:
            act, _ = self._best_escape_step_outside_threat(
                pos,
                facing,
                locked,
                threat,
                self._menhir_spin_free_zone(pos),
            )
            if act is not None:
                return act
        alt = self._any_passable_step_action(facing, pos)
        if alt is not None:
            return alt
        return characters.Action.TURN_LEFT

    def _update_spin_tracker(self, pos: coordinates.Coords, facing: characters.Facing) -> None:
        key = (pos.x, pos.y)
        if self._spin_pos != key:
            self._spin_pos = key
            self._anchor_facing = facing
            self._ever_deviated_from_anchor = False
        elif facing != self._anchor_facing:
            self._ever_deviated_from_anchor = True

    def _spin_lock(
        self,
        facing: characters.Facing,
        knowledge: characters.ChampionKnowledge,
        pos: coordinates.Coords,
    ) -> bool:
        if self._menhir_spin_free_zone(pos) or self._standing_on_menhir(
            knowledge, pos
        ):
            return False
        return self._ever_deviated_from_anchor and facing == self._anchor_facing

    def _should_attack(
        self,
        knowledge: characters.ChampionKnowledge,
        facing: characters.Facing,
    ) -> bool:
        here = _tile_at_position(knowledge)
        if here is None or here.character is None:
            return False
        weapon_name = here.character.weapon.name
        strikes = _strike_cells(
            knowledge.position,
            facing,
            weapon_name,
            self._tile_kind,
            self._width,
            self._height,
        )
        return bool(self._enemy_cells & strikes)

    def _wants_floor_sword_axe(self, knowledge: characters.ChampionKnowledge) -> bool:
        return bool(self._visible_sword_axe_loot_goals(knowledge))

    def _visible_sword_axe_loot_goals(self, knowledge: characters.ChampionKnowledge) -> set[coordinates.Coords]:
        goals: set[coordinates.Coords] = set()
        if self._weapon_seek_suppressed:
            return goals
        held = self._held_weapon_name(knowledge)
        if held is None:
            return goals
        for coords, desc in knowledge.visible_tiles.items():
            if desc.loot is None or desc.character is not None:
                continue
            base = _weapon_base(desc.loot.name)
            if base not in ("sword", "axe"):
                continue
            if not self._worth_picking_weapon_upgrade(held, desc.loot.name):
                continue
            x, y = _xy_pair(coords)
            goals.add(coordinates.Coords(x, y))
        return goals

    def _any_passable_step_action(
        self,
        facing: characters.Facing,
        pos: coordinates.Coords,
    ) -> Optional[characters.Action]:
        for d in _CARDINAL:
            n = coordinates.Coords(pos.x + d.x, pos.y + d.y)
            if _passable_for_astar(
                n.x, n.y, self._width, self._height, self._terrain, self._enemy_cells
            ):
                return _first_step_action(facing, pos, n)
        return None

    def _visible_mist_cells_xy(
        self, knowledge: characters.ChampionKnowledge
    ) -> list[tuple[int, int]]:
        found: list[tuple[int, int]] = []
        for coords, desc in knowledge.visible_tiles.items():
            if any(eff.type == "mist" for eff in desc.effects):
                found.append(_xy_pair(coords))
        return found

    def _mist_escape_ideal(
        self, pos: coordinates.Coords, knowledge: characters.ChampionKnowledge
    ) -> tuple[float, float]:
        """
        Kierunek ucieczki prostopadły do frontu mgły: ku menhirowi (środek zawężającego się koła),
        inaczej od najbliższego widocznego pola mgły (normalna lokalna do łuku frontu).
        Stoimy na mgle: wektor od środka ciężkości widocznej mgły (żeby nie dostać (0,0)).
        """
        mist = self._visible_mist_cells_xy(knowledge)
        if not mist:
            return (0.0, 0.0)
        if self._menhir_position is not None:
            m = self._menhir_position
            dx, dy = float(m.x - pos.x), float(m.y - pos.y)
            if dx != 0.0 or dy != 0.0:
                return (dx, dy)
        px, py = pos.x, pos.y
        best_mx, best_my = mist[0]
        best_d2 = (best_mx - px) ** 2 + (best_my - py) ** 2
        for mx, my in mist[1:]:
            d2 = (mx - px) ** 2 + (my - py) ** 2
            if d2 < best_d2:
                best_d2 = d2
                best_mx, best_my = mx, my
        if best_d2 == 0:
            cx = sum(t[0] for t in mist) / len(mist)
            cy = sum(t[1] for t in mist) / len(mist)
            return (float(px - cx), float(py - cy))
        return (float(px - best_mx), float(py - best_my))

    def _mist_flee_goal_cells(
        self,
        pos: coordinates.Coords,
        nx: float,
        ny: float,
        relax_half_plane: bool,
    ) -> set[coordinates.Coords]:
        ax = int(round(pos.x + nx * MIST_FLEE_GOAL_LEAD))
        ay = int(round(pos.y + ny * MIST_FLEE_GOAL_LEAD))
        ax = max(0, min(self._width - 1, ax))
        ay = max(0, min(self._height - 1, ay))
        r = MIST_FLEE_GOAL_CHEB_RADIUS + (2 if relax_half_plane else 0)
        thr = -1e18
        if self._mist_dot_floor is not None:
            thr = self._mist_dot_floor + (
                -0.75 if relax_half_plane else MIST_FLEE_HALF_PLANE_EPS
            )
        goals: set[coordinates.Coords] = set()
        for x in range(max(0, ax - r), min(self._width, ax + r + 1)):
            for y in range(max(0, ay - r), min(self._height, ay + r + 1)):
                if nx * (x - pos.x) + ny * (y - pos.y) < thr:
                    continue
                if _passable_for_astar(
                    x,
                    y,
                    self._width,
                    self._height,
                    self._terrain,
                    self._enemy_cells,
                ):
                    goals.add(coordinates.Coords(x, y))
        return goals

    def _try_mist_flee(
        self,
        pos: coordinates.Coords,
        facing: characters.Facing,
        knowledge: characters.ChampionKnowledge,
        locked: bool,
    ) -> tuple[Optional[characters.Action], Optional[coordinates.Coords]]:
        if self._menhir_spin_free_zone(pos):
            self._mist_dot_floor = None
            return None, None
        mist_xy = self._visible_mist_cells_xy(knowledge)
        if not mist_xy:
            self._mist_dot_floor = None
            return None, None

        if self._menhir_position is not None:
            self._mist_dot_floor = None
            m = self._menhir_position
            goals = self._menhir_ring_passable_goals()
            if not goals and _passable_for_astar(
                m.x,
                m.y,
                self._width,
                self._height,
                self._terrain,
                self._enemy_cells,
            ):
                goals = {m}
            if goals:
                pa, pn = self._path_first_step_action(
                    knowledge, pos, facing, locked, goals
                )
                if pa is not None:
                    return pa, pn
            ix, iy = float(m.x - pos.x), float(m.y - pos.y)
            if ix == 0.0 and iy == 0.0:
                return None, None
            for d in _cardinals_by_alignment(ix, iy):
                nxt = coordinates.Coords(pos.x + d.x, pos.y + d.y)
                if not self._neighbor_ok_for_step(pos, nxt):
                    continue
                act = _exploration_forward_step_action(facing, pos, nxt, locked)
                return act, nxt
            return None, None

        ix, iy = self._mist_escape_ideal(pos, knowledge)
        if ix == 0.0 and iy == 0.0:
            return None, None
        l = math.hypot(ix, iy)
        if l < 1e-9:
            return None, None
        nx, ny = ix / l, iy / l
        projections = [
            nx * (mx - pos.x) + ny * (my - pos.y) for mx, my in mist_xy
        ]
        loc_floor = max(projections)
        if self._mist_dot_floor is None:
            self._mist_dot_floor = loc_floor
        else:
            self._mist_dot_floor = max(self._mist_dot_floor, loc_floor)

        for relax in (False, True):
            goals = self._mist_flee_goal_cells(pos, nx, ny, relax)
            if not goals:
                continue
            pa, pn = self._path_first_step_action(
                knowledge, pos, facing, locked, goals
            )
            if pa is not None:
                return pa, pn

        for d in _cardinals_by_alignment(ix, iy):
            nxt = coordinates.Coords(pos.x + d.x, pos.y + d.y)
            if not self._neighbor_ok_for_step(pos, nxt):
                continue
            act = _exploration_forward_step_action(facing, pos, nxt, locked)
            return act, nxt
        return None, None

    def _maybe_peek(self, knowledge: characters.ChampionKnowledge, facing: characters.Facing) -> Optional[characters.Action]:
        return _action_peek_blind_adjacent_unknown(
            knowledge, facing, self._width, self._height, self._terrain
        )

    def _gaze_frontier_before_known_step(
        self,
        pos: coordinates.Coords,
        facing: characters.Facing,
        path_next: coordinates.Coords,
    ) -> Optional[characters.Action]:
        if _facing_matches_move_delta(facing, pos, path_next):
            return None
        if not _is_frontier_coord(pos, self._width, self._height, self._terrain):
            return None
        nxt_known = self._terrain[path_next.x][path_next.y] is not None
        if not nxt_known:
            return None
        return _action_face_adjacent_unknown_for_frontier(
            pos, facing, self._width, self._height, self._terrain
        )

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self._merge_visible(knowledge)
        self._update_weapon_seek_state(knowledge)
        pos = knowledge.position
        facing = self._facing_from_knowledge(knowledge)

        if self._standing_on_menhir(knowledge, pos):
            return self._return(
                knowledge, pos, facing, characters.Action.TURN_LEFT, None
            )

        known_now = self._count_known_cells()
        if known_now > self._stagnation_prev_known:
            self._moves_without_new_map = 0
        elif not self._menhir_final_phase(knowledge, pos):
            self._moves_without_new_map += 1
        self._known_cells_count_this_tick = known_now

        hp_flee = self._track_hp_and_maybe_flee(knowledge, pos, facing)
        if hp_flee is not None:
            return self._return(knowledge, pos, facing, hp_flee, None)

        if self._no_progress_since_last_action(pos, facing):
            unstick = self._break_idle_after_blocked(knowledge, pos, facing)
            return self._return(knowledge, pos, facing, unstick, None)

        self._update_spin_tracker(pos, facing)
        locked = self._spin_lock(facing, knowledge, pos)

        bow_reload = self._try_bow_reload_before_ranged(
            knowledge, pos, facing, locked
        )
        if bow_reload is not None:
            return self._return(knowledge, pos, facing, bow_reload, None)

        rng = self._try_ranged_face_and_attack(knowledge, pos, facing)
        if rng is not None:
            return self._return(knowledge, pos, facing, rng, None)

        melee_adj = self._action_face_orthogonal_foe_then_strike(pos, facing)
        if melee_adj is not None:
            return self._return(knowledge, pos, facing, melee_adj, None)

        if self._should_attack(knowledge, facing):
            return self._return(
                knowledge, pos, facing, characters.Action.ATTACK, None
            )

        mist_act, mist_nxt = self._try_mist_flee(pos, facing, knowledge, locked)
        if mist_act is not None:
            return self._return(knowledge, pos, facing, mist_act, mist_nxt)

        if locked:
            step = self._any_passable_step_action(facing, pos)
            if step is not None:
                return self._return(knowledge, pos, facing, step, None)
            return self._return(
                knowledge, pos, facing, characters.Action.STEP_FORWARD, None
            )

        da, dn = self._enemy_danger_response(knowledge, pos, facing, locked)
        if da is not None:
            return self._return(knowledge, pos, facing, da, dn)

        life_goals = self._life_pickup_goals_within(knowledge, pos)
        if life_goals:
            pa, pn = self._path_first_step_action(
                knowledge, pos, facing, locked, life_goals
            )
            if pa is not None:
                return self._return(knowledge, pos, facing, pa, pn)

        luxury = self._luxury_exploration_ok(knowledge, pos, facing)

        if luxury and (
            not self._menhir_final_phase(knowledge, pos)
            and self._moves_without_new_map >= STAGNATION_VISION_LOOT_MOVES
        ):
            vgoals = self._visible_vision_weapon_loot_goals(knowledge)
            if vgoals:
                va, vn = self._path_first_step_action(
                    knowledge, pos, facing, locked, vgoals
                )
                if va is not None:
                    return self._return(knowledge, pos, facing, va, vn)

        if luxury and (
            not self._menhir_final_phase(knowledge, pos)
            and self._moves_without_new_map >= STAGNATION_NO_NEW_MAP_MOVES
        ):
            br, bnxt = self._stagnation_break_action(
                knowledge,
                pos,
                facing,
                locked,
                set(self._last_actions),
            )
            return self._return(knowledge, pos, facing, br, bnxt)

        if luxury and self._wants_floor_sword_axe(knowledge):
            loot_goals = self._visible_sword_axe_loot_goals(knowledge)
            if loot_goals:
                la, ln = self._path_first_step_action(
                    knowledge, pos, facing, locked, loot_goals
                )
                if la is not None:
                    return self._return(knowledge, pos, facing, la, ln)

        goals: Optional[set[coordinates.Coords]] = None
        if self._menhir_position is not None:
            in_near = self._menhir_spin_free_zone(pos) or self._standing_on_menhir(
                knowledge, pos
            )
            if in_near:
                return self._return(
                    knowledge,
                    pos,
                    facing,
                    self._menhir_vigil_action(
                        knowledge, pos, facing, locked, luxury
                    ),
                    None,
                )
            goals = self._menhir_approach_goal_set(pos)
        elif luxury:
            frontier = _frontier_goals(self._width, self._height, self._terrain)
            if not frontier:
                return self._return(
                    knowledge, pos, facing, characters.Action.TURN_LEFT, None
                )
            if pos in frontier:
                step_into = _unknown_neighbor(
                    pos, self._width, self._height, self._terrain
                )
                if step_into is not None:
                    nxt = self._steering_nxt(pos, step_into)
                    peek = (
                        None
                        if _facing_matches_move_delta(facing, pos, nxt)
                        else self._maybe_peek(knowledge, facing)
                    )
                    if peek is not None:
                        return self._return(knowledge, pos, facing, peek, nxt)
                    act = _exploration_forward_step_action(
                        facing, pos, nxt, locked
                    )
                    return self._return(knowledge, pos, facing, act, nxt)
            goals = frontier

        if goals is None:
            tw = self._turn_toward_nearest_enemy(pos, facing)
            if tw is not None:
                return self._return(knowledge, pos, facing, tw, None)
            return self._return(
                knowledge, pos, facing, characters.Action.TURN_LEFT, None
            )

        path = _multi_goal_astar(
            pos, goals, self._width, self._height, self._terrain, self._enemy_cells
        )
        if path is None or len(path) < 2:
            tw = self._turn_toward_nearest_enemy(pos, facing)
            if tw is not None:
                return self._return(knowledge, pos, facing, tw, None)
            return self._return(
                knowledge, pos, facing, characters.Action.TURN_LEFT, None
            )

        nxt = self._steering_nxt(pos, path[1])
        gaze = self._gaze_frontier_before_known_step(pos, facing, nxt)
        if gaze is not None:
            return self._return(knowledge, pos, facing, gaze, nxt)

        peek = (
            None
            if _facing_matches_move_delta(facing, pos, nxt)
            else self._maybe_peek(knowledge, facing)
        )
        if peek is not None:
            return self._return(knowledge, pos, facing, peek, nxt)

        act = _exploration_forward_step_action(facing, pos, nxt, locked)
        return self._return(knowledge, pos, facing, act, nxt)

    def _facing_from_knowledge(self, knowledge: characters.ChampionKnowledge) -> characters.Facing:
        here = _tile_at_position(knowledge)
        if here is not None and here.character is not None:
            return here.character.facing
        return characters.Facing.UP

    def _merge_visible(self, knowledge: characters.ChampionKnowledge) -> None:
        self._enemy_cells = set()
        self._enemy_info.clear()
        for coords, desc in knowledge.visible_tiles.items():
            x, y = _xy_pair(coords)
            self._terrain[x][y] = _terrain_walkable_from_type(desc.type)
            self._tile_kind[x][y] = desc.type
            if desc.type == "menhir":
                self._menhir_position = coordinates.Coords(x, y)
            ch = desc.character
            if ch is not None and ch.controller_name != self.name:
                ec = coordinates.Coords(x, y)
                self._enemy_cells.add(ec)
                self._enemy_info[ec] = (ch.facing, ch.weapon.name)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        arena = arenas.Arena.load(arena_description.name)
        self._width, self._height = arena.size
        self._terrain = [
            [None for _ in range(self._height)] for _ in range(self._width)
        ]
        self._tile_kind = [
            [None for _ in range(self._height)] for _ in range(self._width)
        ]
        self._enemy_cells = set()
        self._menhir_position = None
        self._spin_pos = None
        self._anchor_facing = characters.Facing.UP
        self._ever_deviated_from_anchor = False
        self._steer_commit_pos = None
        self._steer_commit_nxt = None
        self._last_action = None
        self._last_act_pos = None
        self._pre_action_pos = None
        self._pre_action_facing = None
        self._hp_last = None
        self._stagnation_prev_known = 0
        self._moves_without_new_map = 0
        self._known_cells_count_this_tick = 0
        self._last_actions.clear()
        self._enemy_info.clear()
        self._mist_dot_floor = None
        self._last_held_weapon_base = None
        self._lifetime_seen_loot_weapon_bases.clear()
        self._weapon_equipped_transitions_into.clear()
        self._weapon_seek_suppressed = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BIGbot):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    @property
    def name(self) -> str:
        return f"BIGbot_{self.bot_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


POTENTIAL_CONTROLLERS = [
    BIGbot("Big Bot"),
]

"""
BIGbot: wewnętrzna mapa = teren (typ pola, bez „kto stoi”) + zbiór wrogów widzianych
w tej klatce (knowledge). Własne coords zawsze z ChampionKnowledge, nie utrwalamy ich na siatce.
A*: przechodniość z terenu + brak wroga na polu (tylko bieżący widok wrogów).
ATTACK tylko gdy wróg jest na polu trafienia bieżącej broni (nie: widzę gdzieś bokiem → pusty przód).
Ruch po ścieżce (bez spin-lock): najpierw obrót w stronę następnego pola, potem STEP_FORWARD — stożek widzenia jak w kierunku eksploracji.
Spin-lock: na danym polu zapamiętujemy facing „wejścia”; jeśli od niego odbiegliśmy obrotem i wrócimy do tego samego facing → tylko STEP_* (koniec kręcenia).
Peek/gaze nie wykonujemy, gdy już patrzymy w stronę następnego kroku A* (unik oscylacji L/R z _exploration_forward_step_action).
Stabilizacja: ten sam sąsiad docelowy na polu dopóki jest sensowny (remisy A*); blokada TURN_LEFT zaraz po TURN_RIGHT (i odwrotnie) na tym samym polu → krok boczny / STEP zamiast kolejnego obrotu.
Na menhirze: bez spin-locka (można kręcić się bez limitu). Wróg na sąsiednim polu ortogonalnym → obrót w jego stronę, potem cios.
Jeśli ostatnia akcja nie zmieniła pozycji ani facing (np. zablokowany krok) → inna akcja / obrót (unik kary idle).
"""

from __future__ import annotations

import heapq
import math
from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles

# Teren: None = nie widziane, True = przechodni typ (land/forest/menhir), False = ściana/morze
TerrainWalkable = Optional[bool]
# Znany typ pola (dla promieni miecza/łuku)
TileKind = Optional[str]

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

    def _standing_on_menhir(
        self, knowledge: characters.ChampionKnowledge, pos: coordinates.Coords
    ) -> bool:
        if self._menhir_position is not None and pos == self._menhir_position:
            return True
        here = _tile_at_position(knowledge)
        return here is not None and here.type == "menhir"

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
        return action

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
        if self._standing_on_menhir(knowledge, pos):
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
        here = _tile_at_position(knowledge)
        if here is None or here.character is None:
            return False
        wn = _weapon_base(here.character.weapon.name.lower())
        return wn not in ("sword", "axe")

    def _visible_sword_axe_loot_goals(self, knowledge: characters.ChampionKnowledge) -> set[coordinates.Coords]:
        goals: set[coordinates.Coords] = set()
        for coords, desc in knowledge.visible_tiles.items():
            if desc.loot is None or desc.character is not None:
                continue
            base = _weapon_base(desc.loot.name)
            if base in ("sword", "axe"):
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
        pos = knowledge.position
        facing = self._facing_from_knowledge(knowledge)

        if self._no_progress_since_last_action(pos, facing):
            unstick = self._break_idle_after_blocked(knowledge, pos, facing)
            return self._finalize_action(pos, facing, unstick, None)

        self._update_spin_tracker(pos, facing)
        locked = self._spin_lock(facing, knowledge, pos)

        melee_adj = self._action_face_orthogonal_foe_then_strike(pos, facing)
        if melee_adj is not None:
            return self._finalize_action(pos, facing, melee_adj, None)

        if self._should_attack(knowledge, facing):
            return self._finalize_action(pos, facing, characters.Action.ATTACK, None)

        if locked:
            step = self._any_passable_step_action(facing, pos)
            if step is not None:
                return self._finalize_action(pos, facing, step, None)
            return self._finalize_action(
                pos, facing, characters.Action.STEP_FORWARD, None
            )

        if self._wants_floor_sword_axe(knowledge):
            loot_goals = self._visible_sword_axe_loot_goals(knowledge)
            if loot_goals:
                loot_path = _multi_goal_astar(
                    pos,
                    loot_goals,
                    self._width,
                    self._height,
                    self._terrain,
                    self._enemy_cells,
                )
                if loot_path is not None and len(loot_path) >= 2:
                    nxt = self._steering_nxt(pos, loot_path[1])
                    gaze = self._gaze_frontier_before_known_step(pos, facing, nxt)
                    if gaze is not None:
                        return self._finalize_action(pos, facing, gaze, nxt)
                    peek = (
                        None
                        if _facing_matches_move_delta(facing, pos, nxt)
                        else self._maybe_peek(knowledge, facing)
                    )
                    if peek is not None:
                        return self._finalize_action(pos, facing, peek, nxt)
                    act = _exploration_forward_step_action(
                        facing, pos, nxt, locked
                    )
                    return self._finalize_action(pos, facing, act, nxt)

        if self._menhir_position is not None:
            goals = {self._menhir_position}
        else:
            frontier = _frontier_goals(self._width, self._height, self._terrain)
            if not frontier:
                return self._finalize_action(
                    pos, facing, characters.Action.TURN_LEFT, None
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
                        return self._finalize_action(pos, facing, peek, nxt)
                    act = _exploration_forward_step_action(
                        facing, pos, nxt, locked
                    )
                    return self._finalize_action(pos, facing, act, nxt)
            goals = frontier

        path = _multi_goal_astar(
            pos, goals, self._width, self._height, self._terrain, self._enemy_cells
        )
        if path is None or len(path) < 2:
            return self._finalize_action(
                pos, facing, characters.Action.TURN_LEFT, None
            )

        nxt = self._steering_nxt(pos, path[1])
        gaze = self._gaze_frontier_before_known_step(pos, facing, nxt)
        if gaze is not None:
            return self._finalize_action(pos, facing, gaze, nxt)

        peek = (
            None
            if _facing_matches_move_delta(facing, pos, nxt)
            else self._maybe_peek(knowledge, facing)
        )
        if peek is not None:
            return self._finalize_action(pos, facing, peek, nxt)

        act = _exploration_forward_step_action(facing, pos, nxt, locked)
        return self._finalize_action(pos, facing, act, nxt)

    def _facing_from_knowledge(self, knowledge: characters.ChampionKnowledge) -> characters.Facing:
        here = _tile_at_position(knowledge)
        if here is not None and here.character is not None:
            return here.character.facing
        return characters.Facing.UP

    def _merge_visible(self, knowledge: characters.ChampionKnowledge) -> None:
        self._enemy_cells = set()
        for coords, desc in knowledge.visible_tiles.items():
            x, y = _xy_pair(coords)
            self._terrain[x][y] = _terrain_walkable_from_type(desc.type)
            self._tile_kind[x][y] = desc.type
            if desc.type == "menhir":
                self._menhir_position = coordinates.Coords(x, y)
            ch = desc.character
            if ch is not None and ch.controller_name != self.name:
                self._enemy_cells.add(coordinates.Coords(x, y))

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
    BIGbot("Stub"),
]

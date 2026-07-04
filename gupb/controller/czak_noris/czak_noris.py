import os
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from gupb import controller
from gupb.controller.czak_noris.qlearn import DoubleQTable
from gupb.model import arenas, characters, coordinates, weapons

Facing = characters.Facing
Action = characters.Action
Coords = coordinates.Coords


WEAPON_PRIORITY = {
    "bow_loaded": 6,
    "bow_unloaded": 5,
    "bow": 5,
    "sword": 5,
    "axe": 4,
    "amulet": 3,
    "scroll": 2,
    "knife": 1,
}

WEAPON_CLASSES = {
    "knife": weapons.Knife,
    "sword": weapons.Sword,
    "bow": weapons.Bow,
    "bow_loaded": weapons.Bow,
    "bow_unloaded": weapons.Bow,
    "axe": weapons.Axe,
    "amulet": weapons.Amulet,
    "scroll": weapons.Scroll,
}

PASSABLE_TYPES = {"land", "forest", "menhir"}
OPAQUE_TYPES = {"wall", "forest"}

MODES = ["hunt", "loot", "explore", "menhir", "flee"]
MODE_PERIOD = 8
ALPHA = 0.1
GAMMA = 0.99
HP_REWARD_SCALE = 0.5
SCROLL_CHARGES = 5

QTABLE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "czak_noris_qtable.pkl"
)

DIRS = (Coords(1, 0), Coords(-1, 0), Coords(0, 1), Coords(0, -1))


def _c(t) -> Coords:
    return Coords(t[0], t[1])


def _add(a, b) -> Coords:
    return Coords(a[0] + b[0], a[1] + b[1])


def _manhattan(a, b) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def _euclid(a, b) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


class _TileView:
    __slots__ = ("transparent",)

    def __init__(self, transparent: bool) -> None:
        self.transparent = transparent


class _TerrainView:
    """Minimalny adapter pamieci mapy pod weapons.Weapon.cut_positions."""

    def __init__(self, types: Dict[Coords, str], occupied: Set[Coords]) -> None:
        self.types = types
        self.occupied = occupied

    def __contains__(self, coords) -> bool:
        return coords in self.types

    def __getitem__(self, coords) -> _TileView:
        return _TileView(
            self.types[coords] not in OPAQUE_TYPES and coords not in self.occupied
        )


class CzakNoris(controller.Controller):
    def __init__(
        self, bot_name: str, is_training: bool = False, use_qtable: bool = False
    ) -> None:
        self.bot_name = bot_name
        self.is_training = is_training
        self.use_qtable = use_qtable
        self.q = DoubleQTable(MODES, alpha=ALPHA, gamma=GAMMA, path=QTABLE_PATH)
        if use_qtable:
            self.q.load()
        self.mode_counts: Dict[str, int] = {m: 0 for m in MODES}
        self._reset_state()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CzakNoris):
            return self.bot_name == other.bot_name
        return False

    def __hash__(self) -> int:
        return hash(self.bot_name)

    def _reset_state(self) -> None:
        self.terrain_types: Dict[Coords, str] = {}
        self.seen: Set[Coords] = set()
        self.loot: Dict[Coords, str] = {}
        self.potions: Set[Coords] = set()
        self.mist_tiles: Set[Coords] = set()
        self.fire_tiles: Set[Coords] = set()
        self.occupied: Set[Coords] = set()
        self.enemies: List[Tuple[Coords, characters.ChampionDescription]] = []
        self.enemy_danger: List[Tuple[Coords, Set[Coords]]] = []
        self.danger: Set[Coords] = set()
        self.menhir: Optional[Coords] = None
        self.arena_size: Optional[Tuple[int, int]] = None
        self.est_mist_radius: Optional[int] = None
        self.mist_counter: int = 0
        self.mist_seen: bool = False
        self.tick: int = 0
        self.my_pos: Optional[Coords] = None
        self.scroll_used: int = 0
        self.explore_target: Optional[Coords] = None
        self.mode: Optional[str] = None
        self.mode_ticks: int = 0
        self.mode_start_hp: int = 0
        self.prev_enemy_count: int = 0
        self.seg_state: Optional[Tuple[int, ...]] = None
        self.seg_mode: Optional[str] = None
        self.seg_reward: float = 0.0
        self.seg_len: int = 0
        self.last_hp: Optional[int] = None

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._reset_state()
        try:
            arena = arenas.Arena.load(arena_description.name)
            self.arena_size = arena.size
            self.est_mist_radius = arena.mist_radius
            for coords, tile in arena.terrain.items():
                ck = _c(coords)
                self.terrain_types[ck] = tile.description().type
                if tile.loot is not None:
                    self.loot[ck] = tile.loot.description().name
        except Exception:
            pass
        if arena_description.name in arenas.FIXED_MENHIRS:
            self.menhir = _c(arenas.FIXED_MENHIRS[arena_description.name])

    def praise(self, score: int) -> None:
        if not self.is_training:
            return
        if self.seg_state is not None and self.seg_mode is not None:
            total = self.seg_reward + (GAMMA ** self.seg_len) * float(score)
            self.q.update(self.seg_state, self.seg_mode, total, self.seg_len, None)
            self.seg_state = None
            self.seg_mode = None
        self.q.games += 1

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            return self._decide(knowledge)
        except Exception:
            return Action.TURN_RIGHT

    def _decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.tick += 1
        self.my_pos = _c(knowledge.position)
        self._observe(knowledge)
        my_tile = knowledge.visible_tiles[knowledge.position]
        my_desc = my_tile.character
        if my_desc is None:
            return Action.TURN_LEFT
        facing = my_desc.facing
        weapon_name = my_desc.weapon.name
        hp = my_desc.health
        my_prio = WEAPON_PRIORITY.get(weapon_name, 1)
        my_pos = self.my_pos

        self._advance_mist(knowledge)
        self._update_danger()

        if self.is_training and self.last_hp is not None and self.seg_state is not None:
            reward = HP_REWARD_SCALE * (hp - self.last_hp)
            self.seg_reward += (GAMMA ** self.seg_len) * reward
            self.seg_len += 1
        self.last_hp = hp

        state = self._state_features(knowledge, hp, weapon_name, my_pos)
        self._maybe_select_mode(state, hp, my_prio)
        self.mode_ticks += 1
        self.prev_enemy_count = len(self.enemies)

        if my_pos in self.fire_tiles:
            step = self._hazard_step(my_pos, facing)
            if step is not None:
                return step

        if self.mode != "flee" and self._can_hit_enemy(my_pos, facing, weapon_name):
            return self._attack(weapon_name)

        if my_pos in self.mist_tiles:
            step = self._hazard_step(my_pos, facing)
            if step is not None:
                return step

        if weapon_name == "bow_unloaded" and not self.enemies:
            return Action.ATTACK

        action = self._run_mode(my_pos, facing, weapon_name, hp, my_prio)
        if action is not None:
            return action
        return Action.TURN_RIGHT

    def _observe(self, knowledge: characters.ChampionKnowledge) -> None:
        self.occupied = set()
        self.enemies = []
        fresh_mist: List[Coords] = []
        for coord, desc in knowledge.visible_tiles.items():
            ck = _c(coord)
            self.seen.add(ck)
            self.terrain_types[ck] = desc.type
            if desc.type == "menhir":
                self.menhir = ck
            if desc.loot is not None:
                self.loot[ck] = desc.loot.name
            else:
                self.loot.pop(ck, None)
            if desc.consumable is not None:
                self.potions.add(ck)
            else:
                self.potions.discard(ck)
            for eff in desc.effects:
                if eff.type == "mist":
                    if ck not in self.mist_tiles:
                        fresh_mist.append(ck)
                    self.mist_tiles.add(ck)
                    self.mist_seen = True
                elif eff.type == "fire":
                    self.fire_tiles.add(ck)
            if desc.character is not None:
                self.occupied.add(ck)
                if (
                    ck != self.my_pos
                    and desc.character.controller_name != self.bot_name
                ):
                    self.enemies.append((ck, desc.character))
        if self.menhir is not None and self.est_mist_radius is not None:
            for ck in fresh_mist:
                observed = int(_euclid(ck, self.menhir))
                if observed < self.est_mist_radius:
                    self.est_mist_radius = observed
        self.view = _TerrainView(self.terrain_types, self.occupied)

    def _advance_mist(self, knowledge: characters.ChampionKnowledge) -> None:
        if self.est_mist_radius is None:
            if self.arena_size is None and self.terrain_types:
                max_x = max(c[0] for c in self.terrain_types)
                max_y = max(c[1] for c in self.terrain_types)
                self.arena_size = (max_x + 1, max_y + 1)
            if self.arena_size is not None:
                self.est_mist_radius = int(self.arena_size[0] * 2 ** 0.5) + 1
            else:
                return
        self.mist_counter += 1
        if self.mist_counter >= 2 * max(knowledge.no_of_champions_alive, 1):
            self.est_mist_radius = max(self.est_mist_radius - 1, 0)
            self.mist_counter = 0

    def _mist_margin(self, pos: Coords) -> float:
        if self.menhir is None or self.est_mist_radius is None:
            return 999.0
        return self.est_mist_radius - _euclid(pos, self.menhir)

    def _update_danger(self) -> None:
        self.enemy_danger = []
        self.danger = set()
        for pos, desc in self.enemies:
            tiles_hit: Set[Coords] = set()
            weapon_cls = WEAPON_CLASSES.get(desc.weapon.name)
            if weapon_cls is not None:
                tiles_hit.update(weapon_cls.cut_positions(self.view, pos, desc.facing))
            for d in DIRS:
                tiles_hit.add(_add(pos, d))
            self.enemy_danger.append((pos, tiles_hit))
            self.danger.update(tiles_hit)

    def _state_features(
        self,
        knowledge: characters.ChampionKnowledge,
        hp: int,
        weapon_name: str,
        my_pos: Coords,
    ) -> Tuple[int, ...]:
        if hp <= 3:
            hp_b = 0
        elif hp <= 6:
            hp_b = 1
        else:
            hp_b = 2

        if weapon_name.startswith("bow"):
            weapon_b = 2
        elif weapon_name in ("sword", "axe", "amulet"):
            weapon_b = 1
        else:
            weapon_b = 0

        threat_b = self._threat_level(hp, weapon_name, my_pos)

        margin = self._mist_margin(my_pos)
        if self.menhir is None:
            mist_b = 0
        elif margin > 10:
            mist_b = 1
        elif margin > 3:
            mist_b = 2
        else:
            mist_b = 3

        my_prio = WEAPON_PRIORITY.get(weapon_name, 1)
        if self.potions:
            loot_b = 2
        elif self._best_upgrade(my_pos, my_prio) is not None:
            loot_b = 1
        else:
            loot_b = 0

        alive = knowledge.no_of_champions_alive
        if alive >= 7:
            alive_b = 0
        elif alive >= 3:
            alive_b = 1
        else:
            alive_b = 2

        return (hp_b, weapon_b, threat_b, mist_b, loot_b, alive_b)

    def _threat_level(self, hp: int, weapon_name: str, my_pos: Coords) -> int:
        if not self.enemies:
            return 0
        my_prio = WEAPON_PRIORITY.get(weapon_name, 1)
        pos, desc = min(self.enemies, key=lambda e: _manhattan(e[0], my_pos))
        if _manhattan(pos, my_pos) > 4:
            return 1
        favored = hp >= desc.health and my_prio >= WEAPON_PRIORITY.get(
            desc.weapon.name, 1
        )
        return 2 if favored else 3

    def _maybe_select_mode(
        self, state: Tuple[int, ...], hp: int, my_prio: int
    ) -> None:
        reselect = (
            self.mode is None
            or self.mode_ticks >= MODE_PERIOD
            or (self.prev_enemy_count == 0 and len(self.enemies) > 0)
            or (self.mode_start_hp - hp >= 2)
            or self._mode_target_done()
        )
        if not reselect:
            return
        if self.is_training and self.seg_state is not None and self.seg_mode is not None:
            self.q.update(
                self.seg_state, self.seg_mode, self.seg_reward, self.seg_len, state
            )
        if self.is_training:
            mode = self.q.select(state)
        elif self.use_qtable:
            mode = self.q.best_mode(state)
            if mode is None:
                mode = self._cascade_mode(hp, my_prio)
        else:
            mode = self._cascade_mode(hp, my_prio)
        self.mode = mode
        self.mode_counts[mode] = self.mode_counts.get(mode, 0) + 1
        self.mode_ticks = 0
        self.mode_start_hp = hp
        self.seg_state = state
        self.seg_mode = mode
        self.seg_reward = 0.0
        self.seg_len = 0

    def _mode_target_done(self) -> bool:
        if self.mode == "hunt" and not self.enemies:
            return True
        if self.mode == "loot" and not self.potions and not self.loot:
            return True
        return False

    def _cascade_mode(self, hp: int, my_prio: int) -> str:
        threat = 0
        if self.my_pos is not None and self.enemies:
            pos, desc = min(
                self.enemies, key=lambda e: _manhattan(e[0], self.my_pos)
            )
            if _manhattan(pos, self.my_pos) <= 4:
                favored = hp >= desc.health and my_prio >= WEAPON_PRIORITY.get(
                    desc.weapon.name, 1
                )
                threat = 2 if favored else 3
            else:
                threat = 1
        if hp <= 3 and threat == 3:
            return "flee"
        if hp <= 4 and self.potions:
            return "loot"
        if my_prio <= 3 and self._best_upgrade(self.my_pos, my_prio) is not None:
            return "loot"
        if self.menhir is not None and (
            self.mist_seen or self._mist_margin(self.my_pos) <= 10
        ):
            return "menhir"
        if self.enemies and my_prio >= 3:
            return "hunt"
        if self.menhir is not None:
            return "menhir"
        return "explore"

    def _run_mode(
        self, my_pos: Coords, facing: Facing, weapon_name: str, hp: int, my_prio: int
    ) -> Optional[Action]:
        if self.mode == "hunt":
            return self._mode_hunt(my_pos, facing, weapon_name, my_prio)
        if self.mode == "loot":
            return self._mode_loot(my_pos, facing, hp, my_prio)
        if self.mode == "menhir":
            return self._mode_menhir(my_pos, facing)
        if self.mode == "flee":
            return self._mode_flee(my_pos, facing, weapon_name)
        return self._mode_explore(my_pos, facing)

    def _mode_hunt(
        self, my_pos: Coords, facing: Facing, weapon_name: str, my_prio: int
    ) -> Optional[Action]:
        if not self.enemies:
            return self._mode_explore(my_pos, facing)

        def target_score(entry) -> float:
            pos, desc = entry
            score = _manhattan(pos, my_pos) + 2 * desc.health
            score += 3 * max(0, WEAPON_PRIORITY.get(desc.weapon.name, 1) - my_prio)
            to_me = (my_pos[0] - pos[0], my_pos[1] - pos[1])
            fv = desc.facing.value
            if to_me[0] * fv[0] + to_me[1] * fv[1] <= 0:
                score -= 2
            return score

        target_pos, target_desc = min(self.enemies, key=target_score)
        turn = self._turn_to_hit(my_pos, facing, weapon_name)
        if turn is not None:
            return turn
        avoid = self.mist_tiles | self.fire_tiles
        for pos, tiles_hit in self.enemy_danger:
            if pos != target_pos:
                avoid |= tiles_hit
        return self._step_towards(my_pos, facing, target_pos, avoid)

    def _mode_loot(
        self, my_pos: Coords, facing: Facing, hp: int, my_prio: int
    ) -> Optional[Action]:
        goal: Optional[Coords] = None
        if self.potions and hp <= 5:
            goal = min(self.potions, key=lambda c: _manhattan(c, my_pos))
        if goal is None:
            goal = self._best_upgrade(my_pos, my_prio)
        if goal is None and self.potions:
            goal = min(self.potions, key=lambda c: _manhattan(c, my_pos))
        if goal is None or goal == my_pos:
            return self._mode_explore(my_pos, facing)
        avoid = self.danger | self.mist_tiles | self.fire_tiles
        return self._step_towards(my_pos, facing, goal, avoid)

    def _best_upgrade(self, my_pos: Optional[Coords], my_prio: int) -> Optional[Coords]:
        if my_pos is None:
            return None
        best = None
        best_score = 10 ** 9
        for c, name in self.loot.items():
            gain = WEAPON_PRIORITY.get(name, 0) - my_prio
            if gain <= 0:
                continue
            score = _manhattan(c, my_pos) - 3 * gain
            if score < best_score:
                best_score = score
                best = c
        return best

    def _mode_explore(self, my_pos: Coords, facing: Facing) -> Optional[Action]:
        if self.explore_target is not None:
            if self.explore_target == my_pos or not self._is_frontier(
                self.explore_target
            ):
                self.explore_target = None
        if self.explore_target is None:
            self.explore_target = self._frontier(my_pos)
        avoid = self.danger | self.mist_tiles | self.fire_tiles
        if self.explore_target is None:
            goal = self.menhir if self.menhir is not None else self._center()
            if goal is None or goal == my_pos:
                return Action.TURN_RIGHT
            return self._step_towards(my_pos, facing, goal, avoid)
        return self._step_towards(my_pos, facing, self.explore_target, avoid)

    def _is_frontier(self, c: Coords) -> bool:
        if self.terrain_types.get(c) not in PASSABLE_TYPES:
            return False
        return any(_add(c, d) not in self.seen for d in DIRS)

    def _frontier(self, pos: Coords) -> Optional[Coords]:
        best = None
        best_d = 10 ** 9
        for c, t in self.terrain_types.items():
            if t not in PASSABLE_TYPES:
                continue
            for d in DIRS:
                if _add(c, d) not in self.seen:
                    dist = _manhattan(c, pos)
                    if dist < best_d:
                        best_d = dist
                        best = c
                    break
        return best

    def _center(self) -> Optional[Coords]:
        if self.arena_size is not None:
            return Coords(self.arena_size[0] // 2, self.arena_size[1] // 2)
        if not self.seen:
            return None
        xs = [c[0] for c in self.seen]
        ys = [c[1] for c in self.seen]
        return Coords(sum(xs) // len(xs), sum(ys) // len(ys))

    def _mode_menhir(self, my_pos: Coords, facing: Facing) -> Optional[Action]:
        if self.menhir is not None:
            d = _manhattan(my_pos, self.menhir)
            if my_pos == self.menhir:
                return Action.TURN_RIGHT
            if d == 1 and self.menhir not in self.occupied:
                step = self._step_delta(my_pos, facing, self.menhir)
                if step is not None:
                    return step
            if d <= 2 and (self.menhir in self.occupied or d == 1):
                return Action.TURN_RIGHT
        goal = self.menhir if self.menhir is not None else self._center()
        if goal is None or goal == my_pos:
            return Action.TURN_RIGHT
        avoid = self.danger | self.mist_tiles | self.fire_tiles
        action = self._step_towards(my_pos, facing, goal, avoid)
        if action is None and self.menhir is None:
            return self._mode_explore(my_pos, facing)
        return action

    def _mode_flee(
        self, my_pos: Coords, facing: Facing, weapon_name: str
    ) -> Optional[Action]:
        candidates = [my_pos]
        for d in DIRS:
            n = _add(my_pos, d)
            if (
                self.terrain_types.get(n) in PASSABLE_TYPES
                and n not in self.occupied
            ):
                candidates.append(n)

        safe_goal = self.menhir if self.menhir is not None else self._center()

        def cost(c: Coords) -> float:
            value = 0.0
            if c in self.danger:
                value += 1000.0
            if c in self.fire_tiles:
                value += 400.0
            if c in self.mist_tiles:
                value += 60.0
            if self.enemies:
                value -= 12.0 * min(_manhattan(c, e[0]) for e in self.enemies)
            if safe_goal is not None:
                value += 2.0 * _euclid(c, safe_goal)
            if c == my_pos:
                value += 1.0
            return value

        best = min(candidates, key=cost)
        if best == my_pos:
            if self._can_hit_enemy(my_pos, facing, weapon_name):
                return self._attack(weapon_name)
            turn = self._turn_to_hit(my_pos, facing, weapon_name)
            if turn is not None:
                return turn
            return Action.TURN_RIGHT
        return self._step_delta(my_pos, facing, best)

    def _hazard_step(self, my_pos: Coords, facing: Facing) -> Optional[Action]:
        candidates = []
        for d in DIRS:
            n = _add(my_pos, d)
            if (
                self.terrain_types.get(n) in PASSABLE_TYPES
                and n not in self.occupied
            ):
                candidates.append(n)
        if not candidates:
            return None
        safe_goal = self.menhir if self.menhir is not None else self._center()

        def cost(c: Coords) -> float:
            value = 0.0
            if c in self.mist_tiles or c in self.fire_tiles:
                value += 100.0
            if c in self.danger:
                value += 10.0
            if safe_goal is not None:
                value += _euclid(c, safe_goal)
            return value

        best = min(candidates, key=cost)
        if best in self.mist_tiles or best in self.fire_tiles:
            return None
        return self._step_delta(my_pos, facing, best)

    def _attack_tiles(
        self, pos: Coords, facing: Facing, weapon_name: str
    ) -> List[Coords]:
        weapon_cls = WEAPON_CLASSES.get(weapon_name)
        if weapon_cls is None:
            return []
        return weapon_cls.cut_positions(self.view, pos, facing)

    def _can_hit_enemy(self, pos: Coords, facing: Facing, weapon_name: str) -> bool:
        if not self.enemies:
            return False
        if weapon_name == "scroll" and self.scroll_used >= SCROLL_CHARGES:
            return False
        enemy_coords = {ec for ec, _ in self.enemies}
        return bool(enemy_coords & set(self._attack_tiles(pos, facing, weapon_name)))

    def _turn_to_hit(
        self, pos: Coords, facing: Facing, weapon_name: str
    ) -> Optional[Action]:
        if not self.enemies:
            return None
        enemy_coords = {ec for ec, _ in self.enemies}
        left = facing.turn_left()
        right = facing.turn_right()
        if enemy_coords & set(self._attack_tiles(pos, left, weapon_name)):
            return Action.TURN_LEFT
        if enemy_coords & set(self._attack_tiles(pos, right, weapon_name)):
            return Action.TURN_RIGHT
        if enemy_coords & set(self._attack_tiles(pos, facing.opposite(), weapon_name)):
            return Action.TURN_LEFT
        return None

    def _attack(self, weapon_name: str) -> Action:
        if weapon_name == "scroll":
            self.scroll_used += 1
        return Action.ATTACK

    def _step_towards(
        self, pos: Coords, facing: Facing, target: Coords, avoid: Set[Coords]
    ) -> Optional[Action]:
        path = self._bfs(pos, target, avoid)
        if not path:
            path = self._bfs(pos, target, set())
        if not path or len(path) < 2:
            return None
        return self._step_delta(pos, facing, path[1])

    def _step_delta(self, pos: Coords, facing: Facing, nxt: Coords) -> Optional[Action]:
        dx, dy = nxt[0] - pos[0], nxt[1] - pos[1]
        fv = facing.value
        if (dx, dy) == (fv[0], fv[1]):
            return Action.STEP_FORWARD
        ov = facing.opposite().value
        if (dx, dy) == (ov[0], ov[1]):
            return Action.STEP_BACKWARD
        lv = facing.turn_left().value
        if (dx, dy) == (lv[0], lv[1]):
            return Action.STEP_LEFT
        rv = facing.turn_right().value
        if (dx, dy) == (rv[0], rv[1]):
            return Action.STEP_RIGHT
        return None

    def _bfs(self, start: Coords, goal: Coords, avoid: Set[Coords]) -> List[Coords]:
        if start == goal:
            return [start]
        queue = deque([start])
        parent: Dict[Coords, Coords] = {start: start}
        while queue:
            cur = queue.popleft()
            if cur == goal:
                path = [cur]
                while parent[path[-1]] != path[-1]:
                    path.append(parent[path[-1]])
                path.reverse()
                return path
            for d in DIRS:
                n = _add(cur, d)
                if n in parent:
                    continue
                if n != goal:
                    if self.terrain_types.get(n) not in PASSABLE_TYPES:
                        continue
                    if n in self.occupied or n in avoid:
                        continue
                parent[n] = cur
                queue.append(n)
        return []

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.CZAK_NORIS

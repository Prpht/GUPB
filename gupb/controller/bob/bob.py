"""Bob - w skrócie best of bots 
"""

from __future__ import annotations

import random
from collections import deque
from typing import Dict, List, Optional, Set, Tuple

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

from . import bob_utils as bu
from .bob_weights import merge_weights

Coords = coordinates.Coords
Facing = characters.Facing
Action = characters.Action

DEBUG = False

STARTING_HP = 8
LOW_HP = 3
CRITICAL_HP = 2
RECENT_ENEMY_TTL = 5
LOOP_WINDOW = 6

EARLY_MAX_TURN = 60
MID_MAX_TURN = 150

THREAT_BOW_REACH = 8
ENEMY_RADIAL_REACH = {"bow": 8, "sword": 3, "axe": 1, "amulet": 2, "scroll": 1, "knife": 1}

STEP_ACTIONS = (Action.STEP_FORWARD, Action.STEP_BACKWARD, Action.STEP_LEFT, Action.STEP_RIGHT)
SIDE_BACK_ACTIONS = (Action.STEP_BACKWARD, Action.STEP_LEFT, Action.STEP_RIGHT)
TURN_ACTIONS = (Action.TURN_LEFT, Action.TURN_RIGHT)
CANDIDATE_ACTIONS = STEP_ACTIONS + TURN_ACTIONS + (Action.ATTACK, Action.DO_NOTHING)


class EnemyInfo:
    """Ostatnio widziany przeciwnik i jego stan"""

    __slots__ = ("pos", "health", "weapon", "facing", "turn")

    def __init__(self, pos: Coords, health: int, weapon: str, facing: Optional[Facing], turn: int) -> None:
        self.pos = pos
        self.health = health
        self.weapon = weapon
        self.facing = facing
        self.turn = turn


class Bob(controller.Controller):
    def __init__(self, bot_name: str, weights: Optional[Dict[str, float]] = None) -> None:
        self.bot_name = bot_name
        self.w: Dict[str, float] = merge_weights(weights)
        self._reset_state(0)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Bob) and self.bot_name == other.bot_name

    def __hash__(self) -> int:
        return hash(self.bot_name)

    def _reset_state(self, game_no: int) -> None:
        """Czysci cala pamiec i liczniki miedzy grami."""
        self.turn_no = 0
        self.known_type: Dict[Coords, str] = {}
        self.visited_count: Dict[Coords, int] = {}
        self.known_weapons: Dict[Coords, str] = {}
        self.known_potions: Set[Coords] = set()
        self.known_menhir: Optional[Coords] = None
        self.known_fire: Set[Coords] = set()
        self.known_mist: Set[Coords] = set()
        self.mist_seen = False
        self.last_positions: deque = deque(maxlen=16)
        self.last_actions: deque = deque(maxlen=16)
        self.last_seen_enemies: Dict[Coords, EnemyInfo] = {}
        self.visible_characters: Set[Coords] = set()
        self.threat_map: Dict[Coords, float] = {}
        self.current_health = STARTING_HP
        self.prev_pos: Optional[Coords] = None
        self.prev_action: Optional[Action] = None
        self.prev_weapon: str = "knife"
        self.scroll_charges: int = 0
        self.stuck: int = 0
        self.rng = random.Random(1000 + game_no)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._reset_state(game_no)
        fixed = getattr(arenas, "FIXED_MENHIRS", {})
        if getattr(arena_description, "name", None) in fixed:
            self.known_menhir = bu.to_coords(fixed[arena_description.name])

    def praise(self, score: int) -> None:
        pass

    @property
    def name(self) -> str:
        return self.bot_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BOB

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Petla decyzyjna: obserwacja, threat map, cel, scoring akcji. Fallback bezpieczny"""
        try:
            self.turn_no += 1
            self._observe(knowledge)
            pos = bu.to_coords(knowledge.position)
            self._update_stuck(pos)

            my_desc = self._my_description(knowledge, pos)
            if my_desc is None:
                return self._safe_fallback(pos)
            facing = bu.safe_getattr(my_desc, "facing")
            if facing is None:
                return self._safe_fallback(pos)
            health = int(bu.safe_getattr(my_desc, "health", STARTING_HP))
            self.current_health = health
            weapon_full = bu.safe_getattr(bu.safe_getattr(my_desc, "weapon"), "name", "knife")
            weapon = bu.base_weapon_name(weapon_full)
            self._track_scroll(weapon)

            enemies = self._collect_enemies(knowledge, pos)
            phase = self._phase()
            self.threat_map = self._build_threat_map(enemies)

            dist_me, _ = bu.dijkstra([pos], self._passable, self._path_cost)
            target = self._select_target(pos, health, weapon, phase, enemies, dist_me)
            field: Dict[Coords, float] = {}
            if target is not None:
                field, _ = bu.dijkstra([target], self._passable, self._path_cost)

            action = self._choose_action(pos, facing, health, weapon, weapon_full, enemies, phase, target, field)

            self.last_positions.appendleft(pos)
            self.last_actions.appendleft(action)
            self.visited_count[pos] = self.visited_count.get(pos, 0) + 1
            self.prev_pos = pos
            self.prev_action = action
            if action == Action.ATTACK and weapon == "scroll":
                self.scroll_charges = max(0, self.scroll_charges - 1)
            return action
        except Exception:
            if DEBUG:
                raise
            return self._safe_fallback(bu.to_coords(getattr(knowledge, "position", Coords(0, 0))))

    def _safe_fallback(self, pos: Coords) -> Action:
        """Awaryjna akcja: obrot ku nieznanemu albo krok, nigdy None ani bezczynność"""
        for f in bu.ALL_FACINGS:
            if bu.add(pos, f.value) not in self.known_type:
                return Action.TURN_LEFT
        return Action.TURN_RIGHT

    def _my_description(self, knowledge: characters.ChampionKnowledge, pos: Coords):
        tile = knowledge.visible_tiles.get(pos)
        if tile is None:
            return None
        return bu.safe_getattr(tile, "character")

    def _update_stuck(self, pos: Coords) -> None:
        """Wykrywa nieudany ruch: krok bez zmiany pozycji podbija licznik zablokowania"""
        if self.prev_action in STEP_ACTIONS and self.prev_pos == pos:
            self.stuck += 1
        elif self.prev_pos is not None and self.prev_pos != pos:
            self.stuck = 0

    def _track_scroll(self, weapon: str) -> None:
        """Estymuje ladunki scrolla: reset przy podniesieniu, dekrement przy ataku."""
        if weapon == "scroll" and self.prev_weapon != "scroll":
            self.scroll_charges = 5
        self.prev_weapon = weapon

    def _observe(self, knowledge: characters.ChampionKnowledge) -> None:
        """Aktualizuje pamiec mapy, lupow, mikstur, menhiru, ognia i mgły"""
        self.visible_characters = set()
        for coords, tile in knowledge.visible_tiles.items():
            c = bu.to_coords(coords)
            t_type = bu.safe_getattr(tile, "type", "land")
            self.known_type[c] = t_type
            if bu.safe_getattr(tile, "character") is not None:
                self.visible_characters.add(c)
            if t_type == "menhir":
                self.known_menhir = c

            loot = bu.safe_getattr(tile, "loot")
            loot_name = bu.safe_getattr(loot, "name") if loot else None
            if loot_name:
                self.known_weapons[c] = bu.base_weapon_name(loot_name)
            elif c in self.known_weapons:
                del self.known_weapons[c]

            consumable = bu.safe_getattr(tile, "consumable")
            cons_name = bu.safe_getattr(consumable, "name") if consumable else None
            if cons_name == "potion":
                self.known_potions.add(c)
            else:
                self.known_potions.discard(c)

            eff_types = {bu.safe_getattr(e, "type", "") for e in (bu.safe_getattr(tile, "effects", []) or [])}
            if "fire" in eff_types:
                self.known_fire.add(c)
            else:
                self.known_fire.discard(c)
            if "mist" in eff_types:
                self.known_mist.add(c)
                self.mist_seen = True
            else:
                self.known_mist.discard(c)

    def _collect_enemies(self, knowledge: characters.ChampionKnowledge, pos: Coords) -> List[EnemyInfo]:
        """Zwraca widocznych wrogow i odswieza pamiec ostatnio widzianych"""
        seen: List[EnemyInfo] = []
        for coords, tile in knowledge.visible_tiles.items():
            c = bu.to_coords(coords)
            if c == pos:
                continue
            ch = bu.safe_getattr(tile, "character")
            if ch is None:
                continue
            info = EnemyInfo(
                c,
                int(bu.safe_getattr(ch, "health", STARTING_HP)),
                bu.base_weapon_name(bu.safe_getattr(bu.safe_getattr(ch, "weapon"), "name", "knife")),
                bu.safe_getattr(ch, "facing"),
                self.turn_no,
            )
            seen.append(info)
            self.last_seen_enemies[c] = info
        self.last_seen_enemies = {
            k: v for k, v in self.last_seen_enemies.items() if self.turn_no - v.turn <= RECENT_ENEMY_TTL
        }
        return seen

    def _phase(self) -> str:
        if self.mist_seen or self.turn_no >= MID_MAX_TURN:
            return "late"
        if self.turn_no >= EARLY_MAX_TURN:
            return "mid"
        return "early"

    def _passable(self, c: Coords) -> bool:
        return self.known_type.get(c) in bu.PASSABLE_TYPES

    def _in_map(self, c: Coords) -> bool:
        return c in self.known_type

    def _is_opaque(self, c: Coords) -> bool:
        return self.known_type.get(c) in bu.OPAQUE_TYPES or c in self.visible_characters

    def _path_cost(self, c: Coords) -> float:
        """Koszt wejścia na pole przy pathfindingu: ogień/mgła/zagrożenie/las"""
        cost = 0.0
        if c in self.known_fire:
            cost += 12.0
        if c in self.known_mist:
            cost += 7.0
        threat_mult = 1.6 if self.current_health <= LOW_HP else 1.0
        cost += min(self.threat_map.get(c, 0.0), 6.0) * threat_mult
        if self.known_type.get(c) == "forest":
            cost += 0.4
        return cost

    def _build_threat_map(self, enemies: List[EnemyInfo]) -> Dict[Coords, float]:
        """
        Threat map z pól rażenia widocznych wrogów (bieżący facing oraz obroty),
        rozszerzona radialnie o możliwy krok.
        Wrogowie zapamiętani, ale niewidoczni, dostają słabszą groźbę
        """
        tm: Dict[Coords, float] = {}

        def bump(coord: Coords, value: float) -> None:
            if value > tm.get(coord, 0.0):
                tm[coord] = value

        visible_pos = {e.pos for e in enemies}
        for e in enemies:
            dmg = float(bu.weapon_damage(e.weapon))
            mr = THREAT_BOW_REACH if e.weapon == "bow" else None
            if e.facing is not None:
                for c in bu.weapon_hit_tiles(e.weapon, e.pos, e.facing, self._in_map, self._is_opaque, mr):
                    bump(c, dmg)
            for f in bu.ALL_FACINGS:
                for c in bu.weapon_hit_tiles(e.weapon, e.pos, f, self._in_map, self._is_opaque, mr):
                    bump(c, dmg * 0.6)
            reach = ENEMY_RADIAL_REACH.get(e.weapon, 1) + 1
            for c in self._radial(e.pos, reach):
                bump(c, dmg * 0.4 * (1.0 - bu.manhattan(c, e.pos) / (reach + 1.0)))

        for info in self.last_seen_enemies.values():
            if info.pos in visible_pos:
                continue
            dmg = float(bu.weapon_damage(info.weapon))
            reach = ENEMY_RADIAL_REACH.get(info.weapon, 1)
            for c in self._radial(info.pos, reach):
                bump(c, dmg * 0.5 * (1.0 - bu.manhattan(c, info.pos) / (reach + 1.0)))
        return tm

    def _radial(self, center: Coords, reach: int) -> List[Coords]:
        out = []
        for dx in range(-reach, reach + 1):
            for dy in range(-reach, reach + 1):
                if abs(dx) + abs(dy) <= reach:
                    c = Coords(center[0] + dx, center[1] + dy)
                    if c in self.known_type:
                        out.append(c)
        return out

    def _threat_at(self, c: Coords) -> float:
        return self.threat_map.get(c, 0.0)

    def _passable_neighbors(self, c: Coords) -> int:
        return sum(1 for nb in bu.neighbors4(c) if self._passable(nb))

    def _wall_neighbors(self, c: Coords) -> int:
        return sum(1 for nb in bu.neighbors4(c) if self.known_type.get(nb) == "wall")

    def _is_frontier(self, c: Coords) -> bool:
        """Pole przechodnie sąsiadujące z nieznanym obszarem"""
        return self._passable(c) and any(nb not in self.known_type for nb in bu.neighbors4(c))

    def _is_door_like(self, c: Coords) -> bool:
        """Przechodnie pole z ścianami po dwóch przeciwnych stronach"""
        kt = self.known_type
        horiz = kt.get(bu.add(c, Coords(-1, 0))) == "wall" and kt.get(bu.add(c, Coords(1, 0))) == "wall"
        vert = kt.get(bu.add(c, Coords(0, -1))) == "wall" and kt.get(bu.add(c, Coords(0, 1))) == "wall"
        return self._passable(c) and (horiz or vert)

    def _known_bounds(self) -> Tuple[int, int, int, int]:
        xs = [c[0] for c in self.known_type]
        ys = [c[1] for c in self.known_type]
        return min(xs), max(xs), min(ys), max(ys)

    def _known_center(self) -> Coords:
        minx, maxx, miny, maxy = self._known_bounds()
        return Coords((minx + maxx) // 2, (miny + maxy) // 2)

    def _select_target(
        self,
        pos: Coords,
        health: int,
        weapon: str,
        phase: str,
        enemies: List[EnemyInfo],
        dist_me: Dict[Coords, float],
    ) -> Optional[Coords]:
        """
        Wybiera glowny cel wg fazy, HP, znanych broni/mikstur, menhiru i wrogów.
        Zwraca współrzędne celu (mikstura, broń, menhir, pozycja ataku lub frontier)
        """
        w = self.w
        candidates: List[Tuple[float, Coords]] = []

        for p in self.known_potions:
            if p in dist_me:
                mult = 1.0
                extra = 0.0
                if health <= CRITICAL_HP:
                    mult = w["low_hp_potion_multiplier"] * 1.5
                    extra = w["critical_hp_potion_bonus"]
                elif health <= LOW_HP + 1:
                    mult = w["low_hp_potion_multiplier"]
                elif health > 6:
                    mult = 0.45 if dist_me[p] > 2 else 0.9
                danger = self._tile_danger(p, health)
                adjacent_bonus = 3.0 if bu.manhattan(pos, p) <= 1 else 0.0
                candidates.append((w["potion"] * mult + extra + adjacent_bonus - 0.28 * dist_me[p] - danger, p))

        my_val = bu.weapon_value(weapon, phase, health, len(enemies))
        for wp, wname in self.known_weapons.items():
            if wp in dist_me:
                gain = bu.weapon_value(wname, phase, health, len(enemies)) - my_val
                if gain > 0.2:
                    candidates.append((w["weapon_upgrade"] * gain - 0.25 * dist_me[wp], wp))

        enemy_target = self._enemy_target(pos, health, weapon, phase, enemies, dist_me)
        if enemy_target is not None:
            candidates.append(enemy_target)

        if self.known_menhir is not None and self.known_menhir in dist_me:
            mult = w["menhir_late_multiplier"] if phase == "late" else (1.5 if phase == "mid" else 1.0)
            if self.mist_seen:
                mult += 2.0
            candidates.append((w["menhir"] * mult - 0.2 * dist_me[self.known_menhir], self.known_menhir))

        best_frontier = self._best_frontier(pos, phase, dist_me)
        if best_frontier is not None:
            candidates.append(best_frontier)

        fallback = self._center_fallback(pos, phase, dist_me)
        if fallback is not None:
            candidates.append(fallback)

        if not candidates:
            return None
        return max(candidates, key=lambda x: x[0])[1]

    def _tile_danger(self, c: Coords, health: int) -> float:
        mult = self.w["low_hp_threat_multiplier"] if health <= LOW_HP else 1.0
        danger = min(self._threat_at(c), 6.0) * mult
        if c in self.known_fire:
            danger += 8.0
        if c in self.known_mist:
            danger += 6.0
        return danger

    def _enemy_target(
        self,
        pos: Coords,
        health: int,
        weapon: str,
        phase: str,
        enemies: List[EnemyInfo],
        dist_me: Dict[Coords, float],
    ) -> Optional[Tuple[float, Coords]]:
        """
        Wybiera przeciwnika jako cel, jeśli walka jest opłacalna, i wskazuje
        najbliższa bezpieczna pozycje ataku (lub jego pole, gdy juz w zasiegu)
        """
        if not enemies or health <= CRITICAL_HP:
            return None
        w = self.w
        my_dmg = bu.weapon_damage(weapon)
        my_val = bu.weapon_value(weapon, phase, health, len(enemies))
        best: Optional[Tuple[float, Coords]] = None
        threat_tol = 1.0 if health <= LOW_HP else 3.0

        for e in enemies:
            favorable = (
                e.health <= my_dmg
                or my_val >= bu.weapon_value(e.weapon, phase, e.health, 1) - 0.5
            )
            if weapon == "knife" and e.health > my_dmg:
                favorable = False
            if not favorable:
                continue
            aps = bu.attack_positions(weapon, e.pos, self._in_map, self._is_opaque, self._passable, THREAT_BOW_REACH)
            if pos in aps:
                bonus = w["engage_bonus"] + (w["kill_opportunity"] * 0.3 if e.health <= my_dmg else 0.0)
                cand = (bonus + 5.0, e.pos)
                if best is None or cand[0] > best[0]:
                    best = cand
                continue
            reachable = [p for p in aps if p in dist_me and self.threat_map.get(p, 0.0) <= threat_tol]
            if not reachable:
                continue
            spot = min(reachable, key=lambda p: dist_me[p])
            value = w["engage_bonus"] + (w["kill_opportunity"] * 0.2 if e.health <= my_dmg else 0.0)
            cand = (value - 0.3 * dist_me[spot], spot)
            if best is None or cand[0] > best[0]:
                best = cand
        return best

    def _best_frontier(self, pos: Coords, phase: str, dist_me: Dict[Coords, float]) -> Optional[Tuple[float, Coords]]:
        """Najlepszy frontier eksploracji z premia za budynki, drzwi, loot i nowe pola"""
        w = self.w
        best: Optional[Tuple[float, Coords]] = None
        for c, d in dist_me.items():
            if c == pos or not self._is_frontier(c):
                continue
            fv = w["explore"] + w["frontier_bonus"]
            wn = self._wall_neighbors(c)
            if wn >= 1:
                fv += w["building_interest"] * min(wn, 2) * 0.5
            if self._is_door_like(c):
                fv += w["door_bonus"]
            if self.visited_count.get(c, 0) == 0:
                fv += w["unvisited_bonus"]
            else:
                fv -= w["visited_penalty"] * min(self.visited_count.get(c, 0), 4)
            if any(wp in dist_me and bu.manhattan(c, wp) <= 3 for wp in self.known_weapons):
                fv += w["known_loot_bonus"] * 0.5
            open_nb = self._passable_neighbors(c)
            if open_nb <= 1:
                fv -= w["dead_end_penalty"] * 0.5
            fv -= self._tile_danger(c, LOW_HP + 1) * 0.25
            if phase == "late":
                fv -= w["late_edge_penalty"] * self._edge_closeness(c)
            score = fv - 0.25 * d
            if best is None or score > best[0]:
                best = (score, c)
        return best

    def _center_fallback(self, pos: Coords, phase: str, dist_me: Dict[Coords, float]) -> Optional[Tuple[float, Coords]]:
        """
        Gdy menhir nieznany, a jest mid/late lub widoczna mgla: kieruj do srodka
        znanego obszaru, z dala od mgly i zewnetrznych obrzezy. Bez pelnej mapy.
        """
        if self.known_menhir is not None:
            return None
        if phase == "early" and not self.mist_seen:
            return None
        if not self.known_type:
            return None
        w = self.w
        center = self._known_center()
        best: Optional[Tuple[float, Coords]] = None
        for c, d in dist_me.items():
            if c == pos:
                continue
            score = -bu.manhattan(c, center) * 0.6
            if c in self.known_fire or c in self.known_mist:
                score -= 10.0
            if self.known_mist:
                nearest_mist = min(bu.manhattan(c, mist) for mist in self.known_mist)
                score += min(nearest_mist, 8) * w["mist_distance_bonus"]
            if self._is_frontier(c):
                score += 1.5 if bu.manhattan(c, center) <= bu.manhattan(pos, center) + 4 else 0.4
            if self.visited_count.get(c, 0) == 0:
                score += 1.0
            score -= self._edge_closeness(c) * w["late_edge_penalty"]
            score -= self._tile_danger(c, LOW_HP + 1) * 0.2
            score -= 0.1 * d
            if best is None or score > best[0]:
                best = (score, c)
        if best is None:
            return None
        mult = 2.0 if self.mist_seen else 1.0
        return (w["center_fallback"] * mult + best[0] * 0.2, best[1])

    def _choose_action(
        self,
        pos: Coords,
        facing: Facing,
        health: int,
        weapon: str,
        weapon_full: str,
        enemies: List[EnemyInfo],
        phase: str,
        target: Optional[Coords],
        field: Dict[Coords, float],
    ) -> Action:
        """Ocenia każdą akcje funkcja użytecznosci i zwraca najlepszą"""
        recent = list(self.last_positions)[:LOOP_WINDOW]
        recent_set = set(recent)
        enemy_near = min((bu.manhattan(pos, e.pos) for e in enemies), default=999)
        center = self._known_center() if self.known_type else pos
        jitter = 0.02 + 0.25 * min(self.stuck, 4)

        best_action = Action.TURN_LEFT
        best_score = float("-inf")
        for action in CANDIDATE_ACTIONS:
            score = self._score_action(
                action, pos, facing, health, weapon, weapon_full,
                enemies, phase, target, field, recent_set, enemy_near, center,
            )
            score += self.rng.uniform(-jitter, jitter)
            if score > best_score:
                best_score = score
                best_action = action
        return best_action

    def _score_action(
        self,
        action: Action,
        pos: Coords,
        facing: Facing,
        health: int,
        weapon: str,
        weapon_full: str,
        enemies: List[EnemyInfo],
        phase: str,
        target: Optional[Coords],
        field: Dict[Coords, float],
        recent: Set[Coords],
        enemy_near: int,
        center: Coords,
    ) -> float:
        """Suma składników użyteczności: zagrożenia, cel, eksploracja, combat, anty-loop"""
        w = self.w
        low = health <= LOW_HP
        new_pos, new_facing = bu.simulate_action(pos, facing, action)
        is_step = action in STEP_ACTIONS
        is_turn = action in TURN_ACTIONS
        eff_pos = pos
        blocked = False
        unknown_step = False

        if is_step:
            t = self.known_type.get(new_pos)
            if t in bu.PASSABLE_TYPES and not any(e.pos == new_pos for e in enemies):
                eff_pos = new_pos
            elif t is None:
                unknown_step = True
            else:
                blocked = True

        score = 0.0

        if eff_pos in self.known_fire:
            score -= w["fire_penalty"]
        if eff_pos in self.known_mist:
            score -= w["mist_penalty"]
        tmul = w["low_hp_threat_multiplier"] if low else 1.0
        score -= w["threat_penalty"] * min(self._threat_at(eff_pos), 6.0) * 0.3 * tmul

        if target is not None and field:
            f_now = field.get(pos)
            f_new = field.get(eff_pos)
            if f_now is not None and f_new is not None:
                score += w["progress_weight"] * (f_now - f_new)
            if f_new is not None:
                score -= w["target_distance_penalty"] * f_new * 0.03

        moved = eff_pos != pos
        if moved:
            visited = self.visited_count.get(eff_pos, 0)
            if visited == 0:
                score += w["unvisited_bonus"] * (1.0 + 0.4 * min(self.stuck, 4))
            else:
                score -= w["visited_penalty"] * min(visited, 5)
            wn = self._wall_neighbors(eff_pos)
            if wn >= 1 and visited == 0:
                score += w["building_interest"] * 0.4
            if self._is_door_like(eff_pos):
                score += w["door_bonus"] * 0.5
            if eff_pos in recent:
                score -= w["loop_penalty"] * (1.0 + 0.5 * min(self.stuck, 4))
            has_unknown_nb = any(nb not in self.known_type for nb in bu.neighbors4(eff_pos))
            open_nb = self._passable_neighbors(eff_pos)
            if open_nb <= 1 and not has_unknown_nb:
                score -= w["dead_end_penalty"]
            else:
                score += w["escape_route_bonus"] * min(open_nb - 1, 3) * 0.3
            if phase == "late" and self.known_menhir is None:
                score -= w["late_edge_penalty"] * self._edge_closeness(eff_pos) * 0.5
            if self.known_menhir is None and (phase != "early" or self.mist_seen) and self.known_mist:
                nearest_mist = min(bu.manhattan(eff_pos, mist) for mist in self.known_mist)
                score += min(nearest_mist, 8) * w["mist_distance_bonus"] * 0.3

        if unknown_step:
            score -= self._unknown_risk(new_pos, phase, low, enemy_near)
            if phase == "early" and not low and enemy_near > 4:
                score += w["frontier_bonus"] * 0.4

        if blocked:
            score -= w["blocked_penalty"] * (1.0 + 0.4 * min(self.stuck, 4))

        if action == Action.DO_NOTHING:
            score -= w["do_nothing_penalty"]

        if is_turn:
            score -= w["useless_turn_penalty"]
            front = bu.add(pos, new_facing.value)
            if front not in self.known_type:
                score += w["explore"] * 0.4
            if self._turn_oscillation(action):
                score -= w["useless_turn_penalty"] * 1.5
            if self.stuck >= 2 and front in self.known_type:
                score -= w["useless_turn_penalty"] * min(self.stuck, 4)

        if phase == "late" and self.known_menhir is not None:
            score -= (bu.manhattan(eff_pos, self.known_menhir) * 0.03)

        score += self._combat_score(action, pos, facing, new_facing, eff_pos, health, weapon, weapon_full, enemies)

        if action in SIDE_BACK_ACTIONS and enemies and enemy_near <= 4 and not blocked:
            if self._threat_at(eff_pos) < self._threat_at(pos):
                score += w["side_step_bonus"]
        if action in SIDE_BACK_ACTIONS and self.stuck >= 2 and not blocked:
            score += w["side_step_bonus"] * min(self.stuck, 4)

        return score

    def _edge_closeness(self, c: Coords) -> float:
        """0-1: jak blisko zewnetrznej granicy znanego obszaru leży pole"""
        minx, maxx, miny, maxy = self._known_bounds()
        dx = min(c[0] - minx, maxx - c[0])
        dy = min(c[1] - miny, maxy - c[1])
        span = max(1, min(maxx - minx, maxy - miny))
        return max(0.0, 1.0 - 2.0 * min(dx, dy) / span)

    def _unknown_risk(self, new_pos: Coords, phase: str, low: bool, enemy_near: int) -> float:
        """Kontekstowa kara za krok w nieznane: mniejsza w eksploracji, wieksza przy HP/wrogu/late"""
        risk = self.w["unknown_risk"]
        if phase == "early":
            risk *= 0.4
        if low:
            risk *= 2.0
        if enemy_near <= 3:
            risk *= 2.0
        if phase == "late":
            risk += self.w["late_unknown_penalty"]
        known_open = sum(1 for nb in bu.neighbors4(new_pos) if self._passable(nb))
        if known_open <= 1:
            risk += self.w["dead_end_penalty"] * 0.7
        return risk

    def _turn_oscillation(self, action: Action) -> bool:
        """Wykrywa naprzemienne obroty TURN_LEFT/TURN_RIGHT w ostatnich akcjach"""
        if len(self.last_actions) < 2:
            return False
        a0, a1 = self.last_actions[0], self.last_actions[1]
        if a0 in TURN_ACTIONS and a1 in TURN_ACTIONS and a0 != a1:
            return action in TURN_ACTIONS
        return False

    def _combat_score(
        self,
        action: Action,
        pos: Coords,
        facing: Facing,
        new_facing: Facing,
        eff_pos: Coords,
        health: int,
        weapon: str,
        weapon_full: str,
        enemies: List[EnemyInfo],
    ) -> float:
        """Weapon-aware scoring: atak/ustawienie zależnie od broni, HP i przewagi"""
        if not enemies:
            return -1.5 if action == Action.ATTACK else 0.0
        w = self.w
        my_dmg = bu.weapon_damage(weapon)

        if action == Action.ATTACK:
            hits = bu.weapon_hit_tiles(weapon, pos, facing, self._in_map, self._is_opaque)
            victim = self._enemy_in(hits, enemies)
            if weapon == "bow" and not bu.bow_is_loaded(weapon_full):
                if victim is not None and health > LOW_HP and self._threat_at(pos) < 3.0:
                    return w["bow_distance_bonus"]
                return -3.0
            if weapon == "scroll" and self.scroll_charges <= 0:
                return -3.0
            if victim is None:
                return -2.0
            s = w["attack_hit"] + self._weapon_position_bonus(weapon, pos, victim.pos)
            if victim.health <= my_dmg:
                s += w["kill_opportunity"]
            else:
                if health <= LOW_HP:
                    s -= w["low_hp_aggression_penalty"]
                if weapon == "knife":
                    s -= w["knife_aggression_penalty"]
            return s

        if action in TURN_ACTIONS:
            hits = bu.weapon_hit_tiles(weapon, pos, new_facing, self._in_map, self._is_opaque)
            victim = self._enemy_in(hits, enemies)
            if victim is not None:
                s = w["attack_hit"] * 0.5 + self._weapon_position_bonus(weapon, pos, victim.pos) * 0.5
                if health <= LOW_HP and victim.health > my_dmg:
                    s -= w["low_hp_aggression_penalty"] * 0.5
                return s
            return 0.0

        hits = bu.weapon_hit_tiles(weapon, eff_pos, facing, self._in_map, self._is_opaque)
        victim = self._enemy_in(hits, enemies)
        if victim is not None and health > LOW_HP:
            return w["attack_hit"] * 0.4 + self._weapon_position_bonus(weapon, eff_pos, victim.pos) * 0.4
        return 0.0

    def _weapon_position_bonus(self, weapon: str, pos: Coords, enemy_pos: Coords) -> float:
        """Premia pozycyjna zależna od charakteru broni (dystans/skos/linia/bliski)"""
        w = self.w
        d = bu.manhattan(pos, enemy_pos)
        if weapon == "bow":
            return w["bow_distance_bonus"] if d >= 3 else 0.0
        if weapon == "axe":
            return w["axe_close_bonus"] if bu.chebyshev(pos, enemy_pos) <= 1 else 0.0
        if weapon == "sword":
            return w["sword_line_bonus"]
        if weapon == "amulet":
            return w["amulet_diagonal_bonus"] if abs(enemy_pos[0] - pos[0]) == abs(enemy_pos[1] - pos[1]) else 0.0
        if weapon == "scroll":
            return w["scroll_tactical_bonus"]
        return 0.0

    @staticmethod
    def _enemy_in(tiles: List[Coords], enemies: List[EnemyInfo]) -> Optional[EnemyInfo]:
        tileset = set(tiles)
        for e in enemies:
            if e.pos in tileset:
                return e
        return None


POTENTIAL_CONTROLLERS = [
    Bob("Bob"),
]

from __future__ import annotations

from gupb.model import characters, coordinates

from .combat import CombatEvaluator
from .navigation import DIRS, Navigator
from .worldstate import WorldState


class SurvivorBrain:
    def __init__(self) -> None:
        self.world = WorldState()
        self.navigator = Navigator()
        self.combat = CombatEvaluator()
        self._last_score = 0

    def reset(self, game_no: int, arena_name: str) -> None:
        self.world.reset(arena_name)

    def note_score(self, score: int) -> None:
        self._last_score = score

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.world.update_from_knowledge(knowledge)
        pressure = self.combat.pressure_tiles(self.world)

        if not self.combat.can_kill_now(self.world):
            escape = self.navigator.emergency_move(self.world, pressure)
            if escape is not None:
                return escape

        attack = self.combat.decide_attack(self.world, knowledge.no_of_champions_alive)
        if attack is not None:
            if self.world.weapon_name == "scroll":
                self.world.scroll_charges = max(0, self.world.scroll_charges - 1)
            return attack

        if self.combat.should_preload_bow(self.world, pressure):
            return characters.Action.ATTACK

        targets = self._collect_targets(knowledge.no_of_champions_alive, pressure)
        route = self.navigator.pick_route(self.world, targets, pressure)

        if route is not None:
            action = self.navigator.move_action(self.world, route.next_step)
            if self.world.idle_ticks >= 12 and action in {characters.Action.ATTACK, characters.Action.DO_NOTHING}:
                return characters.Action.TURN_RIGHT
            return action

        explore = self.navigator.exploratory_move(self.world, pressure)
        if explore is not None:
            return explore

        if self.world.idle_ticks >= 12:
            return characters.Action.TURN_RIGHT
        return characters.Action.STEP_RIGHT

    def _collect_targets(
        self,
        alive_count: int,
        pressure: set[coordinates.Coords],
    ) -> list[tuple[coordinates.Coords, float]]:
        targets: list[tuple[coordinates.Coords, float]] = []
        hp = self.world.health

        if hp <= 6 or (hp < 8 and alive_count <= 4):
            for potion in self.world.last_seen_potions:
                targets.append((potion, 12.0 + 2.0 * max(0, 8 - hp)))

        for coords, weapon in self.world.last_seen_loot.items():
            gain = self._weapon_value(weapon) - self._weapon_value(self.world.weapon_name)
            if gain > 0:
                bonus = 8.0 + 2.0 * gain
                if weapon.startswith("bow") and alive_count > 3:
                    bonus += 2.0
                if weapon.startswith("scroll") and alive_count <= 5:
                    bonus += 1.0
                targets.append((coords, bonus))

        if self.world.menhir_position:
            nearest_mist = self.world.nearest_mist_distance()
            urgent_menhir = (
                alive_count <= 4
                or self.world.predicted_mist(self.world.position, 8)
                or (nearest_mist is not None and nearest_mist <= 8)
            )
            distance_bias = 18.0 if urgent_menhir else 8.0
            if hp <= 3:
                distance_bias += 5.0
            targets.append((self.world.menhir_position, distance_bias))

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    flank = self.world.menhir_position + coordinates.Coords(dx, dy)
                    if (
                        self.world.passable(flank)
                        and flank not in pressure
                        and flank not in self.world.fire_tiles
                        and not self.world.predicted_mist(flank, 2)
                    ):
                        targets.append((flank, 13.0 if alive_count <= 4 else 6.5))
        elif self.world.mist_tiles:
            targets.extend((coord, bonus) for coord, bonus in self._mist_escape_targets(pressure))
        else:
            targets.extend((coord, 3.8) for coord in self._exploration_frontier())

        for enemy in self.world.enemies.values():
            if (
                self.world.turn_no - enemy.seen_at <= 2
                and hp >= 6
                and alive_count > 3
                and self._weapon_value(self.world.weapon_name) >= self._weapon_value(enemy.weapon_name)
            ):
                ambush = enemy.position + enemy.facing.opposite().value
                if self.world.passable(ambush) and ambush not in pressure:
                    targets.append((ambush, 6.5))

        if not targets:
            targets.extend((coord, 2.2) for coord in self._exploration_frontier())
        return targets

    def _mist_escape_targets(
        self,
        pressure: set[coordinates.Coords],
    ) -> list[tuple[coordinates.Coords, float]]:
        candidates: list[tuple[float, coordinates.Coords]] = []
        for coords, terrain in self.world.known_terrain.items():
            if terrain not in {"land", "forest", "menhir"}:
                continue
            if not self.world.passable(coords):
                continue
            if coords in pressure or coords in self.world.fire_tiles or self.world.predicted_mist(coords, 4):
                continue
            nearest_mist = self.world.nearest_mist_distance(coords)
            if nearest_mist is None:
                continue
            distance = abs(coords.x - self.world.position.x) + abs(coords.y - self.world.position.y)
            score = 0.9 * nearest_mist - 0.25 * distance
            candidates.append((score, coords))
        candidates.sort(reverse=True, key=lambda item: item[0])
        return [(coord, 11.0 + min(score, 8.0)) for score, coord in candidates[:6]]

    def _exploration_frontier(self) -> list[coordinates.Coords]:
        front = []
        for coords, terrain in self.world.known_terrain.items():
            if terrain not in {"land", "forest", "menhir"}:
                continue
            if coords in self.world.seen_tiles:
                if self.world.arena_size is not None:
                    continue
                if not any(coords + direction not in self.world.known_terrain for direction in DIRS):
                    continue
            elif self.world.arena_size is None:
                continue
            if coords in self.world.fire_tiles or self.world.predicted_mist(coords, 6):
                continue
            if abs(coords.x - self.world.position.x) + abs(coords.y - self.world.position.y) > 30:
                continue
            front.append(coords)
        front.sort(
            key=lambda c: (
                c in self.world.recent_positions,
                abs(c.x - self.world.position.x) + abs(c.y - self.world.position.y),
            )
        )
        return front[:20]

    @staticmethod
    def _weapon_value(weapon_name: str) -> int:
        base = weapon_name.split("_")[0]
        if weapon_name == "bow_loaded":
            return 7
        if weapon_name == "bow_unloaded":
            return 6
        return {
            "knife": 1,
            "amulet": 2,
            "axe": 4,
            "sword": 5,
            "scroll": 5,
            "bow": 6,
        }.get(base, 1)

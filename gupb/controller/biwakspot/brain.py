from __future__ import annotations

from gupb.model import characters, coordinates

from .combat import CombatEvaluator
from .navigation import Navigator
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

        attack = self.combat.decide_attack(self.world, knowledge.no_of_champions_alive)
        if attack is not None:
            return attack

        targets = self._collect_targets(knowledge.no_of_champions_alive, pressure)
        route = self.navigator.pick_route(self.world, targets, pressure)

        if route is not None:
            action = self.navigator.move_action(self.world, route.next_step)
            if self.world.idle_ticks >= 12 and action in {characters.Action.ATTACK, characters.Action.DO_NOTHING}:
                return characters.Action.TURN_RIGHT
            return action

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

        if hp <= 4:
            for potion in self.world.last_seen_potions:
                targets.append((potion, 18.0))

        wanted_weapons = self._weapon_upgrades(self.world.weapon_name)
        for coords, weapon in self.world.last_seen_loot.items():
            if weapon.split("_")[0] in wanted_weapons:
                bonus = 10.0
                if weapon.startswith("bow") and alive_count > 5:
                    bonus += 2.0
                targets.append((coords, bonus))

        if self.world.menhir_position:
            distance_bias = 16.0 if alive_count <= 5 else 9.0
            if hp <= 3:
                distance_bias += 5.0
            targets.append((self.world.menhir_position, distance_bias))

            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    flank = self.world.menhir_position + coordinates.Coords(dx, dy)
                    if self.world.passable(flank) and flank not in pressure:
                        targets.append((flank, 12.0 if alive_count <= 4 else 6.0))
        else:
            targets.extend((coord, 3.8) for coord in self._exploration_frontier())

        for enemy in self.world.enemies.values():
            if self.world.turn_no - enemy.seen_at <= 2 and hp >= 5 and alive_count > 3:
                ambush = enemy.position + enemy.facing.opposite().value
                if self.world.passable(ambush):
                    targets.append((ambush, 6.5))

        if not targets:
            targets.extend((coord, 2.2) for coord in self._exploration_frontier())
        return targets

    def _exploration_frontier(self) -> list[coordinates.Coords]:
        front = []
        for coords, terrain in self.world.known_terrain.items():
            if terrain not in {"land", "forest", "menhir"}:
                continue
            if coords in self.world.seen_tiles:
                continue
            if abs(coords.x - self.world.position.x) + abs(coords.y - self.world.position.y) > 20:
                continue
            front.append(coords)
        front.sort(key=lambda c: abs(c.x - self.world.position.x) + abs(c.y - self.world.position.y))
        return front[:20]

    @staticmethod
    def _weapon_upgrades(weapon_name: str) -> set[str]:
        base = weapon_name.split("_")[0]
        order = ["knife", "axe", "sword", "bow", "amulet", "scroll"]
        if base not in order:
            return {"sword", "bow", "amulet", "axe", "scroll"}
        threshold = order.index(base)
        return {w for i, w in enumerate(order) if i > threshold}

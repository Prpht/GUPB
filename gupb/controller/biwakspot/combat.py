from __future__ import annotations

from gupb.model import characters, coordinates

from .worldstate import EnemyTrace, WorldState


class CombatEvaluator:
    def decide_attack(self, world: WorldState, alive_count: int) -> characters.Action | None:
        hit_tiles = self.attack_pattern(world, world.position, world.facing, world.weapon_name)
        enemies_hit = [enemy for enemy in world.enemies.values() if enemy.position in hit_tiles and world.turn_no - enemy.seen_at <= 1]
        if not enemies_hit:
            return None

        expected = sum(self._threat_weight(enemy) for enemy in enemies_hit)
        retaliation = 0.0
        for enemy in enemies_hit:
            if self.can_hit(enemy, world.position, world):
                retaliation += 1.5

        endgame_boost = 1.3 if alive_count <= 4 else 1.0
        if world.health <= 3:
            endgame_boost *= 0.8

        if expected * endgame_boost >= retaliation + 0.8:
            if world.weapon_name == "bow_unloaded" and world.idle_ticks >= 12:
                return None
            return characters.Action.ATTACK
        return None

    def pressure_tiles(self, world: WorldState) -> set[coordinates.Coords]:
        threatened: set[coordinates.Coords] = set()
        for enemy in world.enemies.values():
            if world.turn_no - enemy.seen_at > 3:
                continue
            for facing in (enemy.facing, enemy.facing.turn_left(), enemy.facing.turn_right()):
                threatened.update(self.attack_pattern(world, enemy.position, facing, enemy.weapon_name))
        return threatened

    def can_hit(self, enemy: EnemyTrace, victim: coordinates.Coords, world: WorldState) -> bool:
        pattern = self.attack_pattern(world, enemy.position, enemy.facing, enemy.weapon_name)
        return victim in pattern

    def attack_pattern(
        self,
        world: WorldState,
        origin: coordinates.Coords,
        facing: characters.Facing,
        weapon_name: str,
    ) -> list[coordinates.Coords]:
        weapon = weapon_name.split("_")[0]
        if weapon in {"knife", "scroll"}:
            return [origin + facing.value]
        if weapon == "sword":
            return self._line(world, origin, facing, 3)
        if weapon == "bow":
            return self._line(world, origin, facing, 50)
        if weapon == "axe":
            center = origin + facing.value
            return [center + facing.turn_left().value, center, center + facing.turn_right().value]
        if weapon == "amulet":
            return [
                origin + coordinates.Coords(1, 1),
                origin + coordinates.Coords(-1, 1),
                origin + coordinates.Coords(1, -1),
                origin + coordinates.Coords(-1, -1),
                origin + coordinates.Coords(2, 2),
                origin + coordinates.Coords(-2, 2),
                origin + coordinates.Coords(2, -2),
                origin + coordinates.Coords(-2, -2),
            ]
        return [origin + facing.value]

    def _line(
        self,
        world: WorldState,
        origin: coordinates.Coords,
        facing: characters.Facing,
        reach: int,
    ) -> list[coordinates.Coords]:
        cells = []
        pos = origin
        for _ in range(reach):
            pos = pos + facing.value
            if pos not in world.known_terrain:
                break
            cells.append(pos)
            if not world.transparent(pos):
                break
        return cells

    def _threat_weight(self, enemy: EnemyTrace) -> float:
        if enemy.health <= 2:
            return 2.4
        if enemy.health <= 4:
            return 1.8
        return 1.2

from __future__ import annotations

from gupb.model import characters, coordinates

from .worldstate import EnemyTrace, WorldState

WEAPON_DAMAGE = {
    "knife": 2,
    "sword": 2,
    "axe": 3,
    "bow_loaded": 3,
    "bow_unloaded": 0,
    "bow": 3,
    "amulet": 2,
    "scroll": 3,
}

WEAPON_RANK = {
    "knife": 1,
    "amulet": 2,
    "axe": 4,
    "sword": 5,
    "scroll": 5,
    "bow_unloaded": 6,
    "bow_loaded": 7,
    "bow": 7,
}


class CombatEvaluator:
    def should_preload_bow(
        self,
        world: WorldState,
        pressure_tiles: set[coordinates.Coords],
    ) -> bool:
        if world.weapon_name != "bow_unloaded":
            return False
        if world.health <= 3:
            return False
        if (
            world.position in pressure_tiles
            or world.position in world.fire_tiles
            or world.position in world.mist_tiles
            or world.predicted_mist(world.position, 2)
        ):
            return False
        return True

    def can_kill_now(self, world: WorldState) -> bool:
        damage = self.weapon_damage(world.weapon_name, world)
        if damage <= 0:
            return False
        hit_tiles = self.attack_pattern(world, world.position, world.facing, world.weapon_name)
        return any(
            enemy.position in hit_tiles
            and world.turn_no - enemy.seen_at <= 1
            and damage >= enemy.health
            for enemy in world.enemies.values()
        )

    def decide_attack(self, world: WorldState, alive_count: int) -> characters.Action | None:
        hit_tiles = self.attack_pattern(world, world.position, world.facing, world.weapon_name)
        enemies_hit = [enemy for enemy in world.enemies.values() if enemy.position in hit_tiles and world.turn_no - enemy.seen_at <= 1]
        if not enemies_hit:
            return None

        damage = self.weapon_damage(world.weapon_name, world)
        if damage <= 0:
            return None

        if any(damage >= enemy.health for enemy in enemies_hit):
            return characters.Action.ATTACK

        expected = sum(self._threat_weight(enemy) for enemy in enemies_hit) + 0.6 * damage * len(enemies_hit)
        retaliation = 0.0
        for enemy in enemies_hit:
            if self.can_hit(enemy, world.position, world):
                retaliation += self.weapon_damage(enemy.weapon_name, world) + 1.0

        if retaliation >= world.health and alive_count > 2:
            return None

        best_enemy_rank = max(self.weapon_rank(enemy.weapon_name) for enemy in enemies_hit)
        if self.weapon_rank(world.weapon_name) < best_enemy_rank and world.health <= 5:
            expected *= 0.75

        endgame_boost = 1.3 if alive_count <= 4 else 1.0
        if world.health <= 3:
            endgame_boost *= 0.65

        if expected * endgame_boost >= retaliation + 1.0:
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
        if weapon_name == "bow_unloaded":
            return []
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

    def weapon_damage(self, weapon_name: str, world: WorldState) -> int:
        if weapon_name == "scroll" and world.scroll_charges <= 0:
            return 0
        return WEAPON_DAMAGE.get(weapon_name, WEAPON_DAMAGE.get(weapon_name.split("_")[0], 2))

    @staticmethod
    def weapon_rank(weapon_name: str) -> int:
        return WEAPON_RANK.get(weapon_name, WEAPON_RANK.get(weapon_name.split("_")[0], 1))

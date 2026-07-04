from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
import math

from gupb.model import characters
from gupb.model import coordinates

from .features import StrategicContext
from .utils import HAZARD_EFFECT_TYPES, manhattan
from .weapon_info import can_hit, weapon_damage, weapon_rank
from .world_memory import WorldMemory


class EngagementDecision(Enum):
    ENGAGE = auto()
    AVOID = auto()
    SIMULATE = auto()


@dataclass(frozen=True, slots=True)
class EngagementResult:
    decision: EngagementDecision
    score: float
    enemy_position: coordinates.Coords | None
    enemy: characters.ChampionDescription | None
    can_hit_now: bool
    enemy_can_hit_now: bool


class EngagementPolicy:
    def evaluate(self, context: StrategicContext, memory: WorldMemory) -> EngagementResult:
        if not context.visible_enemies:
            return EngagementResult(EngagementDecision.AVOID, -math.inf, None, None, False, False)

        enemy_position, enemy = context.visible_enemies[0]
        my_position = context.position
        my_weapon = context.weapon_name

        character_at = lambda coords_: memory.character_at(coords_, context.knowledge)
        can_hit_now = can_hit(
            my_weapon,
            my_position,
            context.facing,
            enemy_position,
            memory.tile_type_at,
            character_at,
        )
        enemy_can_hit_now = can_hit(
            enemy.weapon.name,
            enemy_position,
            enemy.facing,
            my_position,
            memory.tile_type_at,
            character_at,
        )

        score = 0.0
        if can_hit_now:
            score += 42.0
        if enemy_can_hit_now:
            score -= 38.0

        my_damage = weapon_damage(my_weapon)
        enemy_damage = weapon_damage(enemy.weapon.name)
        if my_damage >= enemy.health and can_hit_now:
            score += 45.0
        if enemy_damage >= context.health and enemy_can_hit_now:
            score -= 50.0

        score += 8.0 * (weapon_rank(my_weapon) - weapon_rank(enemy.weapon.name))
        score += 4.0 * (context.health - enemy.health)

        current_tile = context.knowledge.visible_tiles.get(my_position)
        if current_tile is not None and any(effect.type in HAZARD_EFFECT_TYPES for effect in current_tile.effects):
            score -= 28.0

        if context.health <= 3:
            score -= 32.0
        elif context.health <= 5:
            score -= 12.0

        escape_routes = self._escape_routes(context, memory, enemy_position)
        if escape_routes == 0:
            score -= 24.0
        elif escape_routes == 1:
            score -= 9.0

        if memory.menhir_position is not None:
            my_menhir_distance = manhattan(my_position, memory.menhir_position)
            enemy_menhir_distance = manhattan(enemy_position, memory.menhir_position)
            if my_menhir_distance <= 3:
                score += 8.0
            if (context.mist_positions or context.knowledge.no_of_champions_alive <= 3) and my_menhir_distance > 5:
                score -= 18.0
            if enemy_menhir_distance <= 2 and context.knowledge.no_of_champions_alive <= 3:
                score += 10.0

        if score >= 35.0 and can_hit_now and context.health > 3:
            decision = EngagementDecision.ENGAGE
        elif score <= -28.0 or (context.health <= 3 and not (can_hit_now and my_damage >= enemy.health)):
            decision = EngagementDecision.AVOID
        else:
            decision = EngagementDecision.SIMULATE

        return EngagementResult(decision, score, enemy_position, enemy, can_hit_now, enemy_can_hit_now)

    @staticmethod
    def _escape_routes(
        context: StrategicContext,
        memory: WorldMemory,
        enemy_position: coordinates.Coords,
    ) -> int:
        routes = 0
        for facing in characters.Facing:
            candidate = context.position + facing.value
            if candidate == enemy_position or not memory.is_known_passable(candidate):
                continue
            tile = context.knowledge.visible_tiles.get(candidate)
            if tile is not None and tile.character is not None:
                continue
            routes += 1
        return routes

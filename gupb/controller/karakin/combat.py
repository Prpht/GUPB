from __future__ import annotations

from dataclasses import dataclass
import math
import random
import time

from gupb.model import characters
from gupb.model import coordinates

from .engagement import EngagementResult
from .features import StrategicContext
from .utils import MOVEMENT_ACTIONS, TACTICAL_ACTIONS, effect_types, manhattan, movement_direction, rotated_facing
from .weapon_info import can_hit, weapon_damage, weapon_rank, weapon_ready_to_damage
from .world_memory import WorldMemory


@dataclass(frozen=True, slots=True)
class DuelState:
    my_position: coordinates.Coords
    my_facing: characters.Facing
    my_health: int
    my_weapon_name: str
    enemy_position: coordinates.Coords
    enemy_facing: characters.Facing
    enemy_health: int
    enemy_weapon_name: str


@dataclass(slots=True)
class RootStats:
    visits: int = 0
    total_value: float = 0.0

    @property
    def mean(self) -> float:
        if self.visits == 0:
            return -math.inf
        return self.total_value / float(self.visits)


class CombatAgent:
    def decide(
        self,
        context: StrategicContext,
        memory: WorldMemory,
        engagement: EngagementResult | None = None,
    ) -> characters.Action:
        if not context.visible_enemies:
            return characters.Action.TURN_LEFT
        enemy_position, enemy = context.visible_enemies[0]
        if engagement is not None and engagement.can_hit_now:
            return characters.Action.ATTACK
        if can_hit(
            context.weapon_name,
            context.position,
            context.facing,
            enemy_position,
            memory.tile_type_at,
            lambda c: memory.character_at(c, context.knowledge),
        ):
            return characters.Action.ATTACK
        if context.weapon_name == "bow_unloaded" and manhattan(context.position, enemy_position) >= 3:
            return characters.Action.ATTACK

        if weapon_rank(context.weapon_name) < weapon_rank(enemy.weapon.name) or context.health <= 3:
            retreat = self._best_distance_action(context, memory, enemy_position, increase=True)
            if retreat is not None:
                return retreat

        approach = self._best_distance_action(context, memory, enemy_position, increase=False)
        if approach is not None:
            return approach

        desired_facing = self._facing_towards(context.position, enemy_position)
        if desired_facing == context.facing.turn_left():
            return characters.Action.TURN_LEFT
        if desired_facing == context.facing.turn_right():
            return characters.Action.TURN_RIGHT
        return characters.Action.TURN_RIGHT

    def _best_distance_action(
        self,
        context: StrategicContext,
        memory: WorldMemory,
        enemy_position: coordinates.Coords,
        increase: bool,
    ) -> characters.Action | None:
        best_action: characters.Action | None = None
        best_score = -math.inf
        current_distance = manhattan(context.position, enemy_position)
        for action in MOVEMENT_ACTIONS:
            direction = movement_direction(action, context.facing)
            if direction is None:
                continue
            candidate = context.position + direction
            if not memory.is_known_passable(candidate) or candidate == enemy_position:
                continue
            tile = context.knowledge.visible_tiles.get(candidate)
            if tile is not None and tile.character is not None:
                continue
            distance = manhattan(candidate, enemy_position)
            progress = distance - current_distance if increase else current_distance - distance
            score = float(progress)
            if tile is not None:
                names = effect_types(tile)
                if "mist" in names:
                    score -= 8.0
                if "fire" in names:
                    score -= 12.0
            if score > best_score:
                best_score = score
                best_action = action
        return best_action if best_score > -math.inf else None

    @staticmethod
    def _facing_towards(
        origin: coordinates.Coords,
        target: coordinates.Coords,
    ) -> characters.Facing | None:
        dx = target.x - origin.x
        dy = target.y - origin.y
        if abs(dx) >= abs(dy) and dx != 0:
            return characters.Facing.RIGHT if dx > 0 else characters.Facing.LEFT
        if dy != 0:
            return characters.Facing.DOWN if dy > 0 else characters.Facing.UP
        return None


class CombatMCTS:
    def __init__(
        self,
        time_budget: float = 0.6,
        hard_time_limit: float = 0.8,
        min_rollouts: int = 16,
        max_rollouts: int = 64,
        rollout_depth: int = 6,
        enemy_model: str = "teacher_combat",
        seed: int = 1312,
    ) -> None:
        self.time_budget = time_budget
        self.hard_time_limit = hard_time_limit
        self.min_rollouts = min_rollouts
        self.max_rollouts = max_rollouts
        self.rollout_depth = rollout_depth
        self.enemy_model = enemy_model
        self.rng = random.Random(seed)
        self.last_rollouts = 0
        self.last_elapsed = 0.0

    def decide(
        self,
        context: StrategicContext,
        memory: WorldMemory,
        engagement: EngagementResult,
    ) -> characters.Action | None:
        if engagement.enemy_position is None or engagement.enemy is None:
            return None

        initial_state = DuelState(
            my_position=context.position,
            my_facing=context.facing,
            my_health=context.health,
            my_weapon_name=context.weapon_name,
            enemy_position=engagement.enemy_position,
            enemy_facing=engagement.enemy.facing,
            enemy_health=engagement.enemy.health,
            enemy_weapon_name=engagement.enemy.weapon.name,
        )
        root_actions = self._legal_actions(initial_state, "me", context, memory)
        if not root_actions:
            return None

        start = time.monotonic()
        soft_deadline = start + self.time_budget
        hard_deadline = start + self.hard_time_limit
        stats = {action: RootStats() for action in root_actions}
        rollouts = 0

        while rollouts < self.max_rollouts:
            now = time.monotonic()
            if now >= hard_deadline:
                break
            if rollouts >= self.min_rollouts and now >= soft_deadline:
                break
            action = self._select_ucb(stats)
            state_after_action = self._apply_action(initial_state, action, "me", context, memory)
            value = self._rollout(
                state_after_action,
                context,
                memory,
                depth_left=self.rollout_depth - 1,
                deadline=hard_deadline,
            )
            stats[action].visits += 1
            stats[action].total_value += value
            rollouts += 1

        self.last_rollouts = rollouts
        self.last_elapsed = time.monotonic() - start
        reliable_actions = {action: stat for action, stat in stats.items() if stat.visits > 0}
        if rollouts < self.min_rollouts or not reliable_actions:
            return None
        best_action, best_stats = max(reliable_actions.items(), key=lambda item: item[1].mean)
        if best_stats.mean < -120.0:
            return None
        return best_action

    def _select_ucb(self, stats: dict[characters.Action, RootStats]) -> characters.Action:
        unvisited = [action for action, stat in stats.items() if stat.visits == 0]
        if unvisited:
            return self.rng.choice(unvisited)
        total_visits = sum(stat.visits for stat in stats.values())
        return max(
            stats,
            key=lambda action: stats[action].mean + 1.2 * math.sqrt(math.log(total_visits + 1) / stats[action].visits),
        )

    def _rollout(
        self,
        state: DuelState,
        context: StrategicContext,
        memory: WorldMemory,
        depth_left: int,
        deadline: float,
    ) -> float:
        current = state
        actor = "enemy"
        for _ in range(depth_left):
            if time.monotonic() >= deadline:
                break
            if current.my_health <= 0 or current.enemy_health <= 0:
                break
            action = self._rollout_action(current, actor, context, memory)
            current = self._apply_action(current, action, actor, context, memory)
            actor = "me" if actor == "enemy" else "enemy"
        return self._state_value(current, state, context, memory)

    def _rollout_action(
        self,
        state: DuelState,
        actor: str,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> characters.Action:
        legal = self._legal_actions(state, actor, context, memory)
        if not legal:
            return characters.Action.DO_NOTHING
        if actor == "enemy" and self.enemy_model == "random_legal":
            return self.rng.choice(legal)
        return max(legal, key=lambda action: self._one_ply_value(state, action, actor, context, memory))

    def _one_ply_value(
        self,
        state: DuelState,
        action: characters.Action,
        actor: str,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> float:
        new_state = self._apply_action(state, action, actor, context, memory)
        if actor == "me":
            return self._state_value(new_state, state, context, memory)
        return -self._state_value(new_state, state, context, memory)

    def _legal_actions(
        self,
        state: DuelState,
        actor: str,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> list[characters.Action]:
        actions: list[characters.Action] = []
        for action in TACTICAL_ACTIONS:
            if action == characters.Action.ATTACK:
                weapon_name = state.my_weapon_name if actor == "me" else state.enemy_weapon_name
                can_attack = weapon_ready_to_damage(weapon_name) or weapon_name == "bow_unloaded"
                if can_attack:
                    actions.append(action)
                continue
            if action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT):
                actions.append(action)
                continue
            if self._movement_destination(state, action, actor, memory) is not None:
                actions.append(action)
        return actions

    def _movement_destination(
        self,
        state: DuelState,
        action: characters.Action,
        actor: str,
        memory: WorldMemory,
    ) -> coordinates.Coords | None:
        facing = state.my_facing if actor == "me" else state.enemy_facing
        position = state.my_position if actor == "me" else state.enemy_position
        occupied = state.enemy_position if actor == "me" else state.my_position
        direction = movement_direction(action, facing)
        if direction is None:
            return None
        destination = position + direction
        if destination == occupied or not memory.is_known_passable(destination):
            return None
        return destination

    def _apply_action(
        self,
        state: DuelState,
        action: characters.Action,
        actor: str,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> DuelState:
        my_position = state.my_position
        my_facing = state.my_facing
        my_health = state.my_health
        my_weapon_name = state.my_weapon_name
        enemy_position = state.enemy_position
        enemy_facing = state.enemy_facing
        enemy_health = state.enemy_health
        enemy_weapon_name = state.enemy_weapon_name

        if actor == "me":
            if action == characters.Action.ATTACK:
                if my_weapon_name == "bow_unloaded":
                    my_weapon_name = "bow_loaded"
                elif can_hit(
                    my_weapon_name,
                    my_position,
                    my_facing,
                    enemy_position,
                    memory.tile_type_at,
                    self._character_at(my_position, enemy_position, context, memory),
                ):
                    enemy_health -= weapon_damage(my_weapon_name)
                    if my_weapon_name == "bow_loaded":
                        my_weapon_name = "bow_unloaded"
            elif action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT):
                my_facing = rotated_facing(action, my_facing)
            else:
                destination = self._movement_destination(state, action, actor, memory)
                if destination is not None:
                    my_position = destination
                    my_health -= self._hazard_damage(my_position, context)
        else:
            if action == characters.Action.ATTACK:
                if enemy_weapon_name == "bow_unloaded":
                    enemy_weapon_name = "bow_loaded"
                elif can_hit(
                    enemy_weapon_name,
                    enemy_position,
                    enemy_facing,
                    my_position,
                    memory.tile_type_at,
                    self._character_at(my_position, enemy_position, context, memory),
                ):
                    my_health -= weapon_damage(enemy_weapon_name)
                    if enemy_weapon_name == "bow_loaded":
                        enemy_weapon_name = "bow_unloaded"
            elif action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT):
                enemy_facing = rotated_facing(action, enemy_facing)
            else:
                destination = self._movement_destination(state, action, actor, memory)
                if destination is not None:
                    enemy_position = destination
                    enemy_health -= self._hazard_damage(enemy_position, context)

        return DuelState(
            my_position=my_position,
            my_facing=my_facing,
            my_health=my_health,
            my_weapon_name=my_weapon_name,
            enemy_position=enemy_position,
            enemy_facing=enemy_facing,
            enemy_health=enemy_health,
            enemy_weapon_name=enemy_weapon_name,
        )

    @staticmethod
    def _character_at(
        my_position: coordinates.Coords,
        enemy_position: coordinates.Coords,
        context: StrategicContext,
        memory: WorldMemory,
    ):
        local_character = object()

        def character_at(coords_: coordinates.Coords):
            if coords_ == my_position or coords_ == enemy_position:
                return local_character
            return memory.character_at(coords_, context.knowledge)

        return character_at

    @staticmethod
    def _hazard_damage(
        position: coordinates.Coords,
        context: StrategicContext,
    ) -> int:
        tile = context.knowledge.visible_tiles.get(position)
        if tile is None:
            return 0
        damage = 0
        names = effect_types(tile)
        if "mist" in names:
            damage += 1
        if "fire" in names:
            damage += 3
        return damage

    def _state_value(
        self,
        state: DuelState,
        initial_state: DuelState,
        context: StrategicContext,
        memory: WorldMemory,
    ) -> float:
        if state.enemy_health <= 0:
            return 1000.0 + 20.0 * state.my_health
        if state.my_health <= 0:
            return -1000.0 - 20.0 * state.enemy_health

        damage_dealt = initial_state.enemy_health - state.enemy_health
        damage_taken = initial_state.my_health - state.my_health
        value = 38.0 * damage_dealt - 48.0 * damage_taken
        value += 8.0 * (weapon_rank(state.my_weapon_name) - weapon_rank(state.enemy_weapon_name))
        distance = manhattan(state.my_position, state.enemy_position)
        if weapon_rank(state.my_weapon_name) >= weapon_rank(state.enemy_weapon_name):
            value -= 2.0 * distance
        else:
            value += 4.0 * distance

        if memory.menhir_position is not None and (context.mist_positions or context.knowledge.no_of_champions_alive <= 3):
            initial_menhir_distance = manhattan(initial_state.my_position, memory.menhir_position)
            final_menhir_distance = manhattan(state.my_position, memory.menhir_position)
            value += 6.0 * (initial_menhir_distance - final_menhir_distance)
        value -= 10.0 * self._hazard_damage(state.my_position, context)
        return value

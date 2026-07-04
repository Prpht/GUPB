from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from gupb import controller
from gupb.model import arenas
from gupb.model import characters

from .combat import CombatAgent, CombatMCTS
from .engagement import EngagementDecision, EngagementPolicy, EngagementResult
from .features import FEATURE_VECTOR_SIZE, StrategicContext, build_context
from .navigator import Navigator
from .strategy import HeuristicStrategicPolicy, PPOStrategicPolicy, StrategicMode
from .utils import MOVEMENT_ACTIONS, effect_types, manhattan, movement_direction
from .weapon_info import weapon_damage
from .world_memory import WorldMemory


class KarakinController(controller.Controller):
    def __init__(
        self,
        first_name: str = "Karakin",
        *,
        use_sb3: bool = True,
        model_path: str | Path | None = None,
        mcts_time_budget: float = 0.6,
        mcts_hard_time_limit: float = 0.8,
        enemy_model: str = "teacher_combat",
        decision_time_budget: float = 1.0,
        **legacy_sarsa_kwargs: Any,
    ) -> None:
        self.first_name = first_name
        self.use_sb3 = use_sb3
        self.decision_time_budget = decision_time_budget
        self._legacy_sarsa_kwargs = legacy_sarsa_kwargs

        self.memory = WorldMemory()
        self.ppo_policy = PPOStrategicPolicy(model_path=model_path, enabled=use_sb3)
        self.heuristic_policy = HeuristicStrategicPolicy()
        self.engagement_policy = EngagementPolicy()
        self.combat_agent = CombatAgent()
        self.combat_mcts = CombatMCTS(
            time_budget=mcts_time_budget,
            hard_time_limit=mcts_hard_time_limit,
            enemy_model=enemy_model,
        )
        self.navigator = Navigator()

        self._forced_mode: StrategicMode | None = None
        self.latest_features = None
        self.latest_mode: StrategicMode | None = None
        self.latest_health: int | None = None
        self.decision_counter = 0
        self.last_decision_elapsed = 0.0
        self._prepared_context: StrategicContext | None = None
        self._prepared_signature: tuple | None = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KarakinController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def eval(self) -> KarakinController:
        self.use_sb3 = True
        self.ppo_policy.enabled = True
        return self

    def force_mode(self, mode: StrategicMode | int | None) -> None:
        self._forced_mode = None if mode is None else StrategicMode(int(mode))

    def observe(self, knowledge: characters.ChampionKnowledge):
        context = self._context_from_knowledge(knowledge)
        if context is None:
            return None
        self._store_latest_context(context)
        self._prepared_context = context
        self._prepared_signature = self._knowledge_signature(knowledge)
        return context.features.copy()

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        started_at = time.monotonic()
        try:
            context = self._prepared_context_for(knowledge)
            if context is None:
                return characters.Action.TURN_LEFT

            self._store_latest_context(context)
            self.decision_counter += 1

            mode = self._select_mode(context)
            self.latest_mode = mode
            action = self._action_for_mode(mode, context)
            action = self._safety_mask(action, context)
            self.memory.last_health = context.health
            return action
        except Exception as exc:
            print(f"Error in KarakinController.decide: {exc}")
            return characters.Action.TURN_LEFT
        finally:
            self.last_decision_elapsed = time.monotonic() - started_at

    def _prepared_context_for(self, knowledge: characters.ChampionKnowledge) -> StrategicContext | None:
        signature = self._knowledge_signature(knowledge)
        if self._prepared_signature == signature and self._prepared_context is not None:
            context = self._prepared_context
            self._prepared_signature = None
            self._prepared_context = None
            return context
        return self._context_from_knowledge(knowledge)

    def _context_from_knowledge(self, knowledge: characters.ChampionKnowledge) -> StrategicContext | None:
        self.memory.update(knowledge, self.name)
        return build_context(knowledge, self.memory, self.name)

    def _store_latest_context(self, context: StrategicContext) -> None:
        self.latest_features = context.features.copy()
        self.latest_health = context.health

    @staticmethod
    def _knowledge_signature(knowledge: characters.ChampionKnowledge) -> tuple:
        visible_signature = []
        for coords_, tile in sorted(knowledge.visible_tiles.items()):
            character = tile.character
            character_signature = None
            if character is not None:
                character_signature = (
                    character.controller_name,
                    character.health,
                    character.weapon.name,
                    character.facing,
                )
            visible_signature.append(
                (
                    coords_,
                    tile.type,
                    tile.loot.name if tile.loot is not None else None,
                    character_signature,
                    tile.consumable.name if tile.consumable is not None else None,
                    tuple(effect.type for effect in tile.effects),
                )
            )
        return knowledge.position, knowledge.no_of_champions_alive, tuple(visible_signature)

    def _select_mode(self, context: StrategicContext) -> StrategicMode:
        if self._forced_mode is not None:
            mode = self._forced_mode
            self._forced_mode = None
            return mode

        mode = self.ppo_policy.predict(context.features) if self.use_sb3 else None
        if mode is not None:
            return mode
        return self.heuristic_policy.select(context, self.memory)

    def _action_for_mode(
        self,
        mode: StrategicMode,
        context: StrategicContext,
    ) -> characters.Action:
        engagement = self.engagement_policy.evaluate(context, self.memory)
        combat_pressure = bool(context.visible_enemies) or mode == StrategicMode.FIGHT

        if self._hazard_escape_needed(context) and not self._has_immediate_lethal_attack(context, engagement):
            escape = self.navigator.hazard_escape_action(context, self.memory)
            if escape is not None:
                return escape.action

        if combat_pressure and engagement.enemy_position is not None:
            if engagement.decision == EngagementDecision.ENGAGE:
                return self.combat_agent.decide(context, self.memory, engagement)

            if engagement.decision == EngagementDecision.SIMULATE or mode == StrategicMode.FIGHT:
                simulated = self.combat_mcts.decide(context, self.memory, engagement)
                if simulated is not None:
                    return simulated
                if mode == StrategicMode.FIGHT and engagement.score > -20.0:
                    return self.combat_agent.decide(context, self.memory, engagement)

            if engagement.decision == EngagementDecision.AVOID:
                mode = StrategicMode.RETREAT

        return self.navigator.action_for_mode(mode, context, self.memory).action

    def _hazard_escape_needed(self, context: StrategicContext) -> bool:
        current_tile = context.knowledge.visible_tiles.get(context.position)
        current_effects = effect_types(current_tile)
        if "fire" in current_effects or "mist" in current_effects:
            return True

        if not context.mist_positions:
            return False
        nearest_mist = min(manhattan(context.position, mist) for mist in context.mist_positions)
        if context.health <= 4 and nearest_mist <= 2:
            return True
        if self.memory.menhir_position is not None and nearest_mist <= 1:
            return True
        return False

    @staticmethod
    def _has_immediate_lethal_attack(
        context: StrategicContext,
        engagement: EngagementResult,
    ) -> bool:
        if not getattr(engagement, "can_hit_now", False):
            return False
        enemy = getattr(engagement, "enemy", None)
        return bool(enemy is not None and weapon_damage(context.weapon_name) >= enemy.health)

    def _safety_mask(
        self,
        action: characters.Action,
        context: StrategicContext,
    ) -> characters.Action:
        if action not in MOVEMENT_ACTIONS:
            return action
        if self._movement_is_safe(action, context):
            return action

        for fallback in MOVEMENT_ACTIONS:
            if self._movement_is_safe(fallback, context):
                return fallback
        return characters.Action.TURN_LEFT

    def _movement_is_safe(
        self,
        action: characters.Action,
        context: StrategicContext,
    ) -> bool:
        direction = movement_direction(action, context.facing)
        if direction is None:
            return False
        destination = context.position + direction
        if not self.memory.is_known_passable(destination):
            return False
        tile = context.knowledge.visible_tiles.get(destination)
        if tile is not None and tile.character is not None:
            return False
        if tile is not None:
            names = effect_types(tile)
            if "fire" in names:
                return False
            if "mist" in names and context.health <= 3:
                return False
        else:
            if destination in self.memory.known_fire_positions:
                return False
            if destination in self.memory.known_mist_positions and context.health <= 3:
                return False
        return True

    def praise(self, score: int) -> None:
        return None

    def die(self) -> None:
        return None

    def win(self) -> None:
        return None

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.memory.reset(arena_description)
        self._forced_mode = None
        self.latest_features = None
        self.latest_mode = None
        self.latest_health = None
        self.decision_counter = 0
        self.last_decision_elapsed = 0.0
        self._prepared_context = None
        self._prepared_signature = None

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KARAKIN


ZERO_FEATURES = [0.0] * FEATURE_VECTOR_SIZE

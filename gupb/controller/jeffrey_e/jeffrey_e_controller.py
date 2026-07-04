from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
import heapq
import math
import os
import random
from typing import Any, Collection, NamedTuple

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model.profiling import profile as base_profile

CoordsLike = coordinates.Coords | tuple[int, int]

PASSABLE_TILE_TYPES = {"land", "forest", "menhir"}
TRANSPARENT_TILE_TYPES = {"land", "sea", "menhir"}

CARDINAL_DIRECTIONS = (
    coordinates.Coords(0, -1),
    coordinates.Coords(1, 0),
    coordinates.Coords(0, 1),
    coordinates.Coords(-1, 0),
)

MOVEMENT_ACTIONS = (
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.STEP_BACKWARD,
)

ALL_ACTIONS = (
    characters.Action.ATTACK,
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.STEP_BACKWARD,
)

WEAPON_PRIORITY = {
    "knife": 1,
    "scroll": 2,
    "amulet": 4,
    "sword": 5,
    "axe": 6,
    "bow_unloaded": 7,
    "bow_loaded": 8,
}

WEAPON_DAMAGE = {
    "knife": 2,
    "sword": 2,
    "bow_loaded": 3,
    "bow_unloaded": 0,
    "axe": 3,
    "amulet": 2,
    "scroll": 3,
}

WEAPON_REACH = {
    "knife": 1,
    "sword": 3,
    "scroll": 1,
    "bow_loaded": 50,
    "bow_unloaded": 50,
}

WEAPON_BASE_BY_NAME = {
    "knife": "knife",
    "sword": "sword",
    "axe": "axe",
    "amulet": "amulet",
    "scroll": "scroll",
    "bow": "bow",
    "bow_loaded": "bow",
    "bow_unloaded": "bow",
}

WEAPON_PRIORITY_BY_NAME = {
    **WEAPON_PRIORITY,
    "bow": WEAPON_PRIORITY["bow_loaded"],
}

WEAPON_DAMAGE_BY_NAME = {
    **WEAPON_DAMAGE,
    "bow": WEAPON_DAMAGE["bow_loaded"],
}

WEAPON_REACH_BY_NAME = {
    **WEAPON_REACH,
    "bow": WEAPON_REACH["bow_loaded"],
}

MIST_TILE_PENALTY = 18
FIRE_TILE_PENALTY = 70

COMBAT_MINIMAX_DEPTH = 3
COMBAT_MINIMAX_BRANCHING = 4
COMBAT_MINIMAX_TRIGGER_DISTANCE = 7

COMBAT_MCTS_ITERATIONS = 144
COMBAT_MCTS_ROLLOUT_DEPTH = 6
COMBAT_MCTS_ACTION_WIDTH = 5
COMBAT_MCTS_EXPLORATION = 1.15
COMBAT_MCTS_TRIGGER_DISTANCE = 3

MIST_CLOSE_DISTANCE = 3
MIST_CRITICAL_DISTANCE = 2
MENHIR_ENDGAME_ALIVE_TRIGGER = 2
MENHIR_ENDGAME_ATTRACTION = 1.1
MENHIR_MIST_ATTRACTION = 0.6
MENHIR_STANDOFF_DISTANCE = 3.0
MENHIR_STANDOFF_BAND = 2.0

KILL_POTION_TARGET_TTL = 7
EXPLORATION_MIN_DISTANCE = 6
EXPLORATION_CANDIDATES = 10
EXPLORATION_SCAN_INTERVAL = 3
EXPLORATION_SCAN_INITIAL_DELAY = 5
ENEMY_MEMORY_TURNS = 10

STEP_COST_BASE = 1.0
STEP_COST_MIST = 50.0
STEP_COST_FIRE = 14.0
STEP_COST_ENEMY_ADJACENT = 15.0
STEP_COST_ENEMY_NEAR = 8.0

MIST_TEMPORAL_SCALE_PER_100_TURNS = 1.0
LOW_HP_MIST_COST_MULTIPLIER = 2.0
MIST_VECTOR_TOWARD_PENALTY = 20.0
MIST_VECTOR_AWAY_BONUS = 5.0
MENHIR_PATH_MIST_TRIGGER_DISTANCE = 5
MENHIR_PATH_PROGRESS_REWARD = 0.2
TARGET_MIST_SAFETY_MARGIN = 2

SHADOW_MEMORY_MAX_TURNS = 5
SHADOW_PRESSURE_BASE = 60.0
SHADOW_PRESSURE_RADIUS_PER_TURN = 1
SHADOW_PRESSURE_MIN_SCALE = 0.35

REACTIVE_SCAN_COOLDOWN = 4
BACK_EXPOSURE_STEP_PENALTY = 3.0
UNSEEN_DAMAGE_PANIC_BONUS = 50.0

ENDGAME_MIST_NEAR_DISTANCE = 5
ENDGAME_MIST_PROXIMITY_PENALTY = 15.0

RANGED_WEAPON_PRESSURE_MULTIPLIER = 1.3
MID_RANGE_WEAPON_PRESSURE_MULTIPLIER = 1.1

DIAGONAL_LINEAR_WEAPON_BONUS = 8.0
DIAGONAL_BOW_SECOND_RING_BONUS = 3.0

LOOT_RANK_GAIN_SCALE = 42.0
LOOT_DISTANCE_COST = 2.2
LOOT_SMALL_GAIN_HYSTERESIS = 14.0

ROLLOUT_EPSILON_SIDE_STEP_PROB = 0.15

BOW_UNLOADED_CLOSE_RANGE_PANIC_DISTANCE = 2
BOW_UNLOADED_LOW_HP_RELOAD_PENALTY = 85.0
MIST_HARD_VETO_PENALTY = 500.0
MIST_STAY_PENALTY = 140.0

BOW_KITE_MIN_DISTANCE_LOADED = 3
BOW_KITE_MIN_DISTANCE_UNLOADED = 4
BOW_KITE_MAX_DISTANCE = 6
BOW_KITE_STANDOFF_BONUS = 24.0
BOW_KITE_CLOSE_RANGE_PENALTY = 28.0
BOW_KITE_TOO_FAR_PENALTY = 7.5

EXPLORE_TURN_PENALTY = 0.0
NON_COMBAT_TURN_PENALTY = 2.0
EXPLORE_FACING_BONUS = 45.0

SETUP_TURN_THREAT_SCALE = 0.6
SETUP_TURN_THREAT_ADJACENT_SCALE = 0.4
ATTACK_ACTION_PRESSURE_DISCOUNT = 0.3
MENHIR_COMBAT_ATTACK_BONUS = 150.0


ENABLE_JEFFREY_PROFILING = os.getenv("GUPB_JEFFREY_PROFILE", "0").lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def optional_profile(name: str):
    if not ENABLE_JEFFREY_PROFILING:
        def passthrough(func):
            return func

        return passthrough
    return base_profile(name=name)


@dataclass(frozen=True, slots=True)
class HeuristicWeights:
    danger_delta_scale: float = 1.2
    attack_scale: float = 1.0
    enemy_distance_scale: float = 1.0
    target_distance_scale: float = 1.0
    mobility_scale: float = 1.0
    lookahead_penalty_scale: float = 0.8
    stay_still_penalty: float = 110.0
    recent_visit_penalty: float = 22.0


class SimulatedState(NamedTuple):
    position: coordinates.Coords
    facing: characters.Facing
    moved: bool
    weapon_name: str


class DuelState(NamedTuple):
    my_position: coordinates.Coords
    my_facing: characters.Facing
    my_health: int
    my_weapon_name: str
    enemy_position: coordinates.Coords
    enemy_facing: characters.Facing
    enemy_health: int
    enemy_weapon_name: str


@dataclass(slots=True)
class MCTSNode:
    state: DuelState
    actor: str
    parent: MCTSNode | None
    action_from_parent: characters.Action | None
    untried_actions: list[characters.Action]
    visits: int = 0
    total_value: float = 0.0
    children: dict[characters.Action, MCTSNode] = field(default_factory=dict)


class JeffreyEController(controller.Controller):
    def __init__(
        self,
        first_name: str = "JeffreyE",
        use_minimax: bool = False,
        use_mcts: bool = True,
        minimax_bonus_scale: float = 0.0,
        mcts_bonus_scale: float = 0.30,
        heuristic_weights: dict[str, float] | None = None,
    ):
        self.first_name: str = first_name
        _ = use_minimax
        _ = minimax_bonus_scale
        self._use_minimax: bool = False
        self._use_mcts: bool = use_mcts
        self._minimax_bonus_scale: float = 0.0
        self._mcts_bonus_scale: float = mcts_bonus_scale

        defaults = asdict(HeuristicWeights())
        if heuristic_weights:
            for key, value in heuristic_weights.items():
                if key in defaults:
                    defaults[key] = float(value)
        self._heuristic_weights = HeuristicWeights(**defaults)

        self._known_tile_type: dict[coordinates.Coords, str] = {}
        self._known_loot: dict[coordinates.Coords, str] = {}
        self._known_consumables: dict[coordinates.Coords, str] = {}
        self._menhir_position: coordinates.Coords | None = None

        self._recent_positions: deque[coordinates.Coords] = deque(maxlen=12)
        self._last_known_enemies: dict[str, tuple[coordinates.Coords, int]] = {}
        self._previous_visible_enemies: dict[str, coordinates.Coords] = {}
        self._kill_potion_target: coordinates.Coords | None = None
        self._kill_potion_target_until_turn: int = 0
        self._last_scan_turn: int = 0
        self._scan_left_next: bool = True
        self._last_health: int | None = None
        self._reactive_scan_remaining: int = 0
        self._reactive_scan_left_first: bool = True
        self._last_reactive_scan_turn: int = 0

        self._turn_no: int = 0
        self._games_played: int = 0
        self._rng = random.Random(1312)
        self._cut_positions_cache_turn: int = -1
        self._cut_positions_cache: dict[tuple[str, coordinates.Coords, characters.Facing, bool], tuple[coordinates.Coords, ...]] = {}
        self._duel_state_value_cache: dict[DuelState, float] = {}
        self._mcts_root: MCTSNode | None = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, JeffreyEController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def _commit_decision_state(
        self,
        position: coordinates.Coords,
        my_health: int,
        action: characters.Action,
    ) -> characters.Action:
        self._recent_positions.append(position)
        self._last_health = my_health
        return action

    @optional_profile(name="JeffreyE.decide")
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self._turn_no += 1
        self._cut_positions_cache_turn = self._turn_no
        self._cut_positions_cache.clear()
        self._duel_state_value_cache.clear()
        self._memorise_tiles(knowledge)
        self._decay_tracked_enemies()

        self_desc = self._self_description(knowledge)
        if self_desc is None:
            self._last_health = None
            self._mcts_root = None
            return characters.Action.ATTACK

        position = knowledge.position
        facing = self_desc.facing
        my_health = self_desc.health
        my_weapon_name = self_desc.weapon.name
        visible_enemies = self._visible_enemies(knowledge)
        self._update_kill_potion_target(knowledge, visible_enemies)
        mist_positions = self._visible_mist_positions(knowledge)
        mist_distance_lookup = self._mist_distance_lookup(mist_positions)
        policy_mode = self._policy_mode(knowledge, my_health, my_weapon_name, visible_enemies)
        if not (self._use_mcts and policy_mode == "combat" and len(visible_enemies) == 1):
            self._mcts_root = None

        if self._last_health is not None and my_health < self._last_health and not visible_enemies:
            self._reactive_scan_remaining = 2
            panic_action = self._reactive_damage_action(
                position=position,
                facing=facing,
                my_health=my_health,
                my_weapon_name=my_weapon_name,
                knowledge=knowledge,
                mist_positions=mist_positions,
            )
            return self._commit_decision_state(position, my_health, panic_action)

        if self._should_force_attack(position, facing, my_weapon_name, my_health, knowledge, visible_enemies):
            return self._commit_decision_state(position, my_health, characters.Action.ATTACK)

        reactive_scan_action = self._reactive_scan_action(
            knowledge=knowledge,
            position=position,
            facing=facing,
            policy_mode=policy_mode,
            visible_enemies=visible_enemies,
        )
        if reactive_scan_action is not None:
            return self._commit_decision_state(position, my_health, reactive_scan_action)

        scan_action = self._exploration_scan_action(
            knowledge=knowledge,
            position=position,
            facing=facing,
            policy_mode=policy_mode,
            visible_enemies=visible_enemies,
        )
        if scan_action is not None:
            return self._commit_decision_state(position, my_health, scan_action)

        objective_targets = self._choose_objective_targets(
            knowledge,
            my_health,
            my_weapon_name,
            visible_enemies,
            mist_positions,
        )
        blocked_positions = {enemy_position for enemy_position, _ in visible_enemies}
        blocked_positions.discard(position)

        candidate_actions, simulated_actions = self._candidate_actions(
            position=position,
            facing=facing,
            my_weapon_name=my_weapon_name,
            knowledge=knowledge,
            blocked_positions=blocked_positions,
            visible_enemies=visible_enemies,
        )

        query_positions: set[coordinates.Coords] = {position}
        for simulated in simulated_actions.values():
            query_positions.add(simulated.position)

        enemy_pressure_map = self._enemy_pressure_map(knowledge, visible_enemies, position)
        distance_map = self._distance_map(
            targets=objective_targets,
            blocked_positions=blocked_positions,
            knowledge=knowledge,
            visible_enemies=visible_enemies,
            mist_positions=mist_positions,
            mist_distance_lookup=mist_distance_lookup,
            query_positions=query_positions,
            agent_position=position,
            my_health=my_health,
        )

        candidate_scores: dict[characters.Action, float] = {
            action: -1_000_000.0 for action in ALL_ACTIONS
        }
        current_danger_penalty = self._danger_penalty(
            position,
            knowledge,
            visible_enemies,
            my_health,
            my_weapon_name,
        )
        for action in candidate_actions:
            simulated = simulated_actions[action]
            candidate_scores[action] = self._score_action(
                action=action,
                simulated=simulated,
                knowledge=knowledge,
                my_health=my_health,
                my_weapon_name=my_weapon_name,
                visible_enemies=visible_enemies,
                distance_map=distance_map,
                blocked_positions=blocked_positions,
                current_position=position,
                current_facing=facing,
                policy_mode=policy_mode,
                mist_positions=mist_positions,
                enemy_pressure_map=enemy_pressure_map,
                current_danger_penalty=current_danger_penalty,
            )

        if policy_mode == "combat" and len(visible_enemies) == 1:
            enemy_position, enemy_description = visible_enemies[0]
            enemy_distance = self._manhattan(position, enemy_position)
            if self._use_mcts and enemy_distance <= COMBAT_MCTS_TRIGGER_DISTANCE:
                mcts_bonuses = self._combat_mcts_bonuses(
                    knowledge=knowledge,
                    my_position=position,
                    my_facing=facing,
                    my_health=my_health,
                    my_weapon_name=my_weapon_name,
                    enemy_position=enemy_position,
                    enemy_description=enemy_description,
                    candidate_scores=candidate_scores,
                )
                for action, bonus in mcts_bonuses.items():
                    candidate_scores[action] += bonus
            else:
                self._mcts_root = None

        best_score = max(candidate_scores.values())
        best_actions = [action for action, score in candidate_scores.items() if score == best_score]
        chosen_action = self._rng.choice(best_actions)
        return self._commit_decision_state(position, my_health, chosen_action)

    def praise(self, score: int) -> None:
        return None

    def die(self) -> None:
        return None

    def win(self) -> None:
        return None

    def training_summary(self) -> dict[str, Any]:
        return {
            "name": self.first_name,
            "games_played": self._games_played,
            "use_minimax": self._use_minimax,
            "use_mcts": self._use_mcts,
            "minimax_bonus_scale": self._minimax_bonus_scale,
            "mcts_bonus_scale": self._mcts_bonus_scale,
            "heuristic_weights": asdict(self._heuristic_weights),
        }

    def current_heuristic_weights(self) -> dict[str, float]:
        return asdict(self._heuristic_weights)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._known_tile_type.clear()
        self._known_loot.clear()
        self._known_consumables.clear()
        self._recent_positions.clear()
        self._last_known_enemies.clear()
        self._previous_visible_enemies.clear()
        self._kill_potion_target = None
        self._kill_potion_target_until_turn = 0
        self._last_scan_turn = 0
        self._scan_left_next = True
        self._last_health = None
        self._reactive_scan_remaining = 0
        self._reactive_scan_left_first = True
        self._last_reactive_scan_turn = 0
        self._turn_no = 0
        self._games_played += 1
        self._duel_state_value_cache.clear()
        self._mcts_root = None

        self._menhir_position = arenas.FIXED_MENHIRS.get(arena_description.name)
        self._preload_arena_knowledge(arena_description.name)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.JEFFREY_E

    def _preload_arena_knowledge(self, arena_name: str) -> None:
        try:
            arena = arenas.Arena.load(arena_name)
            for coords_, tile in arena.terrain.items():
                tile_type = tile.__class__.__name__.lower()
                self._known_tile_type[coords_] = tile_type
                if tile.loot is not None:
                    self._known_loot[coords_] = tile.loot.description().name
                if tile.consumable is not None:
                    self._known_consumables[coords_] = tile.consumable.description().name
        except Exception:
            pass

    def _memorise_tiles(self, knowledge: characters.ChampionKnowledge) -> None:
        for raw_coords, tile in knowledge.visible_tiles.items():
            coords_ = self._to_coords(raw_coords)
            self._known_tile_type[coords_] = tile.type

            if tile.loot is None:
                self._known_loot.pop(coords_, None)
            else:
                self._known_loot[coords_] = tile.loot.name

            if tile.consumable is None:
                self._known_consumables.pop(coords_, None)
            else:
                self._known_consumables[coords_] = tile.consumable.name

            if tile.type == "menhir":
                self._menhir_position = coords_

    def _self_description(
        self,
        knowledge: characters.ChampionKnowledge,
    ) -> characters.ChampionDescription | None:
        own_tile = self._tile_from_visible(knowledge.position, knowledge.visible_tiles)
        return own_tile.character if own_tile else None

    def _visible_enemies(
        self,
        knowledge: characters.ChampionKnowledge,
    ) -> list[tuple[coordinates.Coords, characters.ChampionDescription]]:
        enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]] = []
        for raw_coords, tile in knowledge.visible_tiles.items():
            coords_ = self._to_coords(raw_coords)
            if tile.character is None:
                continue
            if tile.character.controller_name == self.name:
                continue
            if tile.type == "menhir" or coords_ == self._menhir_position:
                continue

            enemies.append((coords_, tile.character))
            self._last_known_enemies[tile.character.controller_name] = (coords_, self._turn_no)
        return enemies

    def _should_force_attack(
        self,
        position: coordinates.Coords,
        facing: characters.Facing,
        weapon_name: str,
        my_health: int,
        knowledge: characters.ChampionKnowledge,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
    ) -> bool:
        if not visible_enemies:
            return False
        enemy_positions = {coords_ for coords_, _ in visible_enemies}
        threatened = self._weapon_cut_positions(weapon_name, position, facing, knowledge.visible_tiles)
        return any(coords_ in enemy_positions for coords_ in threatened)

    def _choose_objective_targets(
        self,
        knowledge: characters.ChampionKnowledge,
        my_health: int,
        my_weapon_name: str,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
        mist_positions: list[coordinates.Coords],
    ) -> set[coordinates.Coords]:
        kill_potion_target = self._current_kill_potion_target(knowledge.position)
        if kill_potion_target is not None:
            if self._is_safe_target(kill_potion_target, mist_positions):
                return {kill_potion_target}
            if self._menhir_position is not None:
                return {self._menhir_position}

        visible_potion_targets = {
            self._to_coords(raw_coords)
            for raw_coords, tile in knowledge.visible_tiles.items()
            if tile.consumable is not None and tile.consumable.name == "potion"
        }
        if visible_potion_targets:
            return self._safe_targets_or_menhir(visible_potion_targets, mist_positions)

        if my_health <= 5:
            potion_targets = {coords_ for coords_, name in self._known_consumables.items() if name == "potion"}
            if potion_targets:
                return self._safe_targets_or_menhir(potion_targets, mist_positions)

        if visible_enemies:
            return {coords_ for coords_, _ in visible_enemies}

        own_weapon_rank = self._weapon_rank(my_weapon_name)
        better_weapon_targets = {
            coords_
            for coords_, weapon_name in self._known_loot.items()
            if self._weapon_rank(weapon_name) > own_weapon_rank
        }
        if better_weapon_targets and own_weapon_rank <= self._weapon_rank("scroll"):
            return self._safe_targets_or_menhir(better_weapon_targets, mist_positions)

        tracked = self._get_recently_tracked_enemies()
        if tracked:
            tracked_targets = {coords_ for coords_, _ in tracked[:2]}
            return self._safe_targets_or_menhir(tracked_targets, mist_positions)

        if better_weapon_targets and own_weapon_rank < self._weapon_rank("bow_loaded"):
            return self._safe_targets_or_menhir(better_weapon_targets, mist_positions)

        nearest_mist = self._nearest_mist_distance(knowledge.position, mist_positions)
        mist_critical = nearest_mist is not None and nearest_mist <= MIST_CRITICAL_DISTANCE
        mist_close = nearest_mist is not None and nearest_mist <= MIST_CLOSE_DISTANCE
        if self._menhir_position is not None:
            if mist_critical:
                return {self._menhir_position}
            if knowledge.no_of_champions_alive <= MENHIR_ENDGAME_ALIVE_TRIGGER:
                return {self._menhir_position}
            if mist_close and my_health <= 4:
                return {self._menhir_position}

        exploration_targets = self._exploration_targets(knowledge.position)
        if exploration_targets:
            return self._safe_targets_or_menhir(exploration_targets, mist_positions)

        frontier = self._frontier_tiles(knowledge.position)
        if frontier:
            return self._safe_targets_or_menhir(frontier, mist_positions)

        if self._menhir_position is not None and knowledge.no_of_champions_alive <= MENHIR_ENDGAME_ALIVE_TRIGGER:
            return {self._menhir_position}

        if self._known_tile_type:
            avg_x = sum(coords_[0] for coords_ in self._known_tile_type) // len(self._known_tile_type)
            avg_y = sum(coords_[1] for coords_ in self._known_tile_type) // len(self._known_tile_type)
            centre = coordinates.Coords(avg_x, avg_y)
            if self._is_known_passable(centre):
                return {centre}

        return set()

    def _policy_mode(
        self,
        knowledge: characters.ChampionKnowledge,
        my_health: int,
        my_weapon_name: str,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
    ) -> str:
        own_tile = self._tile_from_visible(knowledge.position, knowledge.visible_tiles)
        own_effects = {effect.type for effect in own_tile.effects} if own_tile is not None else set()

        if my_health <= 4 or "mist" in own_effects or "fire" in own_effects:
            return "retreat"
        if visible_enemies:
            return "combat"
        if my_health <= 6 and any(name == "potion" for name in self._known_consumables.values()):
            return "recovery"
        if any(self._weapon_rank(weapon) > self._weapon_rank(my_weapon_name) for weapon in self._known_loot.values()):
            return "loot"
        if knowledge.no_of_champions_alive <= 3:
            return "endgame"
        return "explore"

    @staticmethod
    def _desired_facing_towards(
        origin: coordinates.Coords,
        target: coordinates.Coords,
    ) -> characters.Facing | None:
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        if abs(dx) >= abs(dy) and dx != 0:
            return characters.Facing.RIGHT if dx > 0 else characters.Facing.LEFT
        if dy != 0:
            return characters.Facing.DOWN if dy > 0 else characters.Facing.UP
        return None

    def _turn_towards_action(
        self,
        current_facing: characters.Facing,
        desired_facing: characters.Facing | None,
    ) -> characters.Action:
        if desired_facing == current_facing.turn_left():
            return characters.Action.TURN_LEFT
        if desired_facing == current_facing.turn_right():
            return characters.Action.TURN_RIGHT
        return characters.Action.TURN_LEFT if self._scan_left_next else characters.Action.TURN_RIGHT

    def _recent_unseen_enemy_positions(
        self,
        max_turns: int = SHADOW_MEMORY_MAX_TURNS,
    ) -> list[tuple[coordinates.Coords, int]]:
        recent_positions: list[tuple[coordinates.Coords, int]] = []
        for enemy_position, last_seen_turn in self._last_known_enemies.values():
            turns_ago = self._turn_no - last_seen_turn
            if 0 < turns_ago <= max_turns:
                recent_positions.append((enemy_position, turns_ago))
        recent_positions.sort(key=lambda pair: pair[1])
        return recent_positions

    def _reactive_damage_action(
        self,
        position: coordinates.Coords,
        facing: characters.Facing,
        my_health: int,
        my_weapon_name: str,
        knowledge: characters.ChampionKnowledge,
        mist_positions: list[coordinates.Coords],
    ) -> characters.Action:
        recent_enemies = self._recent_unseen_enemy_positions()
        if recent_enemies:
            last_enemy_pos = recent_enemies[0][0]
            desired = self._desired_facing_towards(position, last_enemy_pos)
            if desired is not None and facing != desired:
                return self._turn_towards_action(facing, desired)

        return characters.Action.TURN_LEFT

    def _enemy_likely_behind(
        self,
        position: coordinates.Coords,
        facing: characters.Facing,
    ) -> bool:
        for enemy_position, _ in self._recent_unseen_enemy_positions():
            desired_facing = self._desired_facing_towards(position, enemy_position)
            if desired_facing is None:
                continue
            if desired_facing == facing.opposite():
                return True
        return False

    def _reactive_scan_action(
        self,
        knowledge: characters.ChampionKnowledge,
        position: coordinates.Coords,
        facing: characters.Facing,
        policy_mode: str,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
    ) -> characters.Action | None:
        if visible_enemies:
            self._reactive_scan_remaining = 0
            return None

        if self._reactive_scan_remaining == 1:
            self._reactive_scan_remaining = 0
            self._last_reactive_scan_turn = self._turn_no
            return characters.Action.TURN_RIGHT if self._reactive_scan_left_first else characters.Action.TURN_LEFT

        if policy_mode not in {"explore", "loot", "recovery", "endgame"}:
            return None
        if self._turn_no - self._last_reactive_scan_turn < REACTIVE_SCAN_COOLDOWN:
            return None
        if self._current_kill_potion_target(position) is not None:
            return None

        own_tile = self._tile_from_visible(position, knowledge.visible_tiles)
        own_effects = {effect.type for effect in own_tile.effects} if own_tile is not None else set()
        if "mist" in own_effects or "fire" in own_effects:
            return None

        if not self._enemy_likely_behind(position, facing):
            return None

        self._reactive_scan_left_first = self._scan_left_next
        self._scan_left_next = not self._scan_left_next
        self._reactive_scan_remaining = 1
        return characters.Action.TURN_LEFT if self._reactive_scan_left_first else characters.Action.TURN_RIGHT

    def _exploration_scan_action(
        self,
        knowledge: characters.ChampionKnowledge,
        position: coordinates.Coords,
        facing: characters.Facing,
        policy_mode: str,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
    ) -> characters.Action | None:
        if visible_enemies:
            return None
        if policy_mode != "explore":
            return None
        if self._turn_no < EXPLORATION_SCAN_INITIAL_DELAY:
            return None
        if self._turn_no - self._last_scan_turn < EXPLORATION_SCAN_INTERVAL:
            return None

        self._last_scan_turn = self._turn_no
        self._scan_left_next = not self._scan_left_next
        return characters.Action.TURN_LEFT if self._scan_left_next else characters.Action.TURN_RIGHT

    def _visible_mist_positions(
        self,
        knowledge: characters.ChampionKnowledge,
    ) -> list[coordinates.Coords]:
        mist_positions: list[coordinates.Coords] = []
        for raw_coords, tile in knowledge.visible_tiles.items():
            if any(effect.type == "mist" for effect in tile.effects):
                mist_positions.append(self._to_coords(raw_coords))
        return mist_positions

    def _update_kill_potion_target(
        self,
        knowledge: characters.ChampionKnowledge,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
    ) -> None:
        current_visible_enemies = {
            enemy_description.controller_name: enemy_position
            for enemy_position, enemy_description in visible_enemies
        }

        for enemy_name, previous_position in self._previous_visible_enemies.items():
            if enemy_name in current_visible_enemies:
                continue

            tile = self._tile_from_visible(previous_position, knowledge.visible_tiles)
            if tile is None or tile.consumable is None:
                continue
            if tile.consumable.name != "potion":
                continue

            self._kill_potion_target = previous_position
            self._kill_potion_target_until_turn = self._turn_no + KILL_POTION_TARGET_TTL
            self._known_consumables[previous_position] = "potion"

        self._previous_visible_enemies = current_visible_enemies

        if self._kill_potion_target is None:
            return
        if self._turn_no > self._kill_potion_target_until_turn:
            self._kill_potion_target = None
            self._kill_potion_target_until_turn = 0
            return
        if self._known_consumables.get(self._kill_potion_target) != "potion":
            self._kill_potion_target = None
            self._kill_potion_target_until_turn = 0

    def _current_kill_potion_target(
        self,
        position: coordinates.Coords,
    ) -> coordinates.Coords | None:
        if self._kill_potion_target is None:
            return None
        if self._turn_no > self._kill_potion_target_until_turn:
            self._kill_potion_target = None
            self._kill_potion_target_until_turn = 0
            return None

        target = self._kill_potion_target
        if target == position:
            self._kill_potion_target = None
            self._kill_potion_target_until_turn = 0
            return None
        if self._known_consumables.get(target) != "potion":
            self._kill_potion_target = None
            self._kill_potion_target_until_turn = 0
            return None
        return target

    def _exploration_targets(
        self,
        position: coordinates.Coords,
    ) -> set[coordinates.Coords]:
        candidates: list[tuple[float, coordinates.Coords]] = []
        for coords_, tile_type in self._known_tile_type.items():
            if tile_type not in PASSABLE_TILE_TYPES:
                continue
            if coords_ == position:
                continue

            distance = self._manhattan(position, coords_)
            if distance < EXPLORATION_MIN_DISTANCE:
                continue

            score = float(distance)
            if self._is_recently_visited(coords_):
                score -= 8.0

            if self._menhir_position is not None:
                score += 0.2 * float(self._manhattan(coords_, self._menhir_position))

            candidates.append((score, coords_))

        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return {coords_ for _, coords_ in candidates[:EXPLORATION_CANDIDATES]}

    def _is_safe_target(
        self,
        target_position: coordinates.Coords,
        mist_positions: list[coordinates.Coords],
    ) -> bool:
        if self._menhir_position is None or not mist_positions:
            return True

        mist_to_menhir = self._nearest_mist_distance(self._menhir_position, mist_positions)
        if mist_to_menhir is None:
            return True

        target_to_menhir = self._manhattan(target_position, self._menhir_position)
        if target_to_menhir > mist_to_menhir + TARGET_MIST_SAFETY_MARGIN:
            return False

        if mist_to_menhir <= MENHIR_PATH_MIST_TRIGGER_DISTANCE:
            exits = sum(
                1
                for direction in CARDINAL_DIRECTIONS
                if self._is_known_passable(target_position + direction)
            )
            if exits <= 1 and target_to_menhir >= mist_to_menhir:
                return False
        return True

    def _safe_targets_or_menhir(
        self,
        targets: set[coordinates.Coords],
        mist_positions: list[coordinates.Coords],
    ) -> set[coordinates.Coords]:
        if not targets:
            return set()

        safe_targets = {target for target in targets if self._is_safe_target(target, mist_positions)}
        if safe_targets:
            return safe_targets

        if self._menhir_position is not None:
            return {self._menhir_position}
        return targets

    def _nearest_mist_distance(
        self,
        origin: coordinates.Coords,
        mist_positions: list[coordinates.Coords],
    ) -> int | None:
        if not mist_positions:
            return None
        return min(self._manhattan(origin, mist_position) for mist_position in mist_positions)

    @optional_profile(name="JeffreyE.menhir_guard")
    def _menhir_position_bonus(
        self,
        position: coordinates.Coords,
        champions_alive: int,
        mist_positions: list[coordinates.Coords],
    ) -> float:
        if self._menhir_position is None:
            return 0.0

        dist_to_menhir = float(self._manhattan(position, self._menhir_position))
        nearest_mist = self._nearest_mist_distance(position, mist_positions)
        mist_critical = nearest_mist is not None and nearest_mist <= MIST_CRITICAL_DISTANCE
        mist_close = nearest_mist is not None and nearest_mist <= MIST_CLOSE_DISTANCE

        if champions_alive <= MENHIR_ENDGAME_ALIVE_TRIGGER:
            attraction = MENHIR_ENDGAME_ATTRACTION
        elif mist_critical:
            attraction = MENHIR_MIST_ATTRACTION * 1.6
        elif mist_close:
            attraction = MENHIR_MIST_ATTRACTION
        else:
            return 0.0

        distance_error = abs(dist_to_menhir - MENHIR_STANDOFF_DISTANCE)
        ring_bonus = max(0.0, MENHIR_STANDOFF_BAND - distance_error)
        base = (0.5 + 2.4 * ring_bonus) if mist_close and champions_alive > MENHIR_ENDGAME_ALIVE_TRIGGER else (1.0 + 3.2 * ring_bonus)
        bonus = attraction * base

        if dist_to_menhir <= 1.0 and not mist_critical:
            bonus -= 2.6 * attraction
        return bonus

    def _endgame_mist_proximity_penalty(
        self,
        position: coordinates.Coords,
        mist_positions: list[coordinates.Coords],
        champions_alive: int,
        my_health: int,
    ) -> float:
        if not mist_positions:
            return 0.0
        if champions_alive > MENHIR_ENDGAME_ALIVE_TRIGGER + 1 and my_health > 4:
            return 0.0

        nearest_mist = self._nearest_mist_distance(position, mist_positions)
        if nearest_mist is None or nearest_mist > ENDGAME_MIST_NEAR_DISTANCE:
            return 0.0

        proximity = float(ENDGAME_MIST_NEAR_DISTANCE - nearest_mist + 1)
        penalty = ENDGAME_MIST_PROXIMITY_PENALTY * proximity
        if champions_alive <= MENHIR_ENDGAME_ALIVE_TRIGGER:
            penalty *= 1.35
        if my_health <= 4:
            penalty *= 1.25
        return penalty

    def _candidate_actions(
        self,
        position: coordinates.Coords,
        facing: characters.Facing,
        my_weapon_name: str,
        knowledge: characters.ChampionKnowledge,
        blocked_positions: set[coordinates.Coords],
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
    ) -> tuple[tuple[characters.Action, ...], dict[characters.Action, SimulatedState]]:
        candidate_actions: list[characters.Action] = []
        own_tile = self._tile_from_visible(position, knowledge.visible_tiles)
        currently_in_mist = own_tile is not None and any(effect.type == "mist" for effect in own_tile.effects)

        enemy_positions = {coords_ for coords_, _ in visible_enemies}
        threatened = self._weapon_cut_positions(my_weapon_name, position, facing, knowledge.visible_tiles)
        attack_hits = any(coords_ in enemy_positions for coords_ in threatened)
        if attack_hits or (my_weapon_name == "bow_unloaded" and visible_enemies):
            candidate_actions.append(characters.Action.ATTACK)

        movement_actions: list[characters.Action] = []
        movement_simulated: dict[characters.Action, SimulatedState] = {}
        for movement_action in MOVEMENT_ACTIONS:
            simulated = self._simulate_action(
                action=movement_action,
                position=position,
                facing=facing,
                weapon_name=my_weapon_name,
                knowledge=knowledge,
                blocked_positions=blocked_positions,
            )
            if simulated.moved:
                if not visible_enemies and not currently_in_mist:
                    simulated_tile = self._tile_from_visible(simulated.position, knowledge.visible_tiles)
                    entering_mist = simulated_tile is not None and any(
                        effect.type == "mist" for effect in simulated_tile.effects
                    )
                    if entering_mist:
                        continue
                movement_actions.append(movement_action)
                movement_simulated[movement_action] = simulated

        candidate_actions.extend(movement_actions)

        # if visible_enemies or not movement_actions:
        candidate_actions.append(characters.Action.TURN_LEFT)
        candidate_actions.append(characters.Action.TURN_RIGHT)

        deduped: list[characters.Action] = []
        seen: set[characters.Action] = set()
        for action in candidate_actions:
            if action in seen:
                continue
            seen.add(action)
            deduped.append(action)

        if not deduped:
            deduped = list(ALL_ACTIONS)

        simulated_actions: dict[characters.Action, SimulatedState] = {}
        for action in deduped:
            if action in movement_simulated:
                simulated_actions[action] = movement_simulated[action]
            else:
                simulated_actions[action] = self._simulate_action(
                    action=action,
                    position=position,
                    facing=facing,
                    weapon_name=my_weapon_name,
                    knowledge=knowledge,
                    blocked_positions=blocked_positions,
                )

        return tuple(deduped), simulated_actions

    def _enemy_pressure_map(
        self,
        knowledge: characters.ChampionKnowledge,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
        reference_position: coordinates.Coords,
    ) -> dict[CoordsLike, float]:
        pressure_map: dict[CoordsLike, float] = {}
        visible_enemy_names = {enemy.controller_name for _, enemy in visible_enemies}

        considered_enemies = sorted(
            visible_enemies,
            key=lambda pair: self._manhattan(reference_position, pair[0]),
        )[:3]

        for enemy_position, enemy in considered_enemies:
            damage = max(1, self._weapon_damage(enemy.weapon.name))
            enemy_weapon_base = self._weapon_base(enemy.weapon.name)
            pressure_multiplier = 1.0
            if enemy_weapon_base in {"bow", "amulet", "scroll"}:
                pressure_multiplier *= RANGED_WEAPON_PRESSURE_MULTIPLIER
            elif enemy_weapon_base in {"sword", "axe"}:
                pressure_multiplier *= MID_RANGE_WEAPON_PRESSURE_MULTIPLIER

            enemy_distance_to_me = self._manhattan(reference_position, enemy_position)
            setup_scale = SETUP_TURN_THREAT_SCALE
            if enemy_distance_to_me <= 1:
                setup_scale *= SETUP_TURN_THREAT_ADJACENT_SCALE

            immediate_tiles = self._weapon_cut_positions(
                enemy.weapon.name,
                enemy_position,
                enemy.facing,
                knowledge.visible_tiles,
            )
            for tile in immediate_tiles:
                pressure_map[tile] = pressure_map.get(tile, 0.0) + pressure_multiplier * (65.0 + 12.0 * damage)

            for rotated_facing in (enemy.facing.turn_left(), enemy.facing.turn_right()):
                setup_tiles = self._weapon_cut_positions(
                    enemy.weapon.name,
                    enemy_position,
                    rotated_facing,
                    knowledge.visible_tiles,
                )
                for tile in setup_tiles:
                    tile_setup_scale = setup_scale
                    if enemy_distance_to_me <= 1 and tile == reference_position:
                        tile_setup_scale *= 0.1
                    pressure_map[tile] = pressure_map.get(tile, 0.0) + pressure_multiplier * tile_setup_scale * (14.0 + 4.0 * damage)

            for movement_action in MOVEMENT_ACTIONS:
                moved_enemy = self._simulate_action(
                    action=movement_action,
                    position=enemy_position,
                    facing=enemy.facing,
                    weapon_name=enemy.weapon.name,
                    knowledge=knowledge,
                    blocked_positions=set(),
                )
                if not moved_enemy.moved:
                    continue
                followup_tiles = self._weapon_cut_positions(
                    enemy.weapon.name,
                    moved_enemy.position,
                    moved_enemy.facing,
                    knowledge.visible_tiles,
                )
                for tile in followup_tiles:
                    pressure_map[tile] = pressure_map.get(tile, 0.0) + pressure_multiplier * (9.0 + 3.0 * damage)

            pressure_map[enemy_position] = pressure_map.get(enemy_position, 0.0) + pressure_multiplier * 8.0

        for controller_name, (enemy_position, last_seen_turn) in self._last_known_enemies.items():
            if controller_name in visible_enemy_names:
                continue

            turns_ago = self._turn_no - last_seen_turn
            if turns_ago <= 0 or turns_ago > SHADOW_MEMORY_MAX_TURNS:
                continue

            uncertainty_penalty = SHADOW_PRESSURE_BASE / float(turns_ago)
            radius = SHADOW_PRESSURE_RADIUS_PER_TURN * turns_ago

            for dx in range(-radius, radius + 1):
                for dy in range(-radius, radius + 1):
                    manhattan = abs(dx) + abs(dy)
                    if manhattan > radius:
                        continue

                    candidate: CoordsLike = (enemy_position[0] + dx, enemy_position[1] + dy)
                    tile_type = self._known_tile_type.get(candidate)
                    if tile_type is not None and tile_type not in PASSABLE_TILE_TYPES:
                        continue

                    scale = max(SHADOW_PRESSURE_MIN_SCALE, 1.0 - 0.3 * float(manhattan))
                    pressure_map[candidate] = pressure_map.get(candidate, 0.0) + uncertainty_penalty * scale
        return pressure_map

    def _score_action(
        self,
        action: characters.Action,
        simulated: SimulatedState,
        knowledge: characters.ChampionKnowledge,
        my_health: int,
        my_weapon_name: str,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
        distance_map: dict[coordinates.Coords, float],
        blocked_positions: set[coordinates.Coords],
        current_position: coordinates.Coords,
        current_facing: characters.Facing,
        policy_mode: str,
        mist_positions: list[coordinates.Coords],
        enemy_pressure_map: dict[CoordsLike, float],
        current_danger_penalty: int,
    ) -> float:
        score = 0.0
        hw = self._heuristic_weights
        attack_value = 0.0

        current_tile = self._tile_from_visible(current_position, knowledge.visible_tiles)
        simulated_tile = self._tile_from_visible(simulated.position, knowledge.visible_tiles)
        current_is_mist = current_position in mist_positions or (
            current_tile is not None and any(effect.type == "mist" for effect in current_tile.effects)
        )
        simulated_is_mist = simulated.position in mist_positions or (
            simulated_tile is not None and any(effect.type == "mist" for effect in simulated_tile.effects)
        )

        if simulated_is_mist and not current_is_mist:
            score -= MIST_HARD_VETO_PENALTY
        elif simulated_is_mist:
            score -= MIST_STAY_PENALTY

        score += hw.danger_delta_scale * self._danger_delta_bonus(
            current_position,
            simulated.position,
            knowledge,
            visible_enemies,
            my_health,
            my_weapon_name,
            current_penalty=current_danger_penalty,
        )

        if action in MOVEMENT_ACTIONS and not simulated.moved:
            score -= hw.stay_still_penalty
        elif simulated.moved:
            score += 12.0

        if action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT) and not visible_enemies:
            score -= EXPLORE_TURN_PENALTY if policy_mode == "explore" else NON_COMBAT_TURN_PENALTY

        if distance_map and not visible_enemies:
            best_dir_facing = current_facing
            min_dist = distance_map.get(current_position, math.inf)

            for direction in CARDINAL_DIRECTIONS:
                neighbor = current_position + direction
                d = distance_map.get(neighbor, math.inf)
                if d < min_dist:
                    min_dist = d
                    candidate_facing = self._desired_facing_towards(current_position, neighbor)
                    if candidate_facing is not None:
                        best_dir_facing = candidate_facing

            if simulated.facing == best_dir_facing:
                score += EXPLORE_FACING_BONUS

        if action == characters.Action.ATTACK:
            attack_value = self._attack_score(
                current_position,
                current_facing,
                my_weapon_name,
                visible_enemies,
                knowledge.visible_tiles,
                policy_mode,
            )
            score += hw.attack_scale * attack_value

        if visible_enemies:
            nearest_enemy_pos, nearest_enemy = min(
                visible_enemies,
                key=lambda pair: self._manhattan(current_position, pair[0]),
            )
            current_enemy_distance = self._manhattan(current_position, nearest_enemy_pos)
            new_enemy_distance = self._manhattan(simulated.position, nearest_enemy_pos)
            distance_delta = current_enemy_distance - new_enemy_distance

            my_power = self._combat_power(my_health, my_weapon_name)
            enemy_power = self._combat_power(nearest_enemy.health, nearest_enemy.weapon.name)
            if policy_mode == "retreat":
                score += -35.0 * distance_delta
            else:
                if my_power >= enemy_power:
                    score += 19.0 * distance_delta
                else:
                    score += -20.0 * distance_delta

        if distance_map:
            current_distance = distance_map.get(current_position, math.inf)
            new_distance = distance_map.get(simulated.position, math.inf)
            target_distance_scale = hw.target_distance_scale
            if new_distance < current_distance:
                score += target_distance_scale * 14.0 * (current_distance - new_distance)
            elif new_distance > current_distance and current_distance != math.inf:
                score -= target_distance_scale * 8.0 * (new_distance - current_distance)

        pressure_value = enemy_pressure_map.get(simulated.position, 0.0)
        if action == characters.Action.ATTACK and attack_value > 0.0:
            pressure_value *= ATTACK_ACTION_PRESSURE_DISCOUNT
        score -= hw.lookahead_penalty_scale * pressure_value
        return score

    def _attack_score(
        self,
        current_position: coordinates.Coords,
        current_facing: characters.Facing,
        my_weapon_name: str,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
        visible_tiles: dict[CoordsLike, Any],
        policy_mode: str,
    ) -> float:
        threatened = self._weapon_cut_positions(
            my_weapon_name,
            current_position,
            current_facing,
            visible_tiles,
        )
        enemy_by_position = {coords_: enemy for coords_, enemy in visible_enemies}
        hit_positions = [coords_ for coords_ in threatened if coords_ in enemy_by_position]
        hits = [enemy_by_position[coords_] for coords_ in hit_positions]
        if not hits:
            if my_weapon_name == "bow_unloaded" and visible_enemies:
                nearest_enemy_distance = min(
                    self._manhattan(current_position, enemy_position)
                    for enemy_position, _ in visible_enemies
                )
                if nearest_enemy_distance <= 2:
                    return -15.0
                return 20.0
            return -75.0

        damage = self._weapon_damage(my_weapon_name)
        score = 300.0 + 100.0 * len(hits)
        score += sum(170.0 for enemy in hits if enemy.health <= damage)
        if self._weapon_base(my_weapon_name) == "bow":
            nearest_hit_distance = min(
                self._manhattan(current_position, enemy_position)
                for enemy_position in hit_positions
            )
            if nearest_hit_distance <= 2:
                score -= 48.0
            elif nearest_hit_distance >= 4:
                score += 34.0
        if policy_mode == "retreat":
            score -= 32.0
        return score

    def _danger_delta_bonus(
        self,
        current_position: coordinates.Coords,
        new_position: coordinates.Coords,
        knowledge: characters.ChampionKnowledge,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
        my_health: int,
        my_weapon_name: str,
        current_penalty: int | None = None,
    ) -> float:
        if current_penalty is None:
            current_penalty = self._danger_penalty(
                current_position,
                knowledge,
                visible_enemies,
                my_health,
                my_weapon_name,
            )
        new_penalty = self._danger_penalty(
            new_position,
            knowledge,
            visible_enemies,
            my_health,
            my_weapon_name,
        )
        return float(current_penalty - new_penalty)

    def _danger_penalty(
        self,
        position: coordinates.Coords,
        knowledge: characters.ChampionKnowledge,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
        my_health: int,
        my_weapon_name: str,
    ) -> int:
        penalty = 0.0
        tile = self._tile_from_visible(position, knowledge.visible_tiles)
        if tile is not None:
            for effect in tile.effects:
                if effect.type == "mist":
                    base = MIST_TILE_PENALTY if my_health > 3 else int(MIST_TILE_PENALTY * 1.9)
                    penalty += base
                elif effect.type == "fire":
                    base = FIRE_TILE_PENALTY if my_health > 4 else int(FIRE_TILE_PENALTY * 1.35)
                    penalty += base

        my_rank = self._weapon_rank(my_weapon_name)
        for enemy_position, enemy in visible_enemies:
            enemy_weapon_name = enemy.weapon.name
            enemy_weapon_base = self._weapon_base(enemy_weapon_name)
            threatened = self._weapon_cut_positions(enemy_weapon_name, enemy_position, enemy.facing, knowledge.visible_tiles)
            if position in threatened:
                if enemy_weapon_name == "bow_unloaded":
                    penalty += 20
                else:
                    penalty += 34 + 11 * self._weapon_damage(enemy_weapon_name)
                    if enemy_weapon_name == "bow_loaded":
                        penalty += 12

            diagonal_dx = abs(position[0] - enemy_position[0])
            diagonal_dy = abs(position[1] - enemy_position[1])
            if enemy_weapon_base in {"sword", "bow", "scroll"} and diagonal_dx == 1 and diagonal_dy == 1:
                penalty -= DIAGONAL_LINEAR_WEAPON_BONUS
            elif enemy_weapon_base == "bow" and diagonal_dx == 2 and diagonal_dy == 2:
                penalty -= DIAGONAL_BOW_SECOND_RING_BONUS

            if self._manhattan(position, enemy_position) == 1:
                enemy_rank = self._weapon_rank(enemy_weapon_name)
                penalty += 10 + 4 * max(enemy_rank - my_rank, 0)
                if enemy.health > my_health:
                    penalty += 10

        if my_health <= 3:
            penalty *= 1.2
        return max(0, int(penalty))

    def _weapon_cut_positions(
        self,
        weapon_name: str,
        position: CoordsLike,
        facing: characters.Facing,
        visible_tiles: dict[CoordsLike, Any],
        ignore_characters: bool = False,
    ) -> tuple[coordinates.Coords, ...]:
        position = self._to_coords(position)

        cache_key = (weapon_name, position, facing, ignore_characters)
        cached = self._cut_positions_cache.get(cache_key)
        if cached is not None:
            return cached

        if weapon_name == "axe":
            centre = position + facing.value
            result = (
                centre + facing.turn_left().value,
                centre,
                centre + facing.turn_right().value,
            )
            self._cut_positions_cache[cache_key] = result
            return result

        if weapon_name == "amulet":
            result = (
                coordinates.Coords(position[0] + 1, position[1] + 1),
                coordinates.Coords(position[0] - 1, position[1] + 1),
                coordinates.Coords(position[0] + 1, position[1] - 1),
                coordinates.Coords(position[0] - 1, position[1] - 1),
                coordinates.Coords(position[0] + 2, position[1] + 2),
                coordinates.Coords(position[0] - 2, position[1] + 2),
                coordinates.Coords(position[0] + 2, position[1] - 2),
                coordinates.Coords(position[0] - 2, position[1] - 2),
            )
            self._cut_positions_cache[cache_key] = result
            return result

        base_weapon = self._weapon_base(weapon_name)
        reach = WEAPON_REACH_BY_NAME.get(weapon_name)
        if reach is None:
            reach = WEAPON_REACH_BY_NAME.get(base_weapon)
        if reach is not None:
            current = position
            cut_positions: list[coordinates.Coords] = []
            for _ in range(reach):
                current = current + facing.value
                if current not in self._known_tile_type and self._tile_from_visible(current, visible_tiles) is None:
                    break
                cut_positions.append(current)
                if not self._is_transparent(current, visible_tiles, ignore_characters=ignore_characters):
                    break
            frozen_cut_positions = tuple(cut_positions)
            self._cut_positions_cache[cache_key] = frozen_cut_positions
            return frozen_cut_positions

        self._cut_positions_cache[cache_key] = tuple()
        return tuple()

    @staticmethod
    def _weapon_base(weapon_name: str) -> str:
        known_base = WEAPON_BASE_BY_NAME.get(weapon_name)
        if known_base is not None:
            return known_base
        separator_index = weapon_name.find("_")
        if separator_index == -1:
            return weapon_name
        return weapon_name[:separator_index]

    def _weapon_rank(self, weapon_name: str) -> int:
        return WEAPON_PRIORITY_BY_NAME.get(weapon_name, 1)

    def _combat_power(self, health: int, weapon_name: str) -> float:
        return float(health) + 1.5 * self._weapon_rank(weapon_name)

    def _weapon_damage(self, weapon_name: str) -> int:
        return WEAPON_DAMAGE_BY_NAME.get(weapon_name, 2)

    def _distance_preference_value(
        self,
        distance: int,
        weapon_name: str,
        enemy_weapon_name: str,
    ) -> float:
        weapon_base = self._weapon_base(weapon_name)
        enemy_weapon_base = self._weapon_base(enemy_weapon_name)
        distance_f = float(distance)

        if weapon_base == "bow":
            min_safe = (
                BOW_KITE_MIN_DISTANCE_UNLOADED
                if weapon_name == "bow_unloaded"
                else BOW_KITE_MIN_DISTANCE_LOADED
            )
            max_safe = BOW_KITE_MAX_DISTANCE

            if enemy_weapon_base in {"knife", "sword", "axe", "scroll"}:
                min_safe += 1
                max_safe += 1

            if distance_f < float(min_safe):
                return -BOW_KITE_CLOSE_RANGE_PENALTY * (float(min_safe) - distance_f)
            if distance_f > float(max_safe):
                return -BOW_KITE_TOO_FAR_PENALTY * (distance_f - float(max_safe))

            center = 0.5 * float(min_safe + max_safe)
            return BOW_KITE_STANDOFF_BONUS - 4.0 * abs(distance_f - center)

        desired_distance = 1.0
        if weapon_base == "sword":
            desired_distance = 2.0
        elif weapon_base == "amulet":
            desired_distance = 2.0

        value = 18.0 - 7.0 * abs(distance_f - desired_distance)
        if weapon_base in {"knife", "axe", "scroll"} and distance_f > 3.0:
            value -= 4.0 * (distance_f - 3.0)
        return value

    def _is_transparent(
        self,
        coords_: coordinates.Coords,
        visible_tiles: dict[CoordsLike, Any],
        ignore_characters: bool = False,
    ) -> bool:
        tile_type = self._known_tile_type.get(coords_)
        if tile_type is None:
            visible_tile = self._tile_from_visible(coords_, visible_tiles)
            if visible_tile is None:
                return False
            tile_type = visible_tile.type
        if tile_type not in TRANSPARENT_TILE_TYPES:
            return False
        if not ignore_characters:
            visible_tile = self._tile_from_visible(coords_, visible_tiles)
            if visible_tile is not None and visible_tile.character is not None:
                return False
        return True

    def _is_known_passable(self, coords_: coordinates.Coords) -> bool:
        return self._known_tile_type.get(coords_) in PASSABLE_TILE_TYPES

    def _is_movement_passable(
        self,
        coords_: coordinates.Coords,
        knowledge: characters.ChampionKnowledge,
        blocked_positions: Collection[coordinates.Coords],
    ) -> bool:
        if coords_ in blocked_positions:
            return False
        if not self._is_known_passable(coords_):
            return False
        visible_tile = self._tile_from_visible(coords_, knowledge.visible_tiles)
        if visible_tile is not None and visible_tile.character is not None:
            return False
        return True

    def _local_mobility(
        self,
        position: coordinates.Coords,
        knowledge: characters.ChampionKnowledge,
        blocked_positions: Collection[coordinates.Coords],
    ) -> int:
        mobility = 0
        for direction in CARDINAL_DIRECTIONS:
            neighbour = position + direction
            if self._is_movement_passable(neighbour, knowledge, blocked_positions):
                mobility += 1
        return mobility

    def _frontier_tiles(self, position: coordinates.Coords) -> set[coordinates.Coords]:
        frontier: set[coordinates.Coords] = set()
        for coords_, tile_type in self._known_tile_type.items():
            if tile_type not in PASSABLE_TILE_TYPES:
                continue
            if self._is_recently_visited(coords_):
                continue
            for direction in CARDINAL_DIRECTIONS:
                neighbour = coords_ + direction
                if neighbour not in self._known_tile_type:
                    frontier.add(coords_)
                    break
        if position in frontier and len(frontier) > 1:
            frontier.remove(position)
        return frontier

    def _dynamic_mist_step_cost(self, my_health: int) -> float:
        time_factor = float(self._turn_no) / 100.0
        dynamic_mist_cost = STEP_COST_MIST * (1.0 + MIST_TEMPORAL_SCALE_PER_100_TURNS * time_factor)
        if my_health < 4:
            dynamic_mist_cost *= LOW_HP_MIST_COST_MULTIPLIER
        return dynamic_mist_cost

    def _movement_step_cost(
        self,
        current: coordinates.Coords,
        destination: coordinates.Coords,
        visible_tiles: dict[CoordsLike, Any],
        visible_enemy_positions: list[coordinates.Coords],
        mist_positions: list[coordinates.Coords],
        dynamic_mist_cost: float,
    ) -> float:
        step_cost = STEP_COST_BASE

        tile = self._tile_from_visible(destination, visible_tiles)
        if tile is not None:
            for effect in tile.effects:
                if effect.type == "mist":
                    step_cost += dynamic_mist_cost
                elif effect.type == "fire":
                    step_cost += STEP_COST_FIRE
        elif destination in mist_positions:
            step_cost += dynamic_mist_cost

        if visible_enemy_positions:
            nearest_enemy = min(self._manhattan(destination, enemy_pos) for enemy_pos in visible_enemy_positions)
            if nearest_enemy <= 1:
                step_cost += STEP_COST_ENEMY_ADJACENT
            elif nearest_enemy == 2:
                step_cost += STEP_COST_ENEMY_NEAR

        forward_facing = self._desired_facing_towards(current, destination)
        if forward_facing is not None:
            for _, (last_enemy_position, last_seen_turn) in self._last_known_enemies.items():
                turns_ago = self._turn_no - last_seen_turn
                if turns_ago <= 0 or turns_ago > SHADOW_MEMORY_MAX_TURNS:
                    continue

                desired_to_enemy = self._desired_facing_towards(destination, last_enemy_position)
                if desired_to_enemy is None:
                    continue

                if forward_facing.opposite() == desired_to_enemy:
                    step_cost += BACK_EXPOSURE_STEP_PENALTY / float(turns_ago)

        return step_cost

    def _distance_map(
        self,
        targets: set[coordinates.Coords],
        blocked_positions: set[coordinates.Coords],
        knowledge: characters.ChampionKnowledge,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
        mist_positions: list[coordinates.Coords],
        mist_distance_lookup: dict[coordinates.Coords, int] | None = None,
        query_positions: set[coordinates.Coords] | None = None,
        agent_position: coordinates.Coords | None = None,
        my_health: int = 10,
    ) -> dict[coordinates.Coords, float]:
        if not targets:
            return {}

        distances: dict[coordinates.Coords, float] = {}
        queue: list[tuple[float, int, coordinates.Coords]] = []
        push_order = 0
        visible_enemy_positions = [coords_ for coords_, _ in visible_enemies]
        pending_queries = set(query_positions) if query_positions is not None else None
        dynamic_mist_cost = self._dynamic_mist_step_cost(my_health)
        effective_mist_lookup = mist_distance_lookup if mist_distance_lookup is not None else self._mist_distance_lookup(mist_positions)

        nearest_mist_to_agent = None
        if agent_position is not None:
            nearest_mist_to_agent = self._nearest_mist_distance(agent_position, mist_positions)
        menhir_path_focus = (
            self._menhir_position is not None
            and nearest_mist_to_agent is not None
            and nearest_mist_to_agent <= MENHIR_PATH_MIST_TRIGGER_DISTANCE
        )

        for target in targets:
            distances[target] = 0.0
            heapq.heappush(queue, (0.0, push_order, target))
            push_order += 1
            if pending_queries is not None:
                pending_queries.discard(target)

        while queue:
            current_distance, _, current = heapq.heappop(queue)
            if current_distance > distances.get(current, math.inf):
                continue

            if pending_queries is not None and current in pending_queries:
                pending_queries.remove(current)
                if not pending_queries:
                    return distances

            current_mist_distance = effective_mist_lookup.get(current)

            for direction in CARDINAL_DIRECTIONS:
                neighbour = current + direction
                if neighbour in blocked_positions and neighbour not in targets:
                    continue
                if not self._is_known_passable(neighbour):
                    continue

                step_cost = self._movement_step_cost(
                    current=current,
                    destination=neighbour,
                    visible_tiles=knowledge.visible_tiles,
                    visible_enemy_positions=visible_enemy_positions,
                    mist_positions=mist_positions,
                    dynamic_mist_cost=dynamic_mist_cost,
                )

                if current_mist_distance is not None:
                    neighbour_mist_distance = effective_mist_lookup.get(neighbour)
                    if neighbour_mist_distance < current_mist_distance:
                        step_cost += MIST_VECTOR_TOWARD_PENALTY
                    elif neighbour_mist_distance > current_mist_distance:
                        step_cost = max(0.1, step_cost - MIST_VECTOR_AWAY_BONUS)

                if menhir_path_focus and self._menhir_position is not None:
                    dist_before_menhir = self._manhattan(current, self._menhir_position)
                    dist_after_menhir = self._manhattan(neighbour, self._menhir_position)
                    if dist_after_menhir < dist_before_menhir:
                        step_cost = max(0.1, step_cost - MENHIR_PATH_PROGRESS_REWARD)

                neighbour_distance = current_distance + step_cost

                if neighbour_distance < distances.get(neighbour, math.inf):
                    distances[neighbour] = neighbour_distance
                    heapq.heappush(queue, (neighbour_distance, push_order, neighbour))
                    push_order += 1
        return distances

    def _mist_distance_lookup(
        self,
        mist_positions: list[coordinates.Coords],
    ) -> dict[coordinates.Coords, int]:
        if not mist_positions:
            return {}

        walkable_nodes = {
            coords_
            for coords_, tile_type in self._known_tile_type.items()
            if tile_type in PASSABLE_TILE_TYPES
        }
        if not walkable_nodes:
            return {}

        distance_lookup: dict[coordinates.Coords, int] = {}
        queue: deque[coordinates.Coords] = deque()

        for mist_position in mist_positions:
            if mist_position in walkable_nodes and mist_position not in distance_lookup:
                distance_lookup[mist_position] = 0
                queue.append(mist_position)

        if not queue:
            return {
                node: min(self._manhattan(node, mist_position) for mist_position in mist_positions)
                for node in walkable_nodes
            }

        while queue:
            current = queue.popleft()
            current_distance = distance_lookup[current]
            for direction in CARDINAL_DIRECTIONS:
                neighbour = current + direction
                if neighbour not in walkable_nodes or neighbour in distance_lookup:
                    continue
                distance_lookup[neighbour] = current_distance + 1
                queue.append(neighbour)

        if len(distance_lookup) != len(walkable_nodes):
            for node in walkable_nodes:
                if node in distance_lookup:
                    continue
                distance_lookup[node] = min(self._manhattan(node, mist_position) for mist_position in mist_positions)

        return distance_lookup

    def _simulate_action(
        self,
        action: characters.Action,
        position: coordinates.Coords,
        facing: characters.Facing,
        weapon_name: str,
        knowledge: characters.ChampionKnowledge,
        blocked_positions: Collection[coordinates.Coords],
    ) -> SimulatedState:
        new_position = position
        new_facing = facing
        new_weapon_name = weapon_name

        if action == characters.Action.TURN_LEFT:
            return SimulatedState(new_position, facing.turn_left(), False, new_weapon_name)
        if action == characters.Action.TURN_RIGHT:
            return SimulatedState(new_position, facing.turn_right(), False, new_weapon_name)

        if action in MOVEMENT_ACTIONS:
            if action == characters.Action.STEP_FORWARD:
                direction = facing.value
            elif action == characters.Action.STEP_BACKWARD:
                direction = facing.opposite().value
            elif action == characters.Action.STEP_LEFT:
                direction = facing.turn_left().value
            else:
                direction = facing.turn_right().value

            candidate = position + direction
            if self._is_movement_passable(candidate, knowledge, blocked_positions):
                new_position = candidate
            return SimulatedState(new_position, new_facing, new_position != position, new_weapon_name)

        if action == characters.Action.ATTACK:
            if weapon_name == "bow_unloaded":
                new_weapon_name = "bow_loaded"
            elif weapon_name == "bow_loaded":
                new_weapon_name = "bow_unloaded"

        return SimulatedState(new_position, new_facing, False, new_weapon_name)

    def _enemy_lookahead_penalty(
        self,
        simulated: SimulatedState,
        knowledge: characters.ChampionKnowledge,
        visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
    ) -> int:
        if not visible_enemies:
            return 0

        enemy_blocked_positions = {enemy_position for enemy_position, _ in visible_enemies}
        enemy_blocked_positions.add(simulated.position)

        considered_enemies = sorted(
            visible_enemies,
            key=lambda pair: self._manhattan(simulated.position, pair[0]),
        )[:2]

        pressure = 0
        for enemy_position, enemy in considered_enemies:
            blocked_for_enemy = set(enemy_blocked_positions)
            blocked_for_enemy.discard(enemy_position)

            best_threat = 0
            for enemy_action in ALL_ACTIONS:
                enemy_state = self._simulate_action(
                    enemy_action,
                    enemy_position,
                    enemy.facing,
                    enemy.weapon.name,
                    knowledge,
                    blocked_for_enemy,
                )
                threat = self._enemy_threat_score(
                    enemy_action,
                    enemy_state,
                    enemy.weapon.name,
                    simulated.position,
                    knowledge.visible_tiles,
                )
                best_threat = max(best_threat, threat)

            pressure += best_threat
        return pressure

    def _enemy_threat_score(
        self,
        enemy_action: characters.Action,
        enemy_state: SimulatedState,
        enemy_weapon_name: str,
        my_position: coordinates.Coords,
        visible_tiles: dict[CoordsLike, Any],
    ) -> int:
        threatened_tiles = self._weapon_cut_positions(
            enemy_weapon_name,
            enemy_state.position,
            enemy_state.facing,
            visible_tiles,
        )
        threat = 0

        direct_attack = enemy_action == characters.Action.ATTACK and my_position in threatened_tiles
        setup_attack = (
            enemy_action in (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT)
            and my_position in threatened_tiles
        )
        if direct_attack:
            if enemy_weapon_name == "bow_unloaded":
                threat += 24
            else:
                threat += 95 + 20 * self._weapon_damage(enemy_weapon_name)
        elif setup_attack:
            threat += 20

        distance = self._manhattan(enemy_state.position, my_position)
        threat += max(0, 20 - 4 * distance)
        if enemy_action in MOVEMENT_ACTIONS and enemy_state.moved:
            threat += 6
        return threat

    @optional_profile(name="JeffreyE.combat_minimax")
    def _combat_minimax_bonuses(
        self,
        knowledge: characters.ChampionKnowledge,
        my_position: coordinates.Coords,
        my_facing: characters.Facing,
        my_health: int,
        my_weapon_name: str,
        enemy_position: coordinates.Coords,
        enemy_description: characters.ChampionDescription,
        candidate_scores: dict[characters.Action, float],
    ) -> dict[characters.Action, float]:
        initial_state = DuelState(
            my_position=my_position,
            my_facing=my_facing,
            my_health=my_health,
            my_weapon_name=my_weapon_name,
            enemy_position=enemy_position,
            enemy_facing=enemy_description.facing,
            enemy_health=enemy_description.health,
            enemy_weapon_name=enemy_description.weapon.name,
        )

        baseline_value = self._duel_state_value(initial_state, knowledge)
        ordered_root_actions = sorted(
            ALL_ACTIONS,
            key=lambda action: candidate_scores[action],
            reverse=True,
        )[:COMBAT_MINIMAX_BRANCHING]

        bonuses: dict[characters.Action, float] = {}
        for action in ordered_root_actions:
            next_state = self._duel_apply_action(initial_state, actor="me", action=action, knowledge=knowledge)
            state_value = self._duel_minimax(
                state=next_state,
                knowledge=knowledge,
                depth=COMBAT_MINIMAX_DEPTH - 1,
                maximizing=False,
                alpha=-math.inf,
                beta=math.inf,
            )
            bonus = self._minimax_bonus_scale * (state_value - baseline_value)
            bonuses[action] = max(-90.0, min(90.0, bonus))
        return bonuses

    @optional_profile(name="JeffreyE.combat_mcts")
    def _combat_mcts_bonuses(
        self,
        knowledge: characters.ChampionKnowledge,
        my_position: coordinates.Coords,
        my_facing: characters.Facing,
        my_health: int,
        my_weapon_name: str,
        enemy_position: coordinates.Coords,
        enemy_description: characters.ChampionDescription,
        candidate_scores: dict[characters.Action, float],
    ) -> dict[characters.Action, float]:
        initial_state = DuelState(
            my_position=my_position,
            my_facing=my_facing,
            my_health=my_health,
            my_weapon_name=my_weapon_name,
            enemy_position=enemy_position,
            enemy_facing=enemy_description.facing,
            enemy_health=enemy_description.health,
            enemy_weapon_name=enemy_description.weapon.name,
        )

        baseline_value = self._duel_state_value(initial_state, knowledge)
        root_actions = sorted(
            ALL_ACTIONS,
            key=lambda action: candidate_scores[action],
            reverse=True,
        )[:COMBAT_MCTS_ACTION_WIDTH]
        if not root_actions:
            self._mcts_root = None
            return {}

        root = self._prepare_mcts_root(initial_state, root_actions)

        for _ in range(COMBAT_MCTS_ITERATIONS):
            node = root
            search_depth = 0

            while (
                search_depth < COMBAT_MCTS_ROLLOUT_DEPTH
                and not self._duel_is_terminal(node.state)
                and not node.untried_actions
                and node.children
            ):
                node = self._mcts_select_child(node)
                search_depth += 1

            if (
                search_depth < COMBAT_MCTS_ROLLOUT_DEPTH
                and not self._duel_is_terminal(node.state)
                and node.untried_actions
            ):
                action_index = self._rng.randrange(len(node.untried_actions))
                action = node.untried_actions.pop(action_index)
                child_state = self._duel_apply_action(
                    state=node.state,
                    actor=node.actor,
                    action=action,
                    knowledge=knowledge,
                )
                next_actor = "enemy" if node.actor == "me" else "me"
                child_actions = self._duel_mcts_candidate_actions(child_state, next_actor, knowledge)
                child = MCTSNode(
                    state=child_state,
                    actor=next_actor,
                    parent=node,
                    action_from_parent=action,
                    untried_actions=child_actions,
                )
                node.children[action] = child
                node = child
                search_depth += 1

            rollout_value = self._duel_rollout_value(
                state=node.state,
                actor=node.actor,
                knowledge=knowledge,
                depth_left=COMBAT_MCTS_ROLLOUT_DEPTH - search_depth,
            )

            backprop_node: MCTSNode | None = node
            while backprop_node is not None:
                backprop_node.visits += 1
                backprop_node.total_value += rollout_value
                backprop_node = backprop_node.parent

        bonuses: dict[characters.Action, float] = {}
        for action in root_actions:
            child = root.children.get(action)
            if child is not None and child.visits > 0:
                estimated_value = child.total_value / child.visits
            else:
                child_state = self._duel_apply_action(
                    state=initial_state,
                    actor="me",
                    action=action,
                    knowledge=knowledge,
                )
                estimated_value = self._duel_state_value(child_state, knowledge)
            bonus = self._mcts_bonus_scale * (estimated_value - baseline_value)
            bonuses[action] = max(-65.0, min(65.0, bonus))
        self._mcts_root = root
        return bonuses

    def _prepare_mcts_root(
        self,
        initial_state: DuelState,
        root_actions: list[characters.Action],
    ) -> MCTSNode:
        reusable_root = self._find_reusable_mcts_node(initial_state)
        if reusable_root is None:
            return MCTSNode(
                state=initial_state,
                actor="me",
                parent=None,
                action_from_parent=None,
                untried_actions=list(root_actions),
            )

        reusable_root.parent = None
        reusable_root.action_from_parent = None
        reusable_root.actor = "me"
        reusable_root.state = initial_state

        allowed_actions = set(root_actions)
        reusable_root.children = {
            action: child
            for action, child in reusable_root.children.items()
            if action in allowed_actions
        }
        for child in reusable_root.children.values():
            child.parent = reusable_root

        child_actions = set(reusable_root.children)
        untried_actions: list[characters.Action] = []
        for action in reusable_root.untried_actions:
            if action in allowed_actions and action not in child_actions and action not in untried_actions:
                untried_actions.append(action)
        for action in root_actions:
            if action not in child_actions and action not in untried_actions:
                untried_actions.append(action)
        reusable_root.untried_actions = untried_actions
        return reusable_root

    def _find_reusable_mcts_node(self, initial_state: DuelState) -> MCTSNode | None:
        existing_root = self._mcts_root
        if existing_root is None:
            return None

        search_stack: list[tuple[MCTSNode, int]] = [(existing_root, 0)]
        while search_stack:
            node, depth = search_stack.pop()
            if node.actor == "me" and node.state == initial_state:
                return node
            if depth >= 2:
                continue
            for child in node.children.values():
                search_stack.append((child, depth + 1))
        return None

    def _mcts_select_child(self, node: MCTSNode) -> MCTSNode:
        log_parent_visits = math.log(max(1, node.visits))
        scored_children: list[tuple[float, MCTSNode]] = []
        for child in node.children.values():
            exploitation = child.total_value / max(1, child.visits)
            if node.actor == "enemy":
                exploitation = -exploitation
            exploration = COMBAT_MCTS_EXPLORATION * math.sqrt(log_parent_visits / max(1, child.visits))
            scored_children.append((exploitation + exploration, child))

        best_score = max(score for score, _ in scored_children)
        best_children = [child for score, child in scored_children if score >= best_score - 1e-9]
        return self._rng.choice(best_children)

    @staticmethod
    def _duel_is_terminal(state: DuelState) -> bool:
        return state.my_health <= 0 or state.enemy_health <= 0

    def _duel_mcts_candidate_actions(
        self,
        state: DuelState,
        actor: str,
        knowledge: characters.ChampionKnowledge,
    ) -> list[characters.Action]:
        scored: list[tuple[float, characters.Action]] = []
        for action in ALL_ACTIONS:
            child = self._duel_apply_action(state=state, actor=actor, action=action, knowledge=knowledge)
            score = self._duel_state_value(child, knowledge)
            bias = self._duel_action_bias(state=state, action=action, actor=actor, knowledge=knowledge)
            score += 0.25 * bias if actor == "me" else -0.25 * bias
            scored.append((score, action))

        scored.sort(key=lambda pair: pair[0], reverse=actor == "me")
        return [action for _, action in scored[:COMBAT_MCTS_ACTION_WIDTH]]

    def _duel_rollout_value(
        self,
        state: DuelState,
        actor: str,
        knowledge: characters.ChampionKnowledge,
        depth_left: int,
    ) -> float:
        rollout_state = state
        rollout_actor = actor

        for _ in range(max(0, depth_left)):
            if self._duel_is_terminal(rollout_state):
                break

            action = self._duel_rollout_action(rollout_state, rollout_actor, knowledge)
            if action is None:
                break
            rollout_state = self._duel_apply_action(
                state=rollout_state,
                actor=rollout_actor,
                action=action,
                knowledge=knowledge,
            )
            rollout_actor = "enemy" if rollout_actor == "me" else "me"

        return self._duel_state_value(rollout_state, knowledge)

    def _duel_attack_hits_target(
        self,
        state: DuelState,
        actor: str,
        knowledge: characters.ChampionKnowledge,
    ) -> bool:
        if actor == "me":
            actor_position = state.my_position
            actor_facing = state.my_facing
            actor_weapon_name = state.my_weapon_name
            target_position = state.enemy_position
        else:
            actor_position = state.enemy_position
            actor_facing = state.enemy_facing
            actor_weapon_name = state.enemy_weapon_name
            target_position = state.my_position

        threatened = self._weapon_cut_positions(
            actor_weapon_name,
            actor_position,
            actor_facing,
            knowledge.visible_tiles,
            ignore_characters=True,
        )
        return target_position in threatened and self._weapon_damage(actor_weapon_name) > 0

    def _duel_rollout_action(
        self,
        state: DuelState,
        actor: str,
        knowledge: characters.ChampionKnowledge,
    ) -> characters.Action | None:
        # Heavy playout policy: keep rollout cheap but tactically consistent.
        if self._duel_attack_hits_target(state, actor, knowledge):
            return characters.Action.ATTACK

        if actor == "me":
            actor_position = state.my_position
            actor_facing = state.my_facing
            target_position = state.enemy_position
            actor_weapon_name = state.my_weapon_name
        else:
            actor_position = state.enemy_position
            actor_facing = state.enemy_facing
            target_position = state.my_position
            actor_weapon_name = state.enemy_weapon_name

        if actor_weapon_name == "bow_unloaded":
            return characters.Action.ATTACK

        desired_facing = self._desired_facing_towards(actor_position, target_position)
        if desired_facing is not None and actor_facing != desired_facing:
            return self._turn_towards_action(actor_facing, desired_facing)

        forward_position = actor_position + actor_facing.value
        if not self._is_movement_passable(
            forward_position,
            knowledge,
            (target_position,),
        ):
            return self._rng.choice(
                (
                    characters.Action.STEP_LEFT,
                    characters.Action.STEP_RIGHT,
                )
            )

        if self._rng.random() < ROLLOUT_EPSILON_SIDE_STEP_PROB:
            return self._rng.choice(
                (
                    characters.Action.STEP_LEFT,
                    characters.Action.STEP_RIGHT,
                    characters.Action.STEP_BACKWARD,
                )
            )

        return characters.Action.STEP_FORWARD

    def _duel_minimax(
        self,
        state: DuelState,
        knowledge: characters.ChampionKnowledge,
        depth: int,
        maximizing: bool,
        alpha: float,
        beta: float,
    ) -> float:
        if state.my_health <= 0:
            return -1000.0 - 20.0 * state.enemy_health
        if state.enemy_health <= 0:
            return 1000.0 + 20.0 * state.my_health
        if depth <= 0:
            return self._duel_state_value(state, knowledge)

        if maximizing:
            value = -math.inf
            actions = self._duel_ordered_actions(state, actor="me", knowledge=knowledge, maximizing=True)
            for action in actions:
                child = self._duel_apply_action(state, actor="me", action=action, knowledge=knowledge)
                value = max(value, self._duel_minimax(child, knowledge, depth - 1, False, alpha, beta))
                alpha = max(alpha, value)
                if beta <= alpha:
                    break
            return value

        value = math.inf
        actions = self._duel_ordered_actions(state, actor="enemy", knowledge=knowledge, maximizing=False)
        for action in actions:
            child = self._duel_apply_action(state, actor="enemy", action=action, knowledge=knowledge)
            value = min(value, self._duel_minimax(child, knowledge, depth - 1, True, alpha, beta))
            beta = min(beta, value)
            if beta <= alpha:
                break
        return value

    def _duel_ordered_actions(
        self,
        state: DuelState,
        actor: str,
        knowledge: characters.ChampionKnowledge,
        maximizing: bool,
    ) -> list[characters.Action]:
        scored_actions: list[tuple[float, characters.Action]] = []
        for action in ALL_ACTIONS:
            child = self._duel_apply_action(state, actor=actor, action=action, knowledge=knowledge)
            score = self._duel_state_value(child, knowledge)
            if actor == "me":
                score += self._duel_action_bias(state, action, actor="me", knowledge=knowledge)
            else:
                score -= self._duel_action_bias(state, action, actor="enemy", knowledge=knowledge)
            scored_actions.append((score, action))

        scored_actions.sort(key=lambda pair: pair[0], reverse=maximizing)
        return [action for _, action in scored_actions[:COMBAT_MINIMAX_BRANCHING]]

    def _duel_action_bias(
        self,
        state: DuelState,
        action: characters.Action,
        actor: str,
        knowledge: characters.ChampionKnowledge,
    ) -> float:
        if actor == "me":
            actor_position = state.my_position
            actor_facing = state.my_facing
            actor_weapon_name = state.my_weapon_name
            target_position = state.enemy_position
            target_weapon_name = state.enemy_weapon_name
        else:
            actor_position = state.enemy_position
            actor_facing = state.enemy_facing
            actor_weapon_name = state.enemy_weapon_name
            target_position = state.my_position
            target_weapon_name = state.my_weapon_name

        if action == characters.Action.ATTACK:
            threatened = self._weapon_cut_positions(
                actor_weapon_name,
                actor_position,
                actor_facing,
                knowledge.visible_tiles,
                ignore_characters=True,
            )
            if target_position in threatened:
                attack_bias = 140.0 + 18.0 * self._weapon_damage(actor_weapon_name)
                if self._weapon_base(actor_weapon_name) == "bow":
                    distance = self._manhattan(actor_position, target_position)
                    if distance <= 2:
                        attack_bias -= 36.0
                    elif distance >= 3:
                        attack_bias += 22.0
                return attack_bias
            if actor_weapon_name == "bow_unloaded":
                distance = self._manhattan(actor_position, target_position)
                return 22.0 if distance >= 3 else -8.0
            return -25.0
        if action in MOVEMENT_ACTIONS:
            simulated = self._duel_simulate_non_attack(
                actor_position,
                actor_facing,
                actor_weapon_name,
                action,
                knowledge,
                target_position,
            )
            if not simulated.moved:
                return -65.0
            before = self._manhattan(actor_position, target_position)
            after = self._manhattan(simulated.position, target_position)
            before_pref = self._distance_preference_value(before, actor_weapon_name, target_weapon_name)
            after_pref = self._distance_preference_value(after, simulated.weapon_name, target_weapon_name)
            return 14.0 * (after_pref - before_pref)
        return 0.0

    def _duel_apply_action(
        self,
        state: DuelState,
        actor: str,
        action: characters.Action,
        knowledge: characters.ChampionKnowledge,
    ) -> DuelState:
        if actor == "me":
            actor_position = state.my_position
            actor_facing = state.my_facing
            actor_health = state.my_health
            actor_weapon_name = state.my_weapon_name

            target_position = state.enemy_position
            target_facing = state.enemy_facing
            target_health = state.enemy_health
            target_weapon_name = state.enemy_weapon_name
        else:
            actor_position = state.enemy_position
            actor_facing = state.enemy_facing
            actor_health = state.enemy_health
            actor_weapon_name = state.enemy_weapon_name

            target_position = state.my_position
            target_facing = state.my_facing
            target_health = state.my_health
            target_weapon_name = state.my_weapon_name

        if action == characters.Action.ATTACK:
            threatened = self._weapon_cut_positions(
                actor_weapon_name,
                actor_position,
                actor_facing,
                knowledge.visible_tiles,
                ignore_characters=True,
            )
            if target_position in threatened:
                target_health -= self._weapon_damage(actor_weapon_name)

            if actor_weapon_name == "bow_unloaded":
                actor_weapon_name = "bow_loaded"
            elif actor_weapon_name == "bow_loaded":
                actor_weapon_name = "bow_unloaded"
        else:
            simulated = self._duel_simulate_non_attack(
                actor_position,
                actor_facing,
                actor_weapon_name,
                action,
                knowledge,
                target_position,
            )
            actor_position = simulated.position
            actor_facing = simulated.facing

        actor_health = max(0, actor_health)
        target_health = max(0, target_health)

        if actor == "me":
            return DuelState(
                my_position=actor_position,
                my_facing=actor_facing,
                my_health=actor_health,
                my_weapon_name=actor_weapon_name,
                enemy_position=target_position,
                enemy_facing=target_facing,
                enemy_health=target_health,
                enemy_weapon_name=target_weapon_name,
            )

        return DuelState(
            my_position=target_position,
            my_facing=target_facing,
            my_health=target_health,
            my_weapon_name=target_weapon_name,
            enemy_position=actor_position,
            enemy_facing=actor_facing,
            enemy_health=actor_health,
            enemy_weapon_name=actor_weapon_name,
        )

    def _duel_simulate_non_attack(
        self,
        position: coordinates.Coords,
        facing: characters.Facing,
        weapon_name: str,
        action: characters.Action,
        knowledge: characters.ChampionKnowledge,
        blocked_position: coordinates.Coords,
    ) -> SimulatedState:
        return self._simulate_action(
            action=action,
            position=position,
            facing=facing,
            weapon_name=weapon_name,
            knowledge=knowledge,
            blocked_positions=(blocked_position,),
        )

    def _duel_state_value(self, state: DuelState, knowledge: characters.ChampionKnowledge) -> float:
        cached_value = self._duel_state_value_cache.get(state)
        if cached_value is not None:
            return cached_value

        value = self._duel_state_value_impl(state, knowledge)
        self._duel_state_value_cache[state] = value
        return value

    def _duel_state_value_impl(self, state: DuelState, knowledge: characters.ChampionKnowledge) -> float:
        if state.my_health <= 0:
            return -1000.0
        if state.enemy_health <= 0:
            return 1000.0

        value = 0.0
        value += 120.0 * (state.my_health - state.enemy_health)

        my_power = self._combat_power(state.my_health, state.my_weapon_name)
        enemy_power = self._combat_power(state.enemy_health, state.enemy_weapon_name)
        distance = self._manhattan(state.my_position, state.enemy_position)
        value += 8.0 * (my_power - enemy_power)
        my_distance_value = self._distance_preference_value(
            distance,
            state.my_weapon_name,
            state.enemy_weapon_name,
        )
        enemy_distance_value = self._distance_preference_value(
            distance,
            state.enemy_weapon_name,
            state.my_weapon_name,
        )
        value += 0.9 * my_distance_value
        value -= 0.55 * enemy_distance_value

        my_threatened_tiles = self._weapon_cut_positions(
            state.my_weapon_name,
            state.my_position,
            state.my_facing,
            knowledge.visible_tiles,
            ignore_characters=True,
        )
        enemy_threatened_tiles = self._weapon_cut_positions(
            state.enemy_weapon_name,
            state.enemy_position,
            state.enemy_facing,
            knowledge.visible_tiles,
            ignore_characters=True,
        )
        if state.enemy_position in my_threatened_tiles:
            value += 42.0 + 7.0 * self._weapon_damage(state.my_weapon_name)
        if state.my_position in enemy_threatened_tiles:
            value -= 58.0 + 7.0 * self._weapon_damage(state.enemy_weapon_name)

        my_mobility = self._duel_mobility(state.my_position, state.enemy_position)
        enemy_mobility = self._duel_mobility(state.enemy_position, state.my_position)
        value += 6.0 * (my_mobility - enemy_mobility)

        value -= 0.5 * self._position_effect_penalty(state.my_position, knowledge.visible_tiles)
        value += 0.5 * self._position_effect_penalty(state.enemy_position, knowledge.visible_tiles)
        return value

    def _position_effect_penalty(
        self,
        position: coordinates.Coords,
        visible_tiles: dict[CoordsLike, Any],
    ) -> int:
        tile = self._tile_from_visible(position, visible_tiles)
        if tile is None:
            return 0

        penalty = 0
        for effect in tile.effects:
            if effect.type == "mist":
                penalty += MIST_TILE_PENALTY
            elif effect.type == "fire":
                penalty += FIRE_TILE_PENALTY
        return penalty

    def _duel_mobility(
        self,
        position: coordinates.Coords,
        blocked_position: coordinates.Coords,
    ) -> int:
        mobility = 0
        for direction in CARDINAL_DIRECTIONS:
            neighbour = position + direction
            if neighbour == blocked_position:
                continue
            if self._is_known_passable(neighbour):
                mobility += 1
        return mobility

    def _tile_from_visible(
        self,
        coords_: coordinates.Coords,
        visible_tiles: dict[CoordsLike, Any],
    ) -> Any | None:
        return visible_tiles.get(coords_)

    def _is_recently_visited(self, coords_: coordinates.Coords) -> bool:
        return self._recent_positions.count(coords_) >= 2

    @staticmethod
    def _manhattan(a: coordinates.Coords, b: coordinates.Coords) -> int:
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    @staticmethod
    def _to_coords(coords_: CoordsLike) -> coordinates.Coords:
        return coordinates.Coords(coords_[0], coords_[1])

    def _decay_tracked_enemies(self) -> None:
        to_remove = [
            controller_name
            for controller_name, (_, last_seen_turn) in self._last_known_enemies.items()
            if self._turn_no - last_seen_turn > ENEMY_MEMORY_TURNS
        ]
        for controller_name in to_remove:
            del self._last_known_enemies[controller_name]

    def _get_recently_tracked_enemies(self) -> list[tuple[coordinates.Coords, str]]:
        recent = [
            (controller_name, payload)
            for controller_name, payload in self._last_known_enemies.items()
        ]
        recent.sort(key=lambda pair: pair[1][1], reverse=True)
        return [(coords_, controller_name) for controller_name, (coords_, _) in recent]
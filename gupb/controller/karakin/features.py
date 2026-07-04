from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from gupb.model import characters
from gupb.model import coordinates

from . import weapon_info
from .utils import HAZARD_EFFECT_TYPES, manhattan
from .world_memory import WorldMemory

FEATURE_VECTOR_SIZE = 22
MAX_DISTANCE = 30.0


@dataclass(slots=True)
class StrategicContext:
    knowledge: characters.ChampionKnowledge
    self_description: characters.ChampionDescription
    visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]]
    mist_positions: list[coordinates.Coords]
    fire_positions: list[coordinates.Coords]
    features: np.ndarray

    @property
    def position(self) -> coordinates.Coords:
        return self.knowledge.position

    @property
    def health(self) -> int:
        return self.self_description.health

    @property
    def weapon_name(self) -> str:
        return self.self_description.weapon.name

    @property
    def facing(self) -> characters.Facing:
        return self.self_description.facing


def build_context(
    knowledge: characters.ChampionKnowledge,
    memory: WorldMemory,
    own_name: str,
) -> StrategicContext | None:
    self_description = memory.self_description(knowledge)
    if self_description is None:
        return None

    enemies = memory.visible_enemies(knowledge, own_name)
    mist_positions = memory.visible_mist_positions(knowledge)
    fire_positions = memory.visible_fire_positions(knowledge)
    features = build_feature_vector(knowledge, memory, self_description, enemies, mist_positions)
    return StrategicContext(
        knowledge=knowledge,
        self_description=self_description,
        visible_enemies=enemies,
        mist_positions=mist_positions,
        fire_positions=fire_positions,
        features=features,
    )


def build_feature_vector(
    knowledge: characters.ChampionKnowledge,
    memory: WorldMemory,
    self_description: characters.ChampionDescription,
    visible_enemies: list[tuple[coordinates.Coords, characters.ChampionDescription]],
    mist_positions: list[coordinates.Coords],
) -> np.ndarray:
    position = knowledge.position
    health_norm = min(self_description.health / float(characters.CHAMPION_STARTING_HP), 1.5) / 1.5
    alive_norm = min(knowledge.no_of_champions_alive, 12) / 12.0
    rank_norm = weapon_info.weapon_rank(self_description.weapon.name) / 7.0
    damage_norm = weapon_info.weapon_damage(self_description.weapon.name) / 3.0

    nearest_enemy_distance = _nearest_distance(position, [enemy_position for enemy_position, _ in visible_enemies])
    nearest_enemy_norm = _distance_norm(nearest_enemy_distance)
    visible_enemy_norm = min(len(visible_enemies), 4) / 4.0

    weapon_advantage = 0.0
    can_hit_now = 0.0
    enemy_can_hit_now = 0.0
    if visible_enemies:
        nearest_enemy_position, nearest_enemy = visible_enemies[0]
        weapon_advantage = (
            weapon_info.weapon_rank(self_description.weapon.name)
            - weapon_info.weapon_rank(nearest_enemy.weapon.name)
        ) / 7.0
        if weapon_info.can_hit(
            self_description.weapon.name,
            position,
            self_description.facing,
            nearest_enemy_position,
            memory.tile_type_at,
            lambda coords_: memory.character_at(coords_, knowledge),
        ):
            can_hit_now = 1.0
        if weapon_info.can_hit(
            nearest_enemy.weapon.name,
            nearest_enemy_position,
            nearest_enemy.facing,
            position,
            memory.tile_type_at,
            lambda coords_: memory.character_at(coords_, knowledge),
        ):
            enemy_can_hit_now = 1.0

    better_weapon_targets = [
        coords_
        for coords_, weapon_name in memory.known_loot.items()
        if weapon_info.is_weapon_upgrade(self_description.weapon.name, weapon_name)
    ]
    nearest_weapon_distance = _nearest_distance(position, better_weapon_targets)

    potion_targets = list(memory.known_consumables.keys())
    nearest_potion_distance = _nearest_distance(position, potion_targets)

    menhir_known = memory.menhir_position is not None
    dist_to_menhir = manhattan(position, memory.menhir_position) if memory.menhir_position else math.inf

    nearest_mist_distance = _nearest_distance(position, mist_positions)
    current_tile = knowledge.visible_tiles.get(position)
    on_hazard = 0.0
    if current_tile is not None and any(effect.type in HAZARD_EFFECT_TYPES for effect in current_tile.effects):
        on_hazard = 1.0

    escape_routes = 0
    for facing in characters.Facing:
        candidate = position + facing.value
        if memory.is_known_passable(candidate):
            tile = knowledge.visible_tiles.get(candidate)
            if tile is None or tile.character is None:
                escape_routes += 1

    recent_repeats = sum(1 for old_position in memory.recent_positions if old_position == position)
    menhir_pressure = float(menhir_known and (bool(mist_positions) or knowledge.no_of_champions_alive <= 3))

    vector = np.array(
        [
            health_norm,
            alive_norm,
            rank_norm,
            damage_norm,
            visible_enemy_norm,
            nearest_enemy_norm,
            weapon_advantage,
            can_hit_now,
            enemy_can_hit_now,
            float(bool(better_weapon_targets)),
            _distance_norm(nearest_weapon_distance),
            float(bool(potion_targets)),
            _distance_norm(nearest_potion_distance),
            float(menhir_known),
            _distance_norm(dist_to_menhir),
            float(bool(mist_positions)),
            _distance_norm(nearest_mist_distance),
            on_hazard,
            min(len(memory.known_tile_type), 400) / 400.0,
            min(recent_repeats, 6) / 6.0,
            min(escape_routes, 4) / 4.0,
            menhir_pressure,
        ],
        dtype=np.float32,
    )
    return vector


def _nearest_distance(position: coordinates.Coords, targets: list[coordinates.Coords]) -> int | float:
    if not targets:
        return math.inf
    return min(manhattan(position, target) for target in targets)


def _distance_norm(distance: int | float) -> float:
    if math.isinf(distance):
        return 1.0
    return min(float(distance), MAX_DISTANCE) / MAX_DISTANCE

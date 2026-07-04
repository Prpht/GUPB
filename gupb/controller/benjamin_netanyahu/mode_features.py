from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Iterable, Optional

import numpy as np

from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles

WEAPON_BASES = ("knife", "sword", "bow", "axe", "amulet", "scroll")
WEAPON_TO_INDEX = {weapon_name: idx for idx, weapon_name in enumerate(WEAPON_BASES)}
TRANSPARENT_TILE_TYPES = {"land", "sea", "menhir"}
FEATURE_DIM = 40

PANIC_DAMAGE_SPIKE = 3
PANIC_TURNS = 3


@dataclass(frozen=True)
class TemporalFeatureState:
    known_menhir: Optional[coordinates.Coords]
    recent_damage_sum: int
    panic_turns: int
    hp_delta_prev: float
    was_hit_recently: bool
    turns_since_enemy_seen: int
    nearest_enemy_distance_delta: float


class TemporalFeatureTracker:
    """
    Lightweight temporal tracker for selector features.
    Keeps only short rolling state needed for cheap temporal signals.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self._known_menhir: Optional[coordinates.Coords] = None
        self._last_hp: Optional[int] = None
        self._recent_damage: deque[int] = deque(maxlen=4)
        self._panic_turns: int = 0
        self._turns_since_enemy_seen: int = 0
        self._last_nearest_enemy_distance: Optional[float] = None

    def update(self, knowledge: characters.ChampionKnowledge) -> TemporalFeatureState:
        current_tile = knowledge.visible_tiles.get(knowledge.position)
        self_desc = current_tile.character if current_tile and current_tile.character else None
        current_hp = int(self_desc.health if self_desc else characters.CHAMPION_STARTING_HP)

        if self._panic_turns > 0:
            self._panic_turns -= 1

        hp_delta_prev = 0.0
        if self._last_hp is not None:
            hp_delta_prev = float(current_hp - self._last_hp)
        damage_taken = max(0, int(-hp_delta_prev))
        self._recent_damage.append(damage_taken)
        if damage_taken >= PANIC_DAMAGE_SPIKE:
            self._panic_turns = max(self._panic_turns, PANIC_TURNS)
        elif sum(self._recent_damage) >= PANIC_DAMAGE_SPIKE + 1:
            self._panic_turns = max(self._panic_turns, PANIC_TURNS - 1)
        self._last_hp = current_hp

        enemy_positions: list[coordinates.Coords] = []
        for raw_coords, tile_description in knowledge.visible_tiles.items():
            coords = _to_coords(raw_coords)
            if tile_description.type == "menhir":
                self._known_menhir = coords
            if tile_description.character and tile_description.character.controller_name != (self_desc.controller_name if self_desc else ""):
                enemy_positions.append(coords)

        if enemy_positions:
            nearest_enemy_distance = _normalised_distance(knowledge.position, enemy_positions, max_distance=20.0)
            self._turns_since_enemy_seen = 0
        else:
            nearest_enemy_distance = 1.0
            self._turns_since_enemy_seen = min(self._turns_since_enemy_seen + 1, 50)

        if self._last_nearest_enemy_distance is None:
            nearest_enemy_distance_delta = 0.0
        else:
            nearest_enemy_distance_delta = float(nearest_enemy_distance - self._last_nearest_enemy_distance)
        self._last_nearest_enemy_distance = nearest_enemy_distance

        return TemporalFeatureState(
            known_menhir=self._known_menhir,
            recent_damage_sum=int(sum(self._recent_damage)),
            panic_turns=int(self._panic_turns),
            hp_delta_prev=hp_delta_prev,
            was_hit_recently=damage_taken > 0,
            turns_since_enemy_seen=int(self._turns_since_enemy_seen),
            nearest_enemy_distance_delta=nearest_enemy_distance_delta,
        )


def weapon_base(weapon_name: str) -> str:
    return weapon_name.split("_", 1)[0].lower()


def weapon_rank(weapon_name: str) -> int:
    rank_map = {
        "knife": 0,
        "amulet": 1,
        "sword": 2,
        "scroll": 3,
        "axe": 3,
        "bow": 4,
    }
    return rank_map.get(weapon_base(weapon_name), 0)


def extract_benjamin_features(
        knowledge: characters.ChampionKnowledge,
        current_mode,
        known_menhir: Optional[coordinates.Coords] = None,
        recent_damage_sum: int = 0,
        panic_turns: int = 0,
        hp_delta_prev: float = 0.0,
        turns_since_enemy_seen: int = 0,
        nearest_enemy_distance_delta: float = 0.0,
        was_hit_recently_override: Optional[bool] = None,
) -> np.ndarray:
    current_style = _mode_to_index(current_mode)

    current_tile = knowledge.visible_tiles.get(knowledge.position)
    self_desc = current_tile.character if current_tile and current_tile.character else None
    self_name = self_desc.controller_name if self_desc else ""
    current_hp = float(self_desc.health if self_desc else characters.CHAMPION_STARTING_HP)
    current_hp_norm = np.clip(current_hp / 15.0, 0.0, 1.5).item()
    current_facing = self_desc.facing if self_desc else characters.Facing.UP
    current_weapon = self_desc.weapon.name if self_desc else "knife"
    current_weapon_rank = weapon_rank(current_weapon)

    enemy_infos: list[tuple[coordinates.Coords, float, str]] = []
    potion_positions: list[coordinates.Coords] = []
    better_weapon_positions: list[coordinates.Coords] = []
    menhir_positions: list[coordinates.Coords] = []
    mist_positions: list[coordinates.Coords] = []
    fire_positions: list[coordinates.Coords] = []

    for raw_coords, tile_description in knowledge.visible_tiles.items():
        coords = _to_coords(raw_coords)
        if tile_description.character and tile_description.character.controller_name != self_name:
            enemy_health = float(tile_description.character.health)
            enemy_weapon = tile_description.character.weapon.name
            enemy_infos.append((coords, enemy_health, enemy_weapon))
        if tile_description.consumable and tile_description.consumable.name == "potion":
            potion_positions.append(coords)
        if tile_description.loot:
            loot_name = tile_description.loot.name
            if weapon_rank(loot_name) > current_weapon_rank:
                better_weapon_positions.append(coords)
        if tile_description.type == "menhir":
            menhir_positions.append(coords)
        effect_types = {effect.type for effect in tile_description.effects}
        if "mist" in effect_types:
            mist_positions.append(coords)
        if "fire" in effect_types:
            fire_positions.append(coords)

    enemy_positions = [enemy_coords for enemy_coords, _, _ in enemy_infos]
    nearest_enemy = _nearest_enemy(knowledge.position, enemy_infos)
    nearest_enemy_dist = _normalised_distance(knowledge.position, enemy_positions, max_distance=20.0)
    nearest_enemy_hp_norm = 1.0
    nearest_enemy_weapon_rank_norm = 0.0
    hp_advantage_vs_nearest = 0.0
    if nearest_enemy is not None:
        _, enemy_hp, enemy_weapon = nearest_enemy
        nearest_enemy_hp_norm = np.clip(enemy_hp / 15.0, 0.0, 1.5).item()
        nearest_enemy_weapon_rank_norm = np.clip(float(weapon_rank(enemy_weapon)) / 4.0, 0.0, 1.0).item()
        hp_advantage_vs_nearest = np.clip((current_hp_norm - nearest_enemy_hp_norm) / 1.5, -1.0, 1.0).item()

    adjacent_enemy = 1.0 if _has_adjacent_enemy(knowledge.position, enemy_positions) else 0.0
    enemy_in_range = 1.0 if _enemy_in_attack_range(
        knowledge=knowledge,
        facing=current_facing,
        weapon_name=current_weapon,
        enemy_positions=enemy_positions,
    ) else 0.0
    enemy_threat_close = 1.0 if _enemy_threat_close(knowledge.position, enemy_infos) else 0.0

    on_mist = 1.0 if _position_has_effect(current_tile, "mist") else 0.0
    on_fire = 1.0 if _position_has_effect(current_tile, "fire") else 0.0

    potion_visible = 1.0 if potion_positions else 0.0
    nearest_potion = _normalised_distance(knowledge.position, potion_positions, max_distance=20.0)
    better_weapon_visible = 1.0 if better_weapon_positions else 0.0
    nearest_better_weapon = _normalised_distance(knowledge.position, better_weapon_positions, max_distance=20.0)

    menhir_visible = 1.0 if menhir_positions else 0.0
    known_menhir_position = known_menhir if known_menhir is not None else _nearest_optional(knowledge.position, menhir_positions)
    menhir_known = 1.0 if known_menhir_position is not None else 0.0
    distance_to_known_menhir = _normalised_distance_single(
        knowledge.position,
        known_menhir_position,
        max_distance=20.0,
    )

    recent_damage_value = max(0, int(recent_damage_sum))
    recent_damage_norm = np.clip(float(recent_damage_value) / 8.0, 0.0, 1.0).item()
    was_hit_recently = (
        bool(was_hit_recently_override)
        if was_hit_recently_override is not None
        else (recent_damage_value > 0)
    )
    panic_turns_norm = np.clip(float(max(0, int(panic_turns))) / 3.0, 0.0, 1.0).item()

    hp_delta_prev_norm = np.clip(float(hp_delta_prev) / 8.0, -1.0, 1.0).item()
    turns_since_enemy_seen_norm = np.clip(float(max(0, int(turns_since_enemy_seen))) / 10.0, 0.0, 1.0).item()
    nearest_enemy_distance_delta_norm = np.clip(float(nearest_enemy_distance_delta), -1.0, 1.0).item()

    weapon_one_hot = np.zeros(len(WEAPON_BASES), dtype=np.float32)
    weapon_idx = WEAPON_TO_INDEX.get(weapon_base(current_weapon))
    if weapon_idx is not None:
        weapon_one_hot[weapon_idx] = 1.0

    style_one_hot = np.zeros(3, dtype=np.float32)
    if 0 <= int(current_style) < 3:
        style_one_hot[int(current_style)] = 1.0

    vector = np.array([
        1.0,
        current_hp_norm,
        np.clip(float(knowledge.no_of_champions_alive) / 8.0, 0.0, 1.0),
        np.clip(float(len(knowledge.visible_tiles)) / 120.0, 0.0, 1.0),
        np.clip(float(len(enemy_positions)) / 8.0, 0.0, 1.0),
        np.clip(float(len(potion_positions)) / 8.0, 0.0, 1.0),
        np.clip(float(len(better_weapon_positions)) / 8.0, 0.0, 1.0),
        np.clip(float(len(mist_positions)) / 16.0, 0.0, 1.0),
        np.clip(float(len(fire_positions)) / 16.0, 0.0, 1.0),
        adjacent_enemy,
        enemy_in_range,
        enemy_threat_close,
        on_mist,
        on_fire,
        nearest_enemy_dist,
        nearest_enemy_hp_norm,
        nearest_enemy_weapon_rank_norm,
        hp_advantage_vs_nearest,
        potion_visible,
        nearest_potion,
        better_weapon_visible,
        nearest_better_weapon,
        menhir_visible,
        menhir_known,
        distance_to_known_menhir,
        recent_damage_norm,
        1.0 if was_hit_recently else 0.0,
        panic_turns_norm,
        hp_delta_prev_norm,
        turns_since_enemy_seen_norm,
        nearest_enemy_distance_delta_norm,
    ], dtype=np.float32)

    full_vector = np.concatenate((vector, weapon_one_hot, style_one_hot), dtype=np.float32)
    if full_vector.shape[0] != FEATURE_DIM:
        raise RuntimeError(f"Unexpected feature size: {full_vector.shape[0]} (expected {FEATURE_DIM})")
    return full_vector


def _nearest_enemy(
        origin: coordinates.Coords,
        enemy_infos: list[tuple[coordinates.Coords, float, str]],
) -> Optional[tuple[coordinates.Coords, float, str]]:
    if not enemy_infos:
        return None
    return min(enemy_infos, key=lambda info: _manhattan(origin, info[0]))


def _enemy_in_attack_range(
        knowledge: characters.ChampionKnowledge,
        facing: characters.Facing,
        weapon_name: str,
        enemy_positions: Iterable[coordinates.Coords],
) -> bool:
    enemy_set = set(enemy_positions)
    for attack_pos in _attack_positions(knowledge, facing, weapon_name):
        if attack_pos in enemy_set:
            return True
    return False


def _enemy_threat_close(
        my_position: coordinates.Coords,
        enemy_infos: list[tuple[coordinates.Coords, float, str]],
) -> bool:
    for enemy_coords, _, enemy_weapon in enemy_infos:
        if _manhattan(my_position, enemy_coords) <= _enemy_threat_radius(enemy_weapon):
            return True
    return False


def _enemy_threat_radius(weapon_name: str) -> int:
    base = weapon_base(weapon_name)
    if base in {"knife", "scroll"}:
        return 2
    if base == "sword":
        return 4
    if base == "axe":
        return 3
    if base == "amulet":
        return 3
    if base == "bow":
        return 6
    return 2


def _attack_positions(
        knowledge: characters.ChampionKnowledge,
        facing: characters.Facing,
        weapon_name: str,
) -> list[coordinates.Coords]:
    position = knowledge.position
    base_weapon = weapon_base(weapon_name)
    if base_weapon in {"knife", "scroll"}:
        return [position + facing.value]
    if base_weapon == "sword":
        return _line_positions(knowledge.visible_tiles, position, facing, reach=3)
    if base_weapon == "bow":
        return _line_positions(knowledge.visible_tiles, position, facing, reach=50)
    if base_weapon == "axe":
        centre = position + facing.value
        return [centre + facing.turn_left().value, centre, centre + facing.turn_right().value]
    if base_weapon == "amulet":
        return [
            coordinates.Coords(position.x + 1, position.y + 1),
            coordinates.Coords(position.x - 1, position.y + 1),
            coordinates.Coords(position.x + 1, position.y - 1),
            coordinates.Coords(position.x - 1, position.y - 1),
            coordinates.Coords(position.x + 2, position.y + 2),
            coordinates.Coords(position.x - 2, position.y + 2),
            coordinates.Coords(position.x + 2, position.y - 2),
            coordinates.Coords(position.x - 2, position.y - 2),
        ]
    return [position + facing.value]


def _line_positions(
        visible_tiles: dict[coordinates.Coords, tiles.TileDescription],
        start: coordinates.Coords,
        facing: characters.Facing,
        reach: int,
) -> list[coordinates.Coords]:
    output: list[coordinates.Coords] = []
    current = start
    for _ in range(reach):
        current = current + facing.value
        output.append(current)
        tile_description = visible_tiles.get(current)
        if tile_description is not None and not _is_transparent(tile_description):
            break
    return output


def _is_transparent(tile_description: tiles.TileDescription) -> bool:
    return tile_description.type in TRANSPARENT_TILE_TYPES and tile_description.character is None


def _position_has_effect(
        tile_description: Optional[tiles.TileDescription],
        effect_name: str,
) -> bool:
    if tile_description is None:
        return False
    return any(effect.type == effect_name for effect in tile_description.effects)


def _has_adjacent_enemy(
        position: coordinates.Coords,
        enemy_positions: list[coordinates.Coords],
) -> bool:
    return any(_manhattan(position, enemy_pos) == 1 for enemy_pos in enemy_positions)


def _normalised_distance(
        origin: coordinates.Coords,
        candidates: list[coordinates.Coords],
        max_distance: float,
) -> float:
    if not candidates:
        return 1.0
    nearest = min(float(_manhattan(origin, candidate)) for candidate in candidates)
    return np.clip(nearest / max_distance, 0.0, 1.0).item()


def _normalised_distance_single(
        origin: coordinates.Coords,
        candidate: Optional[coordinates.Coords],
        max_distance: float,
) -> float:
    if candidate is None:
        return 1.0
    nearest = float(_manhattan(origin, candidate))
    return np.clip(nearest / max_distance, 0.0, 1.0).item()


def _nearest_optional(
        origin: coordinates.Coords,
        candidates: list[coordinates.Coords],
) -> Optional[coordinates.Coords]:
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: _manhattan(origin, candidate))


def _manhattan(a: coordinates.Coords, b: coordinates.Coords) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def _to_coords(raw_coords: coordinates.Coords | tuple[int, int]) -> coordinates.Coords:
    if isinstance(raw_coords, coordinates.Coords):
        return raw_coords
    return coordinates.Coords(raw_coords[0], raw_coords[1])


def _mode_to_index(current_mode) -> int:
    if isinstance(current_mode, int):
        return int(current_mode)
    mode_value = getattr(current_mode, "value", None)
    if mode_value == "normal":
        return 0
    if mode_value == "aggressive":
        return 1
    if mode_value == "passive":
        return 2
    return 0


__all__ = [
    "FEATURE_DIM",
    "TemporalFeatureState",
    "TemporalFeatureTracker",
    "extract_benjamin_features",
    "weapon_rank",
]


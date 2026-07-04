from __future__ import annotations

from enum import IntEnum
from pathlib import Path
from typing import Any

import numpy as np

from gupb.model import characters

from .features import StrategicContext
from .utils import manhattan
from .weapon_info import is_weapon_upgrade, weapon_rank
from .world_memory import WorldMemory

MODEL_PATH = Path(__file__).with_name("karakin_sb3.zip")


class StrategicMode(IntEnum):
    FIGHT = 0
    LOOT_WEAPON = 1
    HEAL = 2
    GO_MENHIR = 3
    EXPLORE = 4
    RETREAT = 5


class PPOStrategicPolicy:
    def __init__(self, model_path: str | Path | None = None, enabled: bool = True) -> None:
        self.model_path = Path(model_path) if model_path is not None else MODEL_PATH
        self.enabled = enabled
        self._model: Any | None = None
        self._load_attempted = False

    @property
    def available(self) -> bool:
        self._ensure_loaded()
        return self._model is not None

    def predict(self, features: np.ndarray) -> StrategicMode | None:
        self._ensure_loaded()
        if self._model is None:
            return None
        try:
            action, _ = self._model.predict(features, deterministic=True)
            return StrategicMode(int(action))
        except Exception:
            return None

    def _ensure_loaded(self) -> None:
        if self._load_attempted or not self.enabled:
            return
        self._load_attempted = True
        if not self.model_path.exists():
            return
        try:
            from stable_baselines3 import PPO

            self._model = PPO.load(self.model_path.as_posix(),
                                   custom_objects={
                                        "clip_range": 0.2,
                                        "lr_schedule": lambda _: 0.0003,
                                    })
        except Exception:
            self._model = None


class HeuristicStrategicPolicy:
    def select(self, context: StrategicContext, memory: WorldMemory) -> StrategicMode:
        health = context.health
        current_weapon = context.weapon_name
        position = context.position

        potion_targets = list(memory.known_consumables.keys())
        if health <= 4 and potion_targets:
            return StrategicMode.HEAL

        if context.visible_enemies:
            enemy_position, enemy = context.visible_enemies[0]
            enemy_rank = weapon_rank(enemy.weapon.name)
            own_rank = weapon_rank(current_weapon)
            enemy_distance = manhattan(position, enemy_position)
            if health <= 3 and (enemy_rank >= own_rank or enemy_distance <= 2):
                return StrategicMode.RETREAT
            if enemy_distance <= 6 or health >= enemy.health:
                return StrategicMode.FIGHT

        if memory.menhir_position is not None:
            dist_to_menhir = manhattan(position, memory.menhir_position)
            if context.mist_positions or context.knowledge.no_of_champions_alive <= 3 or dist_to_menhir > 10:
                return StrategicMode.GO_MENHIR

        better_weapon_targets = [
            coords_
            for coords_, weapon_name in memory.known_loot.items()
            if is_weapon_upgrade(current_weapon, weapon_name)
        ]
        if better_weapon_targets and health > 3:
            return StrategicMode.LOOT_WEAPON

        if health < characters.CHAMPION_STARTING_HP and potion_targets:
            return StrategicMode.HEAL

        return StrategicMode.EXPLORE

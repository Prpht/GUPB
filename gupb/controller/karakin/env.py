from __future__ import annotations

from pathlib import Path
import random
from typing import Callable

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from gupb import controller
from gupb.controller import random as random_controller
from gupb.model import characters
from gupb.model import games
from gupb.scripts import arena_generator

from .features import FEATURE_VECTOR_SIZE
from .karakin_controller import KarakinController
from .strategy import MODEL_PATH, StrategicMode
from .utils import manhattan
from .weapon_info import weapon_rank


ControllerFactory = Callable[[str], controller.Controller]


class KarakinStrategicEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(
        self,
        arena_names: list[str] | None = None,
        curriculum: str = "mixed",
        generated_arenas: int = 0,
        random_generated_sizes: bool = True,
        generated_prefix: str = "generated_train",
        arena_mode: str = "mixed",
        agents_no: int = 8,
        karakin_mcts_time_budget: float = 0.05,
        opponent_model_path: str | Path | None = None,
        strict_opponents: bool = False,
        max_cycles_per_step: int = 2000,
        seed: int | None = None,
    ) -> None:
        super().__init__()
        self.action_space = spaces.Discrete(len(StrategicMode))
        self.observation_space = spaces.Box(
            low=-1.0,
            high=1.0,
            shape=(FEATURE_VECTOR_SIZE,),
            dtype=np.float32,
        )
        self.curriculum = curriculum
        self.agents_no = max(2, agents_no)
        self.karakin_mcts_time_budget = karakin_mcts_time_budget
        self.opponent_model_path = Path(opponent_model_path) if opponent_model_path is not None else MODEL_PATH
        self.strict_opponents = strict_opponents
        self.max_cycles_per_step = max_cycles_per_step
        self.rng = random.Random(seed)
        self.game_no = 0
        self.agent = self._training_karakin("Karakin")
        self.game: games.Game | None = None
        self._previous_health: int | None = None
        self._last_score = 0.0
        self._last_snapshot: dict | None = None
        self.opponent_errors: list[str] = []

        generated_names: list[str] = []
        if generated_arenas > 0:
            size_generator = arena_generator.random_size_generator() if random_generated_sizes else None
            if size_generator is None:
                generated_names = arena_generator.generate_arenas(generated_arenas, prefix=generated_prefix)
            else:
                generated_names = arena_generator.generate_arenas(
                    generated_arenas,
                    size_generator=size_generator,
                    prefix=generated_prefix,
                )

        base_arenas = arena_names or self._base_arenas()
        existing_generated = self._existing_generated_arenas()
        if arena_mode == "base":
            selected_arenas = base_arenas
        elif arena_mode == "generated":
            selected_arenas = generated_names + existing_generated
        else:
            selected_arenas = base_arenas + existing_generated + generated_names
        self.arena_names = self._dedupe_arenas(selected_arenas)
        if not self.arena_names:
            if arena_mode == "generated":
                raise ValueError(
                    "arena_mode='generated' requires existing generated_*.gupb maps "
                    "or generated_arenas > 0."
                )
            self.arena_names = self._base_arenas()

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        super().reset(seed=seed)
        if seed is not None:
            self.rng.seed(seed)

        arena_name = self.rng.choice(self.arena_names)
        controllers = self._controllers_for_curriculum()
        self.rng.shuffle(controllers)
        self.game = games.Game(
            game_no=self.game_no,
            arena_name=arena_name,
            to_spawn=controllers,
        )
        self.game_no += 1
        self._previous_health = None
        self._last_score = 0.0
        reached, cycles = self._advance_to_agent_turn()
        observation = self._observe_pending_turn() if reached else self._observation()
        self._previous_health = self.agent.latest_health
        self._last_snapshot = self._snapshot()
        return observation, {
            "arena": arena_name,
            "controllers": [controller_.name for controller_ in controllers],
            "pending_agent_turn": reached,
            "cycles": cycles,
        }

    def step(self, action: int):
        mode = StrategicMode(int(action))
        previous_snapshot = self._last_snapshot
        if not self._is_agent_turn_pending():
            self._advance_to_agent_turn()

        if self._is_agent_turn_pending() and self.game is not None:
            self.agent.force_mode(mode)
            self.game.cycle()

        reached_next_decision, cycles = self._advance_to_agent_turn()
        observation = self._observe_pending_turn() if reached_next_decision else self._observation()
        current_snapshot = self._snapshot()
        terminated = bool(self.game is None or self.game.finished or not self._agent_alive())
        truncated = not reached_next_decision and not terminated
        reward = self._reward(previous_snapshot, current_snapshot, terminated)
        self._previous_health = self.agent.latest_health
        self._last_snapshot = current_snapshot
        return observation, reward, terminated, truncated, {"mode": mode.name, "cycles": cycles}

    def _advance_to_agent_turn(self) -> tuple[bool, int]:
        if self.game is None:
            return False, 0
        cycles = 0
        while (
            not self.game.finished
            and self._agent_alive()
            and not self._is_agent_turn_pending()
            and cycles < self.max_cycles_per_step
        ):
            self.game.cycle()
            cycles += 1
        return self._is_agent_turn_pending(), cycles

    def _observation(self) -> np.ndarray:
        if self.agent.latest_features is None:
            return np.zeros((FEATURE_VECTOR_SIZE,), dtype=np.float32)
        return np.asarray(self.agent.latest_features, dtype=np.float32)

    def _reward(
        self,
        previous_snapshot: dict | None,
        current_snapshot: dict | None,
        terminated: bool,
    ) -> float:
        reward = -0.01
        if previous_snapshot is not None and current_snapshot is not None:
            reward += 0.08 * float(current_snapshot["own_health"] - previous_snapshot["own_health"])
            reward += 0.04 * float(previous_snapshot["enemy_health_sum"] - current_snapshot["enemy_health_sum"])
            reward += 0.25 * float(previous_snapshot["alive_count"] - current_snapshot["alive_count"])
            reward += 0.08 * float(current_snapshot["weapon_rank"] - previous_snapshot["weapon_rank"])
            reward += 0.003 * float(
                max(0, current_snapshot["known_tiles"] - previous_snapshot["known_tiles"])
            )
            if (
                previous_snapshot["menhir_distance"] is not None
                and current_snapshot["menhir_distance"] is not None
                and (current_snapshot["mist_visible"] or current_snapshot["alive_count"] <= 3)
            ):
                reward += 0.03 * float(
                    previous_snapshot["menhir_distance"] - current_snapshot["menhir_distance"]
                )
        if current_snapshot is not None and current_snapshot["own_health"] <= 0:
            reward -= 1.0
        if terminated:
            reward += self._terminal_score_reward(current_snapshot)
        return reward

    def _terminal_score_reward(self, current_snapshot: dict | None) -> float:
        if self.game is None:
            return 0.0
        if not self.game.finished:
            if self._agent_alive():
                return 0.0
            eliminated = 0
            if current_snapshot is not None:
                eliminated = max(0, self.agents_no - current_snapshot["alive_count"])
            return -1.0 + 0.2 * float(eliminated) / float(max(1, self.agents_no - 1))
        try:
            scores = self.game.score()
        except Exception:
            return 0.0
        for scored_controller, score in scores.items():
            if scored_controller == self.agent:
                return float(np.tanh(float(score) / 5.0))
        return -1.0

    def _is_agent_turn_pending(self) -> bool:
        if self.game is None or self.game.finished:
            return False
        if getattr(self.game.current_state, "id", None) != "instants_triggered":
            return False
        return bool(self.game.action_queue and self.game.action_queue[-1].controller == self.agent)

    def _observe_pending_turn(self) -> np.ndarray:
        knowledge = self._pending_knowledge()
        if knowledge is None:
            return self._observation()
        features = self.agent.observe(knowledge)
        if features is None:
            return self._observation()
        return np.asarray(features, dtype=np.float32)

    def _pending_knowledge(self) -> characters.ChampionKnowledge | None:
        if self.game is None or not self._is_agent_turn_pending():
            return None
        champion = self.game.action_queue[-1]
        return characters.ChampionKnowledge(
            champion.position,
            self.game.arena.no_of_champions_alive,
            self.game.arena.visible_tiles(champion),
        )

    def _agent_alive(self) -> bool:
        champion = self._agent_champion()
        return bool(champion is not None and champion.alive)

    def _agent_champion(self):
        if self.game is None:
            return None
        return next((champion for champion in self.game.champions if champion.controller == self.agent), None)

    def _snapshot(self) -> dict | None:
        champion = self._agent_champion()
        if self.game is None or champion is None:
            return None
        own_health = champion.health if champion.alive else 0
        enemy_health_sum = sum(
            other.health for other in self.game.champions if other.controller != self.agent and other.alive
        )
        alive_count = sum(1 for other in self.game.champions if other.alive)
        menhir_distance = None
        if self.agent.memory.menhir_position is not None:
            menhir_distance = manhattan(champion.position, self.agent.memory.menhir_position)
        return {
            "own_health": own_health,
            "enemy_health_sum": enemy_health_sum,
            "alive_count": alive_count,
            "weapon_rank": weapon_rank(champion.weapon.description().name),
            "known_tiles": len(self.agent.memory.known_tile_type),
            "menhir_distance": menhir_distance,
            "mist_visible": bool(self.agent.memory.visible_mist_positions(self._pending_knowledge() or characters.ChampionKnowledge(
                champion.position,
                self.game.arena.no_of_champions_alive,
                self.game.arena.visible_tiles(champion),
            ))),
        }

    def _controllers_for_curriculum(self) -> list[controller.Controller]:
        controllers: list[controller.Controller] = [self.agent]
        opponents_needed = self.agents_no - 1

        if self.curriculum == "teacher":
            controllers.extend(self._team_controllers(limit=opponents_needed, shuffle=False))
        elif self.curriculum == "selfplay":
            selfplay_count = min(3, opponents_needed)
            controllers.extend(self._selfplay_karakin(f"KarakinSelf{i}") for i in range(selfplay_count))
            controllers.extend(
                self._team_controllers(
                    limit=opponents_needed - selfplay_count,
                    shuffle=True,
                )
            )
        else:
            controllers.extend(self._team_controllers(limit=opponents_needed, shuffle=True))

        if len(controllers) < self.agents_no:
            if self.strict_opponents:
                raise RuntimeError(
                    "Unable to build enough non-random opponents: "
                    f"{len(controllers) - 1}/{opponents_needed}. "
                    f"Errors: {self.opponent_errors}"
                )
            controllers.extend(
                random_controller.RandomController(f"Fallback{i}")
                for i in range(self.agents_no - len(controllers))
            )
        return controllers[:self.agents_no]

    def _training_karakin(self, name: str) -> KarakinController:
        return KarakinController(
            name,
            use_sb3=False,
            mcts_time_budget=self.karakin_mcts_time_budget,
            mcts_hard_time_limit=max(self.karakin_mcts_time_budget, 0.01),
        )

    def _selfplay_karakin(self, name: str) -> KarakinController:
        use_model = self.opponent_model_path.exists()
        return KarakinController(
            name,
            use_sb3=use_model,
            model_path=self.opponent_model_path if use_model else None,
            mcts_time_budget=self.karakin_mcts_time_budget,
            mcts_hard_time_limit=max(self.karakin_mcts_time_budget, 0.01),
        )

    def _team_controllers(self, limit: int, shuffle: bool) -> list[controller.Controller]:
        factories = self._team_agent_factories()
        if shuffle:
            factories = factories.copy()
            self.rng.shuffle(factories)
        team_controllers: list[controller.Controller] = []
        for name, factory in factories:
            try:
                team_controllers.append(factory(name))
            except Exception as exc:
                self.opponent_errors.append(f"{name}: {type(exc).__name__}: {exc}")
                continue
            if len(team_controllers) >= limit:
                break
        if self.strict_opponents and self.opponent_errors:
            raise RuntimeError(f"Opponent import/build errors: {self.opponent_errors}")
        return team_controllers

    def _team_agent_factories(self) -> list[tuple[str, ControllerFactory]]:
        factories: list[tuple[str, ControllerFactory]] = []
        try:
            from gupb.controller.jeffrey_e.jeffrey_e_controller import JeffreyEController

            factories.append(("JeffreyE", JeffreyEController))
        except Exception as exc:
            self.opponent_errors.append(f"JeffreyE import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.bigbot.bigbot import BIGbot

            factories.append(("BIGbot", BIGbot))
        except Exception as exc:
            self.opponent_errors.append(f"BIGbot import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.benjamin_netanyahu import BenjaminNetanyahu

            factories.append(("BenjaminNetanyahu", BenjaminNetanyahu))
        except Exception as exc:
            self.opponent_errors.append(f"BenjaminNetanyahu import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.biwakspot.biwakspot_controller import BiwakSpot

            factories.append(("BiwakSpot", BiwakSpot))
        except Exception as exc:
            self.opponent_errors.append(f"BiwakSpot import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.pudzian import Pudzian

            factories.append(("Pudzian", Pudzian))
        except Exception as exc:
            self.opponent_errors.append(f"Pudzian import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.czak_noris.czak_noris import CzakNoris

            factories.append(("CzakNoris", CzakNoris))
        except Exception as exc:
            self.opponent_errors.append(f"CzakNoris import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.the_trooper import TheTrooper

            factories.append(("TheTrooper", TheTrooper))
        except Exception as exc:
            self.opponent_errors.append(f"TheTrooper import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.blade_runner import BladeRunner

            factories.append(("BladeRunner", BladeRunner))
        except Exception as exc:
            self.opponent_errors.append(f"BladeRunner import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.syntax_terror import SyntaxTerror

            factories.append(("SyntaxTerror", SyntaxTerror))
        except Exception as exc:
            self.opponent_errors.append(f"SyntaxTerror import: {type(exc).__name__}: {exc}")
        try:
            from gupb.controller.bob import Bob

            factories.append(("Bob", Bob))
        except Exception as exc:
            self.opponent_errors.append(f"Bob import: {type(exc).__name__}: {exc}")
        return factories

    @staticmethod
    def _base_arenas() -> list[str]:
        return ["ordinary_chaos", "wasteland", "island", "dungeon", "archipelago"]

    @staticmethod
    def _dedupe_arenas(arena_names: list[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for arena_name in arena_names:
            if arena_name in seen:
                continue
            seen.add(arena_name)
            deduped.append(arena_name)
        return deduped

    @staticmethod
    def _existing_generated_arenas() -> list[str]:
        paths = sorted(Path("resources/arenas").glob("generated_*.gupb"))
        return [path.stem for path in paths]

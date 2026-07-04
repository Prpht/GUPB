from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import torch
from torch import nn

from gupb.model import characters

from .benjamin_netanyahu import BenjaminMode
from .benjamin_netanyahu import BenjaminNetanyahu
from .mode_features import TemporalFeatureTracker
from .mode_features import extract_benjamin_features

DEFAULT_BUNDLED_CHECKPOINT_PATH = str(Path(__file__).with_name("benjamin_weights.pt"))


class _InferenceQNetwork(nn.Module):
    def __init__(self, input_dim: int, output_dim: int) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, output_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.net(x)


class _CPUModePolicy:
    """
    CPU-only mode policy loader.
    """

    def __init__(self, checkpoint_path: str) -> None:
        payload = torch.load(checkpoint_path, map_location="cpu")
        self.input_dim = int(payload["input_dim"])
        self.action_dim = int(payload["action_dim"])
        state_dict = payload.get("state_dict", payload.get("policy_state_dict"))
        if state_dict is None:
            raise RuntimeError("Checkpoint does not contain state_dict.")

        self.device = torch.device("cpu")
        self.model = _InferenceQNetwork(self.input_dim, self.action_dim)
        self.model.load_state_dict(state_dict)
        self.model.eval()

    def select_mode_index(self, features) -> int:
        with torch.no_grad():
            state_tensor = torch.as_tensor(features, dtype=torch.float32, device=self.device).unsqueeze(0)
            q_values = self.model(state_tensor)
            return int(torch.argmax(q_values, dim=1).item())


class BenjaminNetanyahuDQN(BenjaminNetanyahu):
    """
    Final CPU-only inference bot for Benjamin mode selection.
    Fallback to heuristic selector is allowed only when loading weights fails.
    """

    def __init__(
            self,
            bot_name: str = "BenjaminNetanyahu",
            checkpoint_path: Optional[str] = None,
            mode_horizon_turns: int = 3,
            allow_oracle_menhir: bool = False,
    ) -> None:
        resolved_checkpoint_path = checkpoint_path or DEFAULT_BUNDLED_CHECKPOINT_PATH
        self.checkpoint_path = resolved_checkpoint_path
        self.policy: Optional[_CPUModePolicy] = None
        self._fallback_after_load_error: bool = False
        self._load_error: Optional[str] = None
        self._feature_tracker = TemporalFeatureTracker()
        try:
            self.policy = _CPUModePolicy(resolved_checkpoint_path)
        except Exception as exc:
            self.policy = None
            self._fallback_after_load_error = True
            self._load_error = f"{type(exc).__name__}: {exc}"

        super().__init__(
            bot_name=bot_name,
            mode_horizon_turns=mode_horizon_turns,
            mode_selector=self._select_mode,
            allow_oracle_menhir=allow_oracle_menhir,
        )

    def reset(self, game_no, arena_description) -> None:
        self._feature_tracker.reset()
        super().reset(game_no, arena_description)

    def _resolve_mode_choice(self, knowledge: characters.ChampionKnowledge) -> BenjaminMode:
        if self._pending_mode is not None:
            chosen_mode = self._pending_mode
            self._pending_mode = None
            return chosen_mode
        if self._mode_selector is None:
            raise RuntimeError("Mode selector is not configured for BenjaminNetanyahuDQN.")
        mode_choice = self._mode_selector(knowledge, self.current_mode, self._turns_taken)
        return self._normalise_mode_choice(mode_choice)

    def _select_mode(
            self,
            knowledge: characters.ChampionKnowledge,
            current_mode: BenjaminMode,
            turns_taken: int,
    ) -> BenjaminMode:
        _ = turns_taken
        temporal = self._feature_tracker.update(knowledge)
        if self.policy is None:
            if self._fallback_after_load_error:
                # Explicit fallback: only when loading DQN weights failed.
                return self._choose_mode(knowledge)
            raise RuntimeError("DQN policy is missing and no load-error fallback is allowed.")

        features = extract_benjamin_features(
            knowledge=knowledge,
            current_mode=current_mode,
            known_menhir=temporal.known_menhir,
            recent_damage_sum=temporal.recent_damage_sum,
            panic_turns=temporal.panic_turns,
            hp_delta_prev=temporal.hp_delta_prev,
            turns_since_enemy_seen=temporal.turns_since_enemy_seen,
            nearest_enemy_distance_delta=temporal.nearest_enemy_distance_delta,
            was_hit_recently_override=temporal.was_hit_recently,
        )
        if int(features.shape[0]) != self.policy.input_dim:
            raise RuntimeError(
                f"Feature size mismatch: got {int(features.shape[0])}, "
                f"checkpoint expects {self.policy.input_dim}."
            )

        mode_index = self.policy.select_mode_index(features)
        try:
            return self.mode_from_index(mode_index)
        except ValueError:
            raise RuntimeError(f"Invalid mode index predicted by policy: {mode_index}.")

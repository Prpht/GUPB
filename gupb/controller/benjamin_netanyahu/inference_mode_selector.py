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
        self._feature_tracker = TemporalFeatureTracker()
        if os.path.exists(resolved_checkpoint_path):
            self.policy = _CPUModePolicy(resolved_checkpoint_path)

        super().__init__(
            bot_name=bot_name,
            mode_horizon_turns=mode_horizon_turns,
            mode_selector=self._select_mode,
            allow_oracle_menhir=allow_oracle_menhir,
        )

    def reset(self, game_no, arena_description) -> None:
        self._feature_tracker.reset()
        super().reset(game_no, arena_description)

    def _select_mode(
            self,
            knowledge: characters.ChampionKnowledge,
            current_mode: BenjaminMode,
            turns_taken: int,
    ) -> BenjaminMode:
        _ = turns_taken
        temporal = self._feature_tracker.update(knowledge)
        if self.policy is None:
            return self._choose_mode(knowledge)

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
            return self._choose_mode(knowledge)

        mode_index = self.policy.select_mode_index(features)
        try:
            return self.mode_from_index(mode_index)
        except ValueError:
            return self._choose_mode(knowledge)

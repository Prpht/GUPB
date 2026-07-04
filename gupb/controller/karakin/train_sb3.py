from __future__ import annotations

import argparse
from pathlib import Path
import time

from stable_baselines3 import PPO
from stable_baselines3.common.callbacks import BaseCallback
from tqdm import tqdm

from .env import KarakinStrategicEnv
from .strategy import MODEL_PATH


def _tqdm_progress(*args, **kwargs):
    try:
        from tqdm.rich import tqdm as rich_tqdm

        return rich_tqdm(*args, **kwargs)
    except Exception:
        return tqdm(*args, **kwargs)


class ProgressCallback(BaseCallback):
    def __init__(self, total_timesteps: int, postfix_interval: int) -> None:
        super().__init__()
        self.total_timesteps = max(1, total_timesteps)
        self.postfix_interval = max(1, postfix_interval)
        self.started_at = 0.0
        self.last_progress = 0
        self.last_postfix = 0
        self.episodes = 0
        self.progress_bar = None

    def _on_training_start(self) -> None:
        self.started_at = time.monotonic()
        self.progress_bar = _tqdm_progress(
            total=self.total_timesteps,
            desc="Karakin PPO",
            unit="step",
            dynamic_ncols=True,
        )

    def _on_step(self) -> bool:
        dones = self.locals.get("dones")
        if dones is not None:
            self.episodes += int(sum(bool(done) for done in dones))

        current = min(self.num_timesteps, self.total_timesteps)
        if self.progress_bar is not None and current > self.last_progress:
            self.progress_bar.update(current - self.last_progress)
            self.last_progress = current

        if (
            self.progress_bar is not None
            and (
                self.num_timesteps == 1
                or self.num_timesteps - self.last_postfix >= self.postfix_interval
                or self.num_timesteps >= self.total_timesteps
            )
        ):
            elapsed = max(time.monotonic() - self.started_at, 1e-9)
            self.progress_bar.set_postfix(
                episodes=self.episodes,
                steps_s=f"{self.num_timesteps / elapsed:.2f}",
                elapsed_s=f"{elapsed:.1f}",
            )
            self.last_postfix = self.num_timesteps
        return self.num_timesteps < self.total_timesteps

    def _on_training_end(self) -> None:
        if self.progress_bar is None:
            return
        if self.last_progress < self.total_timesteps:
            self.progress_bar.update(self.total_timesteps - self.last_progress)
        self.progress_bar.close()


def train(
    total_timesteps: int,
    curriculum: str,
    generated_arenas: int,
    random_generated_sizes: bool,
    generated_prefix: str,
    arena_mode: str,
    agents_no: int,
    karakin_mcts_time_budget: float,
    opponent_model_path: Path,
    strict_opponents: bool,
    progress_interval: int,
    save_path: Path,
) -> None:
    env = KarakinStrategicEnv(
        curriculum=curriculum,
        generated_arenas=generated_arenas,
        random_generated_sizes=random_generated_sizes,
        generated_prefix=generated_prefix,
        arena_mode=arena_mode,
        agents_no=agents_no,
        karakin_mcts_time_budget=karakin_mcts_time_budget,
        opponent_model_path=opponent_model_path,
        strict_opponents=strict_opponents,
    )
    print(f"Training arenas: {env.arena_names}")
    print(f"Available team opponents: {[name for name, _ in env._team_agent_factories()]}")
    if env.opponent_errors:
        print(f"Opponent import/build errors: {env.opponent_errors}")
        if strict_opponents:
            raise RuntimeError(f"Strict opponent mode failed: {env.opponent_errors}")
    model = PPO(
        "MlpPolicy",
        env,
        verbose=0,
        n_steps=256,
        batch_size=64,
        gamma=0.96,
        learning_rate=3e-4,
    )
    progress_callback = ProgressCallback(total_timesteps, progress_interval)
    model.learn(
        total_timesteps=total_timesteps,
        callback=progress_callback,
        log_interval=1,
    )
    save_path.parent.mkdir(parents=True, exist_ok=True)
    model.save(save_path.as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Karakin strategic PPO policy.")
    parser.add_argument("--timesteps", type=int, default=20_000)
    parser.add_argument("--curriculum", choices=["teacher", "mixed", "selfplay"], default="mixed")
    parser.add_argument("--generated-arenas", type=int, default=10)
    parser.add_argument("--fixed-generated-size", action="store_true")
    parser.add_argument("--generated-prefix", default="generated_train")
    parser.add_argument("--arena-mode", choices=["base", "generated", "mixed"], default="mixed")
    parser.add_argument("--agents", type=int, default=8)
    parser.add_argument("--karakin-mcts-time-budget", type=float, default=0.05)
    parser.add_argument("--opponent-model-path", type=Path, default=MODEL_PATH)
    parser.add_argument("--strict-opponents", action="store_true")
    parser.add_argument("--progress-interval", type=int, default=10)
    parser.add_argument("--save-path", type=Path, default=MODEL_PATH)
    args = parser.parse_args()

    train(
        total_timesteps=args.timesteps,
        curriculum=args.curriculum,
        generated_arenas=args.generated_arenas,
        random_generated_sizes=not args.fixed_generated_size,
        generated_prefix=args.generated_prefix,
        arena_mode=args.arena_mode,
        agents_no=args.agents,
        karakin_mcts_time_budget=args.karakin_mcts_time_budget,
        opponent_model_path=args.opponent_model_path,
        strict_opponents=args.strict_opponents,
        progress_interval=args.progress_interval,
        save_path=args.save_path,
    )


if __name__ == "__main__":
    main()

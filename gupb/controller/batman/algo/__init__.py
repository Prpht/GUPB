from abc import ABC, abstractmethod
from dataclasses import dataclass
from stable_baselines3.common.off_policy_algorithm import OffPolicyAlgorithm
from stable_baselines3.common.vec_env import DummyVecEnv
import stable_baselines3.dqn as dqn

from gupb.controller.batman.environment import GUPBEnv


@dataclass
class AlgoConfig:
    learning_rate: float = 0.005
    batch_size: int = 32
    buffer_size: int = 1000
    learning_starts: int = 100
    tau: float = 0.05
    gamma: float = 0.98


class SomeAlgo(ABC):
    def __init__(self, env: GUPBEnv, config: AlgoConfig) -> None:
        self._algo = self._build_algo(env, config)

    def train(self, time_steps: int) -> None:
        """where time steps is number of env steps"""
        self._algo.learn(time_steps)

    def save(self, path: str) -> None:
        self._algo.save(path)

    def load(self, path: str) -> None:
        self._algo.load(path)

    @abstractmethod
    def _build_algo(self, env, config: AlgoConfig) -> OffPolicyAlgorithm:
        raise NotImplementedError()


class DQN(SomeAlgo):
    def _build_algo(self, env, config: AlgoConfig) -> OffPolicyAlgorithm:
        return dqn.DQN(
            policy=dqn.MlpPolicy,
            env=env,
            learning_rate=config.learning_rate,
            batch_size=config.batch_size,
            buffer_size=config.buffer_size,
            learning_starts=config.learning_starts,
            tau=config.tau,
            gamma=config.gamma,
            verbose=1,
        )

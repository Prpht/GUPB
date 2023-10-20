from abc import ABC, abstractmethod
from collections import namedtuple
from stable_baselines3.common.off_policy_algorithm import OffPolicyAlgorithm
from stable_baselines3.common.vec_env import DummyVecEnv
import stable_baselines3.dqn as dqn

from gupb.controller.batman.environment import GUPBEnv


AlgoConfig = namedtuple(
    "TrainingConfig",
    [
        "learning_rate",
        "batch_size",
        "buffer_size",
        "learning_starts",
        "tau",
        "gamma",
    ],
)


class SomeAlgo(ABC):
    def __init__(self, envs: list[GUPBEnv], config: AlgoConfig) -> None:
        env = DummyVecEnv([lambda: e for e in envs])
        self._algo = self._build_algo(env, config)

    def train(self, epochs: int) -> None:
        self._algo.learn(epochs)

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

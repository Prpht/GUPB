from abc import ABC, abstractmethod
from dataclasses import dataclass
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor
from stable_baselines3.common.off_policy_algorithm import OffPolicyAlgorithm
from stable_baselines3.common.vec_env import DummyVecEnv
import stable_baselines3.dqn as dqn

from gupb.controller.batman.rl.environment import GUPBEnv
from gupb.controller.batman.rl.environment.feature_extractors import NeighborhoodCNN


@dataclass
class AlgoConfig:
    learning_rate: float = 0.005
    batch_size: int = 32
    buffer_size: int = 1000
    learning_starts: int = 10
    tau: float = 0.05
    gamma: float = 0.98
    feature_extractor_class: BaseFeaturesExtractor = NeighborhoodCNN


class SomeAlgo(ABC):
    def __init__(self, env: GUPBEnv, config: AlgoConfig) -> None:
        self._algo = self._build_algo(env, config)

    @property
    def timesteps_limit(self) -> int:
        # just in case, TODO need to investigate
        return 5

    def train(self) -> None:
        """where time steps is number of env steps"""

        self._algo.learn(self.timesteps_limit)

    def set_timesteps(self, timesteps: int):
        self._algo.num_timesteps = timesteps

    def save(self, path: str) -> None:
        self._algo.save(path)
        self._algo.save_replay_buffer(f"{path}_reply_buffer")

    def load(self, path: str) -> None:
        self._algo.load(path)
        self._algo.load_replay_buffer(f"{path}_reply_buffer")

    @abstractmethod
    def _build_algo(self, env, config: AlgoConfig) -> OffPolicyAlgorithm:
        raise NotImplementedError()


class DQN(SomeAlgo):
    def _build_algo(self, env, config: AlgoConfig) -> OffPolicyAlgorithm:
        return dqn.DQN(
            policy=dqn.CnnPolicy,
            env=env,
            learning_rate=config.learning_rate,
            batch_size=config.batch_size,
            buffer_size=config.buffer_size,
            learning_starts=config.learning_starts,
            tau=config.tau,
            gamma=config.gamma,
            verbose=1,
            policy_kwargs={
                "features_extractor_class": config.feature_extractor_class,
            },
        )

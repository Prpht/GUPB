"""Definition of environment."""

import numpy as np
import gymnasium as gym
from gymnasium import spaces
from gymnasium.envs.registration import register

from gupb.model.characters import Action
from gpub.model.arenas import Arena


class GUPBEnv(gym.Env):
    """GUPB environment."""

    def __init__(self):
        """Initiate environment."""
        super().__init__()
        self.action_space = spaces.Discrete(len(Action))
        self.observation_space = spaces.Box(low=-1, high=1, shape=(100, 100), dtype=np.float32)

    def step(self, action):
        """Result of taking step in environment."""
        return observation, reward, terminated, truncated, info

    def reset(self, seed=None, options=None):
        """Called after every epoch."""
        return observation, info

    def render(self):
        ...

    def close(self):
        ...

register(
    id="GUPBEnv-Krombopulos-v2",
    entry_point=GUPBEnv
)

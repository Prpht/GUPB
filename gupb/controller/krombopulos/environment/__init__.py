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
        self.actions = list(Action)
        self.action_space = spaces.Discrete(len(Action))
        self.observation_space = spaces.Box(low=-1, high=1, shape=(100, 100), dtype=np.float32)

    def step(self, action):
        """Result of taking step in environment. Implements abstract method."""
        observation = ... # todo: should be the state of the environment
        reward = ... # todo: design reward function
        terminated = ...
        # do not limit the number of steps
        truncated = False 
        # this is for passing additional information, if there is ever the need to
        info = {} 
        return observation, reward, terminated, truncated, info

    def reset(self, seed=None, options=None):
        """Called after every epoch. Implements abstract method."""
        return observation, info

    def render(self):
        ...

    def close(self):
        ...

register(
    id="GUPBEnv-Krombopulos-v2",
    entry_point=GUPBEnv
)

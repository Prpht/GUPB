import gym
import gym.spaces
import numpy as np

from typing import List, Optional, Sequence, Tuple, Union

from gupb.controller.rl_agent import RlAgentController
from gupb.model.characters import Action


class GUPBEnv(gym.Env):
    metadata = {
        "render.modes": ["human", "rgb_array"],
    }

    def name():
        return "custom/gupb-env-v0"

    def __init__(
        self,
        controller: RlAgentController,
        grid_shape: Sequence[int],
        num_tiles_types: int,
    ):
        super().__init__()

        self.action_space = gym.spaces.Discrete(len(Action))

        self.observation_space = gym.spaces.Box(
            low=-0,
            high=num_tiles_types,
            shape=grid_shape,
            dtype=np.int8,
        )

        self._controller = controller

    def render(self, *args, **kwargs):
        return self._observation()

    def step(self, action: int):
        # TODO apply action

        return self._observation(), self._reward(), self._is_termination_state(), {}

    def reset(self):
        return self._observation()

    def _reward(self):
        # TODO
        return 0

    def _observation(self):
        # TODO use self._controller.knowledge to compute observation
        return np.zeros_like(self.observation_space.shape)

    def _is_termination_state(self):
        # TODO
        return False

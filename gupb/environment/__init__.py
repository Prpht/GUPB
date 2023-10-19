import gym
import gym.spaces
import numpy as np

from typing import Sequence

from gupb.environment.observer import Observer, Observable
from gupb.model.characters import Action, ChampionKnowledge


class GUPBEnv(gym.Env, Observer[ChampionKnowledge], Observable[Action]):
    metadata = {
        "render.modes": ["human", "rgb_array"],
    }

    def name():
        return "custom/gupb-env-v0"

    def __init__(
        self,
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

        self._ignore_action = True

    def render(self, *args, **kwargs):
        return self._observation()

    def step(self, action: int):
        if not self._ignore_action:
            self.observable_state = Action(action)
        knowledge = self.wait_for_observed()
        # TODO use knowledge ito update observation and rward
        self._ignore_action = False
        return self._observation(), self._reward(), self._is_termination_state(), {}

    def reset(self):
        pass

    def _reward(self):
        # TODO
        return 0

    def _observation(self):
        # TODO
        return np.zeros_like(self.observation_space.shape)

    def _is_termination_state(self):
        # TODO
        return False

import gymnasium as gym
from gymnasium.envs.registration import register

import numpy as np
from typing import Any

from gupb.controller.batman.knowledge.knowledge import Knowledge

from gupb.controller.batman.rl.environment.observation import SomeObservation
from gupb.controller.batman.rl.environment.reward import SomeReward

from gupb.controller.batman.utils.observer import Observer, Observable

from gupb.model.characters import Action


class GUPBEnv(gym.Env, Observer[Knowledge], Observable[Action]):
    def __init__(self, reward: SomeReward, observation: SomeObservation):
        super().__init__()
        Observer.__init__(self)
        Observable.__init__(self)

        self.action_space = gym.spaces.Discrete(len(Action))

        self.observation_space = gym.spaces.Box(
            low=-0,
            high=1,
            shape=observation.observation_shape,
            dtype=np.float16,
        )

        self._reward = reward
        self._observation = observation

        self._actions = [action for action in Action]

    def render(self, *args, **kwargs):
        pass

    def step(self, action_idx: int):
        self.observable_state = self._actions[action_idx]
        knowledge = self.wait_for_observed()

        obs = self._observation(knowledge)
        reward = self._reward(knowledge)
        done = knowledge.episode == 0
        truncated = False
        info = {}

        return obs, reward, done, truncated, info

    def reset(
        self, *, seed: int | None = None, options: dict[str, Any] | None = None
    ) -> tuple[Any, dict[str, Any]]:
        knowledge = self.wait_for_observed()
        obs = self._observation(knowledge)
        info = {}

        return obs, info


register(
    id="GUPBBatman-v0",
    entry_point="gupb.controller.batman.environment:GUPBEnv",
)

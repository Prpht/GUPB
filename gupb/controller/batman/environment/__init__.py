import gym
import gym.spaces
import numpy as np

from gupb.controller.batman.environment.knowledge import Knowledge
from gupb.controller.batman.environment.observation import SomeObservation
from gupb.controller.batman.environment.observer import Observer, Observable
from gupb.controller.batman.environment.reward import SomeReward
from gupb.model.characters import Action


class GUPBEnv(gym.Env, Observer[Knowledge], Observable[Action]):
    metadata = {
        "render.modes": ["human", "rgb_array"],
    }

    def name():
        return "custom/gupb-env-v0"

    def __init__(self, reward: SomeReward, observation: SomeObservation):
        super().__init__()

        self.action_space = gym.spaces.Discrete(len(Action))

        self.observation_space = gym.spaces.Box(
            low=-0,
            high=1,
            shape=observation.observation_shape,
            dtype=np.float16,
        )

        self._ignore_action = True

        self._reward = reward
        self._observation = observation

    def render(self, *args, **kwargs):
        pass

    def step(self, action: int):
        if not self._ignore_action:
            self.observable_state = Action(action)
        self._ignore_action = False

        knowledge = self.wait_for_observed()

        return (
            self._observation(knowledge),
            self._reward(knowledge),
            self._is_termination_state(),
            {},
        )

    def reset(self):
        pass

    def _is_termination_state(self):
        # TODO
        return False

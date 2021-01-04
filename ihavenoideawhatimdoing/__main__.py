import gym
from gym import spaces
from gupb.__main__ import main
import numpy as np
from observation_encoding import encode_observation
from openaigym_env import *


class CustomEnv(gym.Env):
    """Custom Environment that follows gym interface"""
    metadata = {'render.modes': ['human']}
    N_DISCRETE_ACTIONS = 5
    HEIGHT = 20
    WIDTH = 10
    N_CHANNELS = 3

    def __init__(self, game):
        super(CustomEnv, self).__init__()  # Define action and observation space
        # They must be gym.spaces objects    # Example when using discrete actions:
        self.action_space = spaces.Discrete(CustomEnv.N_DISCRETE_ACTIONS)  # Example for using image as input:
        self.observation_space = spaces.Box(low=0, high=1, shape=
                                            (CustomEnv.HEIGHT, CustomEnv.WIDTH, CustomEnv.N_CHANNELS), dtype=np.uint8)
        self.game = game

    def step(self, action):
        game.cycle()
        champion = list(filter(lambda c: c.controller.name() == 'IHaveNoIdeaWhatImDoingController', game.champions))[0]
        done = False
        if champion.controller.health <= 1:
            done = True

        x_dist = np.abs(champion.position.x - game.arena.menhir_position.x)
        y_dist = np.abs(champion.position.y - game.arena.menhir_position.y)
        dist = np.sqrt(x_dist ** 2 + y_dist ** 2)
        reward = -dist
        obs = encode_observation(champion.controller.knowledge)

        return obs, reward, done, {}

    def reset(self):
        game = main(prog_name='python -m gupb')
        game.cycle()
        champion = list(filter(lambda c: c.controller.name() == 'IHaveNoIdeaWhatImDoingController', game.champions))[0]

        return encode_observation(champion.controller.knowledge)

    def render(self, mode='human', close=False):
        pass


if __name__ == '__main__':

    game = main(prog_name='python -m gupb')

    env = CustomEnv(game)
    init_obs = env.reset()

    run_training(env)

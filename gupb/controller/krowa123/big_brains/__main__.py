from __future__ import unicode_literals

import tensorflow as tf
from rl.agents import DQNAgent
from rl.memory import SequentialMemory
from rl.policy import BoltzmannQPolicy
from tensorflow.keras.optimizers import Adam

tf.config.set_visible_devices([], 'GPU')

from gupb.controller.krowa123.big_brains.controller import create_model
from gupb.controller.krowa123.big_brains.env import Env
from gupb.__main__ import load_initial_config


if __name__ == '__main__':
    current_config = load_initial_config("gupb/default_config.py")
    env = Env(current_config, )

    actions_n = env.action_space.n

    model = create_model(env.observation_space.shape, actions_n)

    print(model.summary())
    memory = SequentialMemory(limit=50000, window_length=10)
    policy = BoltzmannQPolicy()
    agent = DQNAgent(model=model, memory=memory, nb_actions=actions_n, nb_steps_warmup=10, policy=policy)
    agent.compile(Adam(lr=1e-4), metrics=['mae'])
    # # agent.load_weights('weights.h5f')
    # agent.fit(env, nb_steps=50000, visualize=False, verbose=2)
    #
    # agent.save_weights('weights.h5f', overwrite=True)


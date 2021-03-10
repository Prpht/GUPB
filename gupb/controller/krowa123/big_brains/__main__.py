# import tensorflow as tf

# gpus = tf.config.experimental.list_physical_devices('GPU')
# for gpu in gpus:
#   tf.config.experimental.set_memory_growth(gpu, True)
# tf.config.set_visible_devices([], 'GPU')

from gupb.__main__ import load_initial_config

from env import Env
from agent import DQNAgent

if __name__ == '__main__':
    current_config = load_initial_config("gupb/default_config.py")
    env = Env(current_config, )

    actions_n = env.action_space.n
    agent = DQNAgent(env, "menhir_adam")
    agent.run()
    agent.save(agent.Model_name)
    # agent.test()


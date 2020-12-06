from __future__ import unicode_literals

import click
import tensorflow as tf
from rl.agents import SARSAAgent
from tensorflow.keras.optimizers import Adam

tf.config.set_visible_devices([], 'GPU')

from gupb.controller.krowa123.big_brains.controller import create_model
from gupb.__main__ import configure_logging, load_initial_config, configuration_inquiry
from .env import Env


@click.command()
@click.option('-c', '--config_path', default='gupb/default_config.py',
              type=click.Path(exists=True), help="The path to run configuration file.")
@click.option('-i', '--inquiry',
              is_flag=True, help="Whether to configure the runner interactively on start.")
@click.option('-l', '--log_directory', default='results',
              type=click.Path(exists=False), help="The path to log storage directory.")
def main(config_path: str, inquiry: bool, log_directory: str) -> None:
    configure_logging(log_directory)
    current_config = load_initial_config(config_path)
    current_config = configuration_inquiry(current_config) if inquiry else current_config

    env = Env(current_config, )

    actions_n = env.action_space.n

    model = create_model(env.observation_space.shape, actions_n)

    print(model.summary())

    sarsa = SARSAAgent(model=model, nb_actions=actions_n, nb_steps_warmup=10)
    sarsa.compile(Adam(lr=1e-4))
    # sarsa.load_weights('sarsa_weights.h5f')
    sarsa.fit(env, nb_steps=50000, visualize=False, verbose=2)

    sarsa.save_weights('sarsa_weights.h5f', overwrite=True)


if __name__ == '__main__':
    main()

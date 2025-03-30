import click

from gupb.controller.neat.model_config import NeatConfig
from gupb.controller.neat.neat_training.train_neat import run_neat_training


@click.command()
@click.option('--neat_config', default='default_config',
              help="Neat config file to load during training.")
@click.option('--network_name', default='test_network',
              help="Neat network name that will be saved.")
@click.option('--n', default=2, type=int,
              help="Number of generations during training.")
@click.option('--evaluator', required=True,
              help="Evaluator name added to 'create_evaluator'.")
def neat(neat_config: str, network_name: str, n: int, evaluator: str):
    neat_config = NeatConfig.load_neat_config(neat_config)
    winner = run_neat_training(neat_config, n, evaluator)
    NeatConfig.save_winner_network(winner, network_name)


if __name__ == '__main__':
    neat(prog_name='python -m gupb')

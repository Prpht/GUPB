import os
import pickle

import neat

_NEAT_PATH = 'gupb/controller/neat/'


class NeatConfig:
    def __init__(self, network_name, config_name):
        neat_config = self.load_neat_config(config_name)
        network_path = os.path.join(_NEAT_PATH, f"networks/{network_name}.pkl")
        self._network = None

        try:
            with open(network_path, "rb") as f:
                best_genome = pickle.load(f)

            self._network = neat.nn.FeedForwardNetwork.create(best_genome, neat_config)
        except FileNotFoundError:
            print(f"Network {network_name} is not found.")

    @property
    def network(self):
        return self._network

    @staticmethod
    def load_neat_config(config_name) -> neat.Config:
        config_path = os.path.join(_NEAT_PATH, f"neat_configs/{config_name}.txt")
        return neat.Config(neat.DefaultGenome, neat.DefaultReproduction,
                           neat.DefaultSpeciesSet, neat.DefaultStagnation,
                           config_path)

    @staticmethod
    def save_winner_network(winner, network_name):
        network_path = os.path.join(_NEAT_PATH, f"networks/{network_name}.pkl")
        with open(network_path, "wb") as f:
            pickle.dump(winner, f)

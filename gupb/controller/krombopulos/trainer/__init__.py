"""Module for managing the controller's training."""

import os

from threading import Thread

from stable_baselines3 import DQN
from stable_baselines3.deepqn.policies import CnnPolicy

from gupb.controller.krombopulos.environment import GUPBEnv


class Trainer:
    def __init__(self, controller, save_path):
        # path for saving trained model (for passing model between games)
        self.save_path = save_path
        # make sure directories exist
        os.makedirs(self.save_path, exist_ok=True)
        # initialize environment
        self.env = GUPBEnv()
        # initialize training model (algorithm)
        self.model = DQN(CnnPolicy, self.env)
    
    def start(self):
        """Prepare trainer for next game."""
        # load model from last games if it exists
        try:
            self.model.load(self.save_path)
        except ValueError:
            # do nothing
            ...
        # move training to new thread for efficiency
        self.training = Thread(target=self.model.train)
        self.training.start()

    def stop(self, save):
        """Clean up trainer after game."""
        self.training.join()
        if save:
            self.model.save(self.save_path)

import json
import os
import numpy as np


class Model:

    @staticmethod
    def from_config(name, learning=True):
        path = os.path.join("./bb_bot_resources", name)
        config_path = os.path.join(path, "config.json")

        with open(config_path, 'r') as config_file:
            config = json.load(config_file)

        model = Model(config, learning=learning)
        model.load_snapshot('latest')
        return model

    @staticmethod
    def new_model(name, map_w, map_h):
        path = os.path.join("./bb_bot_resources", name)
        config_path = os.path.join(path, "config.json")

        try:
            os.mkdir(path)
        except OSError:
            print(
                "Creation of the directory {} failed".format(path)
            )

        model_config = {
            'name': name,
            'map_w': map_w,
            'map_h': map_h,
            'epoch': 0
        }

        with open(config_path, 'w') as config_file:
            json.dump(model_config, config_file)

        model = Model(model_config, learning=True)
        model.snapshot()
        return model

    def __init__(self, config, learning=False):
        self.config = config
        self.learning = learning

        self.W = config['map_w']
        self.H = config['map_h']
        self.name = config['name']
        self.path = os.path.join("./bb_bot_resources", self.name)
        self.epoch = config['epoch']
        self.rewards = 0

        table_shape = (self.W, self.H, 4, 4)
        self.q_table = np.zeros(table_shape)

    def snapshot(self):
        model_path = os.path.join(self.path, "model_{}.npy".format(self.config["epoch"]))
        model_path_l = os.path.join(self.path, "model_latest.npy")
        config_path = os.path.join(self.path, "config.json")

        with open(config_path, 'w') as config_file:
            json.dump(self.config, config_file)

        if self.config["epoch"] % 100 == 0:
            np.save(model_path, self.q_table)
            np.save(model_path_l, self.q_table)


    def load_snapshot(self, epoch):
        model_path = os.path.join(self.path, "model_{}.npy".format(epoch))
        self.epoch = epoch
        self.q_table = np.load(model_path)

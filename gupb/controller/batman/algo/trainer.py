from threading import Thread

from gupb.controller.batman.algo import DQN, AlgoConfig

# from gupb.controller.batman.controller import BatmanController
from gupb.controller.batman.environment import GUPBEnv
from gupb.controller.batman.environment.observation import SimpleObservation
from gupb.controller.batman.environment.reward import (
    AccumulatedReward,
    MenhirProximityReward,
    UpdatedKnowledgeReward,
    StayingAliveReward,
)


# TODO config


class Trainer:
    def __init__(self, controller) -> None:
        # TODO observation config
        # observation
        neighborhood_range = 8
        observation_function = SimpleObservation(neighborhood_range)

        # TODO reward config
        # reward
        menhir_proximity = MenhirProximityReward(4, 20)
        updated_knowledge = UpdatedKnowledgeReward(7)
        staying_alive = StayingAliveReward()

        reward_function = AccumulatedReward(
            [(menhir_proximity, 0.2), (updated_knowledge, 0.3), (staying_alive, 0.5)]
        )

        # env
        self._env = GUPBEnv(reward_function, observation_function)
        self._env.attach(controller)
        controller.attach(self._env)

        # algo
        self._algo = DQN(self._env, AlgoConfig())

        # training
        self._trainig = Thread(target=self._training_function)

    def start(self):
        self._trainig.start()

    def _training_function(self):
        self._algo.train(10_000)

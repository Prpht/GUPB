from threading import Thread

from gupb.controller.batman.rl import DQN, AlgoConfig

from gupb.model.characters import CHAMPION_STARTING_HP

from gupb.controller.batman.rl.environment import GUPBEnv
from gupb.controller.batman.rl.environment.observation import SimpleObservation
from gupb.controller.batman.rl.environment.reward import (
    AccumulatedReward,
    MenhirProximityReward,
    MotionEntropyReward,
    UpdatedKnowledgeReward,
    StayingAliveReward,
    StayingHealthyReward,
    FindingWeaponReward,
)

from gupb.controller.batman.knowledge.knowledge import Knowledge


# TODO config


class Trainer:
    def __init__(self, controller, path_to_algo: str) -> None:
        self._path_to_algo = path_to_algo

        # TODO observation config
        # observation
        neighborhood_range = 20
        observation_function = SimpleObservation(neighborhood_range)

        # TODO reward config
        # reward
        menhir_proximity = MenhirProximityReward(4, 20)
        updated_knowledge = UpdatedKnowledgeReward(15, 4)
        motion_entropy = MotionEntropyReward(12)
        staying_alive = StayingAliveReward()
        staying_healthy = StayingHealthyReward(CHAMPION_STARTING_HP)
        finding_weapon = FindingWeaponReward(30)

        reward_function = AccumulatedReward(
            [
                (menhir_proximity, 5),
                (updated_knowledge, 2),
                (motion_entropy, 10),
                (staying_alive, 20),
                (staying_healthy, 15),
                (finding_weapon, 5),
            ]
        )

        # env
        self._env = GUPBEnv(reward_function, observation_function)
        self._env.attach(controller)
        controller.attach(self._env)

        # algo
        self._algo = DQN(self._env, AlgoConfig())

    def start(self, load: bool = True):
        try:
            self._algo.load(self._path_to_algo)
        except Exception:
            pass
        self._trainig = Thread(target=self._training_function)
        self._trainig.start()

    def next_step(self):
        self._algo.set_timesteps(0)

    def stop(self, knowledge_to_terminate: Knowledge, save: bool = True):
        # TODO is any other way?
        self._env.update(knowledge_to_terminate)
        self._algo.set_timesteps(self._algo.timesteps_limit)
        while self._trainig.is_alive():
            self._env.update(knowledge_to_terminate)
        self._trainig.join()
        if save:
            self._algo.save(self._path_to_algo)

    def _training_function(self):
        self._algo.train()

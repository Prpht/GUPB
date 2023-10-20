import random
import threading
from collections import namedtuple

from gupb.controller import Controller
from gupb.controller.random import RandomController
from gupb.controller.batman import BatmanController
from gupb.controller.batman.algo import DQN
from gupb.controller.batman.environment import GUPBEnv
from gupb.controller.batman.environment.observation import (
    SomeObservation,
    SimpleObservation,
)
from gupb.controller.batman.environment.reward import (
    SomeReward,
    AccumulatedReward,
    MenhirProximityReward,
    UpdatedKnowledgeReward,
    StayingAliveReward,
    WeightedReward,
)
from gupb.controller.batman.algo import AlgoConfig
from gupb.model.games import Game


TrainingConfig = namedtuple(
    "TrainingConfig",
    [
        "num_batmans",
        "num_random",
        "algo_config",
        "epochs",
        "games_per_epoch",
        "areans",
    ],
)


def create_observation_func() -> SomeObservation:
    neighborhood_range = 8
    return SimpleObservation(neighborhood_range)


def create_reward_function() -> SomeReward:
    menhir_proximity = MenhirProximityReward(4, 20)
    updated_knowledge = UpdatedKnowledgeReward(7)
    staying_alive = StayingAliveReward()

    reward = AccumulatedReward(
        [(menhir_proximity, 0.2), (updated_knowledge, 0.3), (staying_alive, 0.5)]
    )

    return reward


def create_batman(
    observation: SomeObservation, reward: SomeReward, name: str
) -> tuple[GUPBEnv, BatmanController]:
    env = GUPBEnv(reward, observation)
    controller = BatmanController(name)

    env.attach(controller)
    controller.attach(env)

    return env, controller


def run_game(arena: str, controllers: list[Controller]):
    game = Game(arena, controllers)
    while not game.finished:
        game.cycle()


def run_games(
    epochs: int,
    games_per_epoch: int,
    areans: list[str],
    controllers_for_games: list[list[Controller]],
):
    for epoch in range(epochs):
        print(f"starting {epoch} epoch")
        games = [
            threading.Thread(
                target=run_game, args=[random.choice(areans), controllers_for_games[i]]
            )
            for i in range(games_per_epoch)
        ]
        for game in games:
            game.start()
        for game in games:
            game.join()


def run_algo(epochs: int, envs: list[GUPBEnv], config: AlgoConfig):
    algo = DQN(envs, config)
    algo.train(epochs)


def run_training(config: TrainingConfig):
    observation = create_observation_func()
    # TODO - generate rewards so each batman has little different goal
    reward = create_reward_function()

    controllers_for_games = []
    batman_envs = [[] for _ in range(config.num_batmans)]

    for _ in range(config.games_per_epoch):
        batmans = [
            create_batman(observation, reward, f"batman ({i})")
            for i in range(config.num_batmans)
        ]
        randoms = [RandomController(f"random ({i})") for i in range(config.num_random)]

        envs = [env for env, _ in batmans]
        controllers = [batman for _, batman in batmans] + randoms

        controllers_for_games.append(controllers)

        for i in range(config.num_batmans):
            batman_envs[i].append(envs[i])

    algos = []
    for i, envs in zip(range(config.num_batmans), batman_envs):
        algos.append(
            threading.Thread(
                target=run_algo, args=[config.epochs, envs, config.algo_config]
            )
        )
    for algo in algos:
        algo.start()

    games = threading.Thread(
        target=run_games,
        args=[1, config.games_per_epoch, config.areans, controllers],
    )
    games.start()

    for algo in algos:
        algo.join()

    games.join()

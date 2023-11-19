from typing import Optional

import numpy as np
import random

from gupb import controller
from gupb.model import arenas

from gupb.controller.batman.heuristic.events import EventDetector
from gupb.controller.batman.heuristic.navigation import Navigation
from gupb.controller.batman.heuristic.passthrough import Passthrough
from gupb.controller.batman.heuristic.strategies import StrategiesFactory

from gupb.controller.batman.knowledge.knowledge import Knowledge

from gupb.controller.batman.trainer import Trainer

from gupb.model.characters import Action, ChampionKnowledge, Tabard


class BatmanHeuristicsController(controller.Controller):
    def __init__(self, name: str) -> None:
        super().__init__()

        self._name = name
        self._episode = 0
        self._game = 0

        self._event_detector = EventDetector()

        self._trainer = Trainer()
        self._params = np.array([3])  # default

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        assert (
            self._knowledge is not None and self._navigation is not None
        ), "Reset was not called before first decide() call"

        self._episode += 1
        self._knowledge.update(knowledge, self._episode)

        if self._episode == 1:
            # here becasue we need to know Batman position
            self._parametrize_strategies()

        events = self._event_detector.detect(self._knowledge)

        action = None
        changed_strategies = 0
        while action is None and changed_strategies < 10:
            action, strategy = self._current_strategy.decide(
                self._knowledge, events, self._navigation
            )
            self._current_strategy = self._strategies.get(strategy)
            changed_strategies += 1

        # this should never happen (but it does happen xd)
        if action is None:
            # print('WARNING: endless loop in strategies changing')
            action = Action.DO_NOTHING

        return action

    def praise(self, score: int) -> None:
        self._trainer.add_to_buffer(self._state, self._params, score / 1000)
        self._trainer.force_training_end()

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._episode = 0
        self._game += 1
        self._knowledge = Knowledge(arena_description)
        self._navigation = Navigation(self._knowledge)
        self._passthrough = Passthrough(self._knowledge, self._navigation, samples=1000)

        if game_no % 3 == 0 and game_no > 0:
            self._trainer.train()

    def _parametrize_strategies(self):
        self._state = np.concatenate(
            (
                self._knowledge.arena.one_hot_encoding(),
                np.array([self._passthrough._passthrough]),
            )
        )

        self._strategies = StrategiesFactory(self._passthrough)
        self._init_position = np.array(self._knowledge.champion.position, dtype=int)
        self._params = self._select_params(self._epsilon())
        self._strategies.set_params(self._params)  # type: ignore
        self._current_strategy = self._strategies.get("hiding")

    def _epsilon(self):
        init_eps = 0.7
        eps_decay = 0.995
        min_eps = 0.1

        return max(min_eps, init_eps * eps_decay**self._game)

    def _select_params(self, epsilon):
        possible_params = list(self._strategies.possible_params())
        if random.random() < epsilon:
            return np.concatenate((random.choice(possible_params), self._init_position))
        else:
            best_reward = 0
            best_params = self._params
            for params in possible_params:
                params = np.concatenate((params, self._init_position))
                reward = self._trainer.guess_reward(self._state, params)
                if reward > best_reward:
                    best_reward = reward
                    best_params = params
            return best_params

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.STRIPPED  # TODO change to batman

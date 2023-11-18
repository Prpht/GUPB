from typing import Optional

import numpy as np

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
        self._last_params = np.array([5])  # default

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        assert (
            self._knowledge is not None and self._navigation is not None
        ), "Reset was not called before first decide() call"

        self._episode += 1
        self._knowledge.update(knowledge, self._episode)

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
        self._trainer.add_to_buffer(self._last_state, self._last_params, score / 1000)
        self._trainer.force_training_end()

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._episode = 0
        self._game += 1
        self._knowledge = Knowledge(arena_description)
        self._navigation = Navigation(self._knowledge)
        self._passthrough = Passthrough(self._knowledge, self._navigation, samples=1000)

        self._last_state = self._knowledge.arena.one_hot_encoding()
        best_reward = 0

        self._strategies = StrategiesFactory(self._passthrough)
        for params in self._strategies.possible_params():
            reward = self._trainer.guess_reward(self._last_state, params)
            if reward > best_reward:
                best_reward = reward
                self._last_params = params

        self._strategies.set_params(self._last_params)  # type: ignore
        self._current_strategy = self._strategies.get("hiding")

        if game_no % 5 == 0 and game_no > 0:
            self._trainer.train()

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.STRIPPED  # TODO change to batman

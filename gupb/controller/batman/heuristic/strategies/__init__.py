from .defending import DefendingStrategy
from .fighting import FightingStrategy
from .hiding import HidingStrategy
from .rotating import RotatingStrategy
from .running_away import RunningAwayStrategy
from .scouting import ScoutingStrategy

from gupb.controller.batman.heuristic.passthrough import Passthrough

from typing import Sequence
import numpy as np

from itertools import product


class StrategiesFactory:
    def __init__(self, passthrough: Passthrough) -> None:
        self._passthrough = passthrough
        self._params = np.array([3])
        self._lower_params_limit = np.array([2], dtype=int)
        self._upper_params_limit = np.array([5], dtype=int)
        self._set_strategies()

    def _set_strategies(self):
        self._startegies = {
            "defending": DefendingStrategy(),
            "fighting": FightingStrategy(),
            "rotating": RotatingStrategy(),
            "running_away": RunningAwayStrategy(),
            "scouting": ScoutingStrategy(),
            "hiding": HidingStrategy(
                self._passthrough,
                safe_hampions_alive_count=self.safe_hampions_alive_count,
            ),
        }

    def possible_params(self):
        possible_params = [
            [p for p in range(lower, upper + 1)]
            for lower, upper in zip(self._lower_params_limit, self._upper_params_limit)
        ]
        for params in product(*possible_params):
            yield np.array(params)

    def set_params(self, params: Sequence[float]):
        """params should be from range 0 to 1"""
        self._params = params
        self._set_strategies()

    @property
    def safe_hampions_alive_count(self) -> int:
        return int(self._params[0])

    def get(self, startegy: str):
        return self._startegies[startegy]

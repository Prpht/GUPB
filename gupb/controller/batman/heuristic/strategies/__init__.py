from .defending import DefendingStrategy
from .fighting import FightingStrategy
from .hiding import HidingStrategy
from .rotating import RotatingStrategy
from .running_away import RunningAwayStrategy
from .scouting import ScoutingStrategy

from gupb.controller.batman.heuristic.passthrough import Passthrough


from typing import Sequence
import numpy as np


class StrategiesFactory:
    def __init__(self, passthrough: Passthrough) -> None:
        self._passthrough = passthrough
        self._params = np.array([5])
        self._lower_params_limit = np.array([3], dtype=int)
        self._upper_params_limit = np.array([8], dtype=int)

    def set_params(self, params: Sequence[float]):
        """params should be from range 0 to 1"""
        ranges = self._upper_params_limit - self._lower_params_limit
        self._params = np.array(params) * ranges + self._lower_params_limit

    @property
    def safe_hampions_alive_count(self) -> int:
        return int(self._params[0])

    def get(self, startegy: str):
        if startegy == "defending":
            return DefendingStrategy()
        if startegy == "fighting":
            return FightingStrategy()
        if startegy == "rotating":
            return RotatingStrategy()
        if startegy == "running_away":
            return RunningAwayStrategy()
        if startegy == "scouting":
            return ScoutingStrategy()
        else:  # if startegy == "hiding": (Default)
            return HidingStrategy(
                self._passthrough,
                safe_hampions_alive_count=self.safe_hampions_alive_count,
            )

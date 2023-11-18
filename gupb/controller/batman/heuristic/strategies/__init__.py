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
        self._params = np.array(params)

    def _denormalize_param(self, param_id: int) -> float:
        lower_limit = self._lower_params_limit[param_id]
        range = self._upper_params_limit[param_id] - lower_limit
        return self._params[param_id] * range + lower_limit

    @property
    def safe_hampions_alive_count(self) -> int:
        return int(self._denormalize_param(0))

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

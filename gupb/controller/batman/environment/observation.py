from abc import ABC, abstractmethod, abstractproperty
import numpy as np
from typing import Sequence

from gupb.controller.batman.environment.knowledge import Knowledge


class SomeObservation(ABC):
    @abstractproperty
    def observation_shape(self) -> Sequence[int]:
        raise NotImplementedError()

    @abstractmethod
    def _observation(self, knowledge: Knowledge) -> np.ndarray:
        raise NotImplementedError()

    def __call__(self, knowledge: Knowledge) -> np.ndarray:
        return self._observation(knowledge)


class SimpleObservation(SomeObservation):
    def __init__(
        self, tile_type_mapping: dict[str, int], neighborhood_range: int
    ) -> None:
        self._tile_type_mapping = tile_type_mapping
        self._range = neighborhood_range

    @property
    def observation_shape(self) -> Sequence[int]:
        return (max(self._tile_type_mapping.values()), self._range, self._range)

    def _observation(self, knowledge: Knowledge) -> np.ndarray:
        observation = np.zeros(self.observation_shape)
        for (x, y), tile in knowledge.arena.explored_map.items():
            if tile.type is not None:
                type = self._tile_type_mapping[tile.type]
                observation[type, x, y] = 1
        return observation

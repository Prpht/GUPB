from abc import ABC, abstractmethod, abstractproperty
import numpy as np
from typing import Sequence

from gupb.controller.batman.environment.knowledge import Knowledge, TileKnowledge
from gupb.model.coordinates import Coords, sub_coords, add_coords


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
    def __init__(self, neighborhood_range: int) -> None:
        self._range_vec = Coords(neighborhood_range, neighborhood_range)

    @property
    def num_types(self) -> int:
        # TODO
        return 1

    @property
    def observation_shape(self) -> Sequence[int]:
        return (
            self.num_types,
            2 * self._range_vec.x + 1,
            2 * self._range_vec.y + 1,
        )

    def _observation(self, knowledge: Knowledge) -> np.ndarray:
        observation = np.zeros(self.observation_shape)
        for tile in knowledge.arena.explored_map.values():
            position = self._position(knowledge.position, tile.coords)
            if tile.type is not None and position is not None:
                type = self._tile_type_mapping(tile)
                observation[type, position.x, position.y] = 1
        return observation

    def _position(self, champion: Coords, other: Coords) -> Coords | None:
        diff = sub_coords(other, champion)
        position = add_coords(diff, self._range_vec)
        limit = position.x < self.observation_shape[1]
        if (
            position.x >= 0
            and position.y >= 0
            and position.x < limit
            and position.y < limit
        ):
            return position
        else:
            return None

    def _tile_type_mapping(self, tile: TileKnowledge) -> int:
        # TODO
        return 0

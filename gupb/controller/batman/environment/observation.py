from abc import ABC, abstractmethod, abstractproperty
import numpy as np
from typing import Sequence

from gupb.controller.batman.environment.knowledge import Knowledge, TileKnowledge
from gupb.controller.batman.environment.analyzers.knowledge_analyzer import KnowledgeAnalyzer
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
    def embedding_size(self) -> int:
        """
        Embedding size is the number of various features, which encode all the information about a single tile.
        """
        return 24  # TODO do we need to extract this to a separate class to make this value automatically updated?

    @property
    def observation_shape(self) -> Sequence[int]:
        return (
            self.embedding_size,
            2 * self._range_vec.x + 1,
            2 * self._range_vec.y + 1,
        )

    def _tile_embedding(self, knowledge: Knowledge, position: Coords) -> np.ndarray:
        analyzer = KnowledgeAnalyzer(knowledge)
        tile_analyzer = analyzer.tile_analyzer(position)

        embedding = np.array([
            # tile properties (7)
            tile_analyzer.is_out_of_map,
            tile_analyzer.is_wall,
            tile_analyzer.is_water,
            tile_analyzer.is_manhir,
            tile_analyzer.is_attacked,
            tile_analyzer.has_mist,
            tile_analyzer.last_seen,

            # weapons (5)
            tile_analyzer.has_knife,
            tile_analyzer.has_sword,
            tile_analyzer.has_bow,
            tile_analyzer.has_axe,
            tile_analyzer.has_amulet,

            # characters (11)
            tile_analyzer.has_enemy,
            tile_analyzer.character_health,
            tile_analyzer.has_character_with_knife,
            tile_analyzer.has_character_with_sword,
            tile_analyzer.has_character_with_bow,
            tile_analyzer.has_character_with_axe,
            tile_analyzer.has_character_with_amulet,
            tile_analyzer.has_character_facing_up,
            tile_analyzer.has_character_facing_down,
            tile_analyzer.has_character_facing_left,
            tile_analyzer.has_character_facing_right,

            # consumables (1)
            tile_analyzer.has_potion,
        ])

        return embedding.astype(np.float32)

    def _observation(self, knowledge: Knowledge) -> np.ndarray:
        observation = np.zeros(self.observation_shape)
        top_left_position = sub_coords(knowledge.position, self._range_vec)
        for x, y in np.ndindex(observation.shape[1:]):
            map_position = add_coords(Coords(x, y), top_left_position)
            observation[:, x, y] = self._tile_embedding(knowledge, map_position)
        return observation

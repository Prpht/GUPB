from abc import ABC, abstractmethod
import numpy as np
import scipy.stats as stats

from gupb.controller.batman.environment.knowledge import Knowledge
from gupb.model.coordinates import Coords


class SomeReward(ABC):
    @abstractmethod
    def _compute(self, knowledge: Knowledge) -> float:
        raise NotImplementedError()

    def __call__(self, knowledge: Knowledge) -> float:
        """returns reward in the range from -1 to 1"""
        return self._compute(knowledge)


Weight = float
WeightedReward = tuple[SomeReward, Weight]


class AccumulatedReward(SomeReward):
    def __init__(self, wighted_reward: list[WeightedReward]) -> None:
        weights = [weight for _, weight in wighted_reward]
        self._total_weight = sum(weights)
        self._wighted_reward = wighted_reward

    def _compute(self, knowledge: Knowledge) -> float:
        return (
            sum([reward(knowledge) * weight for reward, weight in self._wighted_reward])
            / self._total_weight
        )


def distance(a: Coords, b: Coords) -> float:
    return np.linalg.norm(np.array(a) - np.array(b))


class MenhirProximityReward(SomeReward):
    def __init__(
        self, save_distance_to_menhir: float, episodes_to_found_menhir: int
    ) -> None:
        self._save_distance_to_menhir = save_distance_to_menhir
        self._episodes_to_found_menhir = episodes_to_found_menhir

    def _compute(self, knowledge: Knowledge) -> float:
        if knowledge.arena.menhir_position is None:
            penalty = min(
                knowledge.episode / self._episodes_to_found_menhir,
                1.0,
            )
        else:
            distance_to_manhir = distance(
                knowledge.position, knowledge.arena.menhir_position
            )
            penalty = min(
                distance_to_manhir / self._save_distance_to_menhir,
                1.0,
            )
        return 1 - 2 * penalty**2


class UpdatedKnowledgeReward(SomeReward):
    def __init__(self, uptodate_till: int) -> None:
        self._uptodate_till = uptodate_till

    def _compute(self, knowledge: Knowledge) -> float:
        episodes = np.array(
            [tile.last_seen for tile in knowledge.arena.explored_map.values()]
        )
        if episodes.size == 0:
            return 0
        penalty = np.mean((episodes - knowledge.episode) / self._uptodate_till)
        return float(1 - 2 * penalty**2)


class MotionEntropyReward(SomeReward):
    def __init__(self, positions_buffer_size) -> None:
        self._max_size = positions_buffer_size
        self._buffer = []

    def _compute(self, knowledge: Knowledge) -> float:
        self._buffer.append(knowledge.position)
        if len(self._buffer) > self._max_size:
            self._buffer.pop()
        xs = [x for x, _ in self._buffer]
        ys = [y for _, y in self._buffer]
        H = stats.entropy(xs) + stats.entropy(ys)
        return np.tanh(H) - 1


class FrequentAttackingReward(SomeReward):
    # TODO
    pass


class StayingAliveReward(SomeReward):
    def __init__(self) -> None:
        self._total_chempions: int | None = None

    def _compute(self, knowledge: Knowledge) -> float:
        if self._total_chempions is None:
            self._total_chempions = knowledge.champions_alive
        return 1 - knowledge.champions_alive / self._total_chempions

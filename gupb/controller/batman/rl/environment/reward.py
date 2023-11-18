from abc import ABC, abstractmethod
from collections import deque
import numpy as np
import scipy.stats as stats

from gupb.controller.batman.knowledge.knowledge import Knowledge
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
    def __init__(self, weighted_reward: list[WeightedReward]) -> None:
        weights = [weight for _, weight in weighted_reward]
        self._total_weight = sum(weights)
        self._weighted_reward = weighted_reward

    def _compute(self, knowledge: Knowledge) -> float:
        return (
            sum(
                [reward(knowledge) * weight for reward, weight in self._weighted_reward]
            )
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
            distance_to_menhir = distance(
                knowledge.position, knowledge.arena.menhir_position
            )
            penalty = min(
                distance_to_menhir / self._save_distance_to_menhir,
                1.0,
            )
        return 1 - 2 * penalty**2


class UpdatedKnowledgeReward(SomeReward):
    def __init__(self, uptodate_till: int, radius: int) -> None:
        self._uptodate_till = uptodate_till
        self._radius = radius

    def _compute(self, knowledge: Knowledge) -> float:
        episodes = np.array(
            [
                tile.last_seen
                for tile in list(knowledge.arena.explored_map.values())
                if distance(knowledge.position, tile.coords) <= self._radius
            ]
        )
        if episodes.size == 0:
            return 0
        penalty = min(
            np.mean((knowledge.episode - episodes) / self._uptodate_till), 1.0
        )
        return float(1 - 2 * penalty**2)


class MotionEntropyReward(SomeReward):
    def __init__(self, positions_buffer_size: int) -> None:
        self._max_size = positions_buffer_size
        self._buffer = deque(maxlen=self._max_size)

    def _compute(self, knowledge: Knowledge) -> float:
        self._buffer.append(knowledge.position)
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


class StayingHealthyReward(SomeReward):
    def __init__(self, acceptable_health: int) -> None:
        self._acceptable_health = acceptable_health

    def _compute(self, knowledge: Knowledge) -> float:
        tile = knowledge.arena.explored_map.get(knowledge.position)
        if tile is None:
            return 0
        champion = tile.character
        penalty = 1 - champion.health / self._acceptable_health
        return 1 - 2 * penalty**2


class FindingWeaponReward(SomeReward):
    def __init__(self, episodes_to_find_weapon: int) -> None:
        self._episodes_to_find_weapon = episodes_to_find_weapon

    def _compute(self, knowledge: Knowledge) -> float:
        tile = knowledge.arena.explored_map.get(knowledge.position)
        if tile is None:
            return 0

        champion = tile.character
        weapon_name = champion.weapon.name

        if weapon_name == "knife":
            penalty = min(
                knowledge.episode / self._episodes_to_find_weapon,
                1.0,
            )
        else:
            penalty = 0.0

        return 1 - 2 * penalty**2

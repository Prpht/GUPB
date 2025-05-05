import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize

from gupb.controller.bupg.strategies.base import BaseStrategy
from gupb.controller.bupg.knowledge.map import MapKnowledge
from gupb.model import characters
from gupb.model.effects import EffectDescription
from gupb.model.characters import ChampionKnowledge


class FindMenhirStrategy(BaseStrategy):
    INITIAL_MOVES = [
        characters.Action.TURN_LEFT for _ in range(4)
    ]

    menhir_found = False

    def apply(self) -> characters.Action:
        q = self.INITIAL_MOVES

        if not self.menhir_found and q:
            return q.pop(0)

        return characters.Action.DO_NOTHING


class MenhirEstimator:

    def __init__(self, map_knowledge: MapKnowledge):
        self.map_knowledge = map_knowledge
        self.mist_coordinates = []
        self.clear_coordinates = []

    def update_knowledge(self, champion_knowledge: ChampionKnowledge):
        if self.map_knowledge.mnist_moved:
            self.mist_coordinates = []
            self.clear_coordinates = []
        else:
            for coord, tile in champion_knowledge.visible_tiles.items():
                if EffectDescription(type='mist') in tile.effects:
                    self.mist_coordinates.append(coord)
                else:
                    self.clear_coordinates.append(coord)

    def estimate_menhir(self, champion_knowledge: ChampionKnowledge) -> tuple[np.ndarray, int] | tuple[None, None]:
        self.update_knowledge(champion_knowledge)

        if not self.mist_coordinates:
            return None, None

        result = constraint_solver(self.clear_coordinates, self.mist_coordinates, self.map_knowledge.mist_radius, np.zeros((2,)))

        return result, len(self.mist_coordinates)


def constraint_solver(inner_points: list, outer_points: list, radius: int, starting_point: np.ndarray) -> np.ndarray | None:
    constraints = []

    for x, y in inner_points:
        constraints.append({'type': 'ineq', 'fun': lambda p, x=x, y=y: radius ** 2 - (x - p[0]) ** 2 - (y - p[1]) ** 2})

    for x, y in outer_points:
        constraints.append({'type': 'ineq', 'fun': lambda p, x=x, y=y: (x - p[0]) ** 2 + (y - p[1]) ** 2 - radius ** 2})

    constraints.append({'type': 'ineq', 'fun': lambda p: p[0]})
    constraints.append({'type': 'ineq', 'fun': lambda p: p[1]})

    result = minimize(
        lambda *args: 0, x0=starting_point,
        constraints=constraints,
        method='SLSQP'
    )
    return result.x if result.success else None

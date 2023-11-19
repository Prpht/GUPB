import random

import numpy as np

from gupb.model.coordinates import Coords
from gupb.controller.batman.knowledge.knowledge import Knowledge
from gupb.controller.batman.heuristic.navigation import Navigation


class Passthrough:
    def __init__(
        self,
        knowledge: Knowledge,
        navigation: Navigation,
        samples: int = 1000,
        seed: int = 0,
    ):
        self._knowledge = knowledge
        self.arena_size = knowledge.arena.arena_size
        self.navigation = navigation
        self._samples = samples
        self._rng = random.Random(seed)
        self._passthrough = self._calculate_passthrough()

    def __getitem__(self, item: Coords):
        return self._passthrough[item.y, item.x]

    def _calculate_passthrough(self) -> np.ndarray:
        base_grid = self.navigation.base_grid()
        passthrough = np.where(base_grid == 0, 100 * self._samples, 0)

        passable_ys, passable_xs = np.where(base_grid == 1)
        passable_tiles = [Coords(x, y) for x, y in zip(passable_xs, passable_ys)]

        from_tiles = self._rng.choices(passable_tiles, k=self._samples)
        to_tiles = self._rng.choices(passable_tiles, k=self._samples)

        for from_tile, to_tile in zip(from_tiles, to_tiles):
            path = self.navigation.find_path(from_tile, to_tile)
            for tile in path:
                passthrough[tile.y, tile.x] += 1

        passthrough = passthrough / self._samples
        return passthrough

from abc import ABC, abstractmethod

import numpy as np

from gupb.controller.forrest_gump.utils import CharacterInfo, init_grid
from gupb.model import arenas, characters, coordinates, tiles


class Strategy(ABC):
    def __init__(self, arena_description: arenas.ArenaDescription) -> None:
        self.arena_description = arena_description
        self.arena = arenas.Arena.load(arena_description.name)
        self.matrix = init_grid(arena_description)
        self.fields = np.argwhere(self.matrix.T == 1).tolist()

    def __eq__(self, other: object) -> bool:
        return self.__class__.__name__ == other.__class__.__name__

    def __hash__(self) -> int:
        return hash(self.__class__.__name__)

    @abstractmethod
    def enter(self) -> None:
        pass

    @abstractmethod
    def should_enter(self, coords: coordinates.Coords, tile: tiles.TileDescription, character_info: CharacterInfo) -> bool:
        pass

    @abstractmethod
    def should_leave(self, character_info: CharacterInfo) -> bool:
        pass

    @abstractmethod
    def left(self) -> None:
        pass

    @abstractmethod
    def next_action(self, character_info: CharacterInfo) -> characters.Action:
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        pass

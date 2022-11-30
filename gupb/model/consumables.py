from __future__ import annotations
from abc import ABC, abstractmethod
from typing import NamedTuple

from gupb.model import characters

POTION_RESTORED_HP: int = 5


class ConsumableDescription(NamedTuple):
    name: str


class Consumable(ABC):
    def description(self) -> ConsumableDescription:
        return ConsumableDescription(self.__class__.__name__.lower())

    @classmethod
    @abstractmethod
    def apply_to(cls, champion: characters.Champion):
        raise NotImplementedError


class Potion(Consumable):
    @classmethod
    def apply_to(cls, champion: characters.Champion):
        champion.health += POTION_RESTORED_HP

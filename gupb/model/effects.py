from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
import logging
from enum import auto, StrEnum
import functools
from typing import NamedTuple

from gupb.logger import core as logger_core
from gupb.model import characters

verbose_logger = logging.getLogger('verbose')

CUT_DAMAGE: int = 2
MIST_DAMAGE: int = 1


class EffectDescription(NamedTuple):
    type: str


class EffectLifetime(StrEnum):
    INSTANT = auto()
    ETERNAL = auto()


@functools.total_ordering
class Effect(ABC):
    order: int = 0

    def description(self) -> EffectDescription:
        return EffectDescription(self.__class__.__name__.lower())

    def __lt__(self, other):
        return self.order < other.order

    @staticmethod
    @abstractmethod
    def instant(champion: characters.Champion) -> None:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def stay(champion: characters.Champion) -> None:
        raise NotImplementedError

    @staticmethod
    @abstractmethod
    def lifetime() -> EffectLifetime:
        raise NotImplementedError


class Mist(Effect):
    @staticmethod
    def instant(champion: characters.Champion) -> None:
        pass

    @staticmethod
    def stay(champion: characters.Champion) -> None:
        verbose_logger.debug(f"Champion {champion.controller.name} was damaged by deadly mist.")
        ChampionDamagedByMistReport(champion.controller.name, MIST_DAMAGE).log(logging.DEBUG)
        champion.damage(MIST_DAMAGE)

    @staticmethod
    def lifetime() -> EffectLifetime:
        return EffectLifetime.ETERNAL


class WeaponCut(Effect):
    def __init__(self, damage: int = CUT_DAMAGE):
        self.damage: int = damage

    def instant(self, champion: characters.Champion) -> None:
        verbose_logger.debug(f"Champion {champion.controller.name} was damaged by weapon cut.")
        ChampionDamagedByWeaponCutReport(champion.controller.name, self.damage).log(logging.DEBUG)
        champion.damage(self.damage)

    @staticmethod
    def stay(champion: characters.Champion) -> None:
        pass

    @staticmethod
    def lifetime() -> EffectLifetime:
        return EffectLifetime.INSTANT


@dataclass(frozen=True)
class ChampionDamagedByMistReport(logger_core.LoggingMixin):
    controller_name: str
    damage: int


@dataclass(frozen=True)
class ChampionDamagedByWeaponCutReport(logger_core.LoggingMixin):
    controller_name: str
    damage: int


EFFECTS_ORDER = {
    Mist,
    WeaponCut,
}
for i, effect in enumerate(EFFECTS_ORDER):
    effect.order = i

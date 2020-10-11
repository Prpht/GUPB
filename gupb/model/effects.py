from __future__ import annotations
from abc import ABC, abstractmethod
import logging
from enum import auto, Enum
import functools
from typing import NamedTuple

from gupb.logger.core import log
from gupb.logger.primitives import LogSeverity, ChampionDamagedByMistReport, \
    ChampionDamagedByWeaponCutReport
from gupb.model import characters

CUT_DAMAGE: int = 1
MIST_DAMAGE: int = 1


class EffectDescription(NamedTuple):
    type: str


class EffectLifetime(Enum):
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
        logging.debug(f"Champion {champion.controller.name} was damaged by deadly mist.")
        log(
            severity=LogSeverity.DEBUG,
            value=ChampionDamagedByMistReport(champion.controller.name, MIST_DAMAGE)
        )
        champion.damage(MIST_DAMAGE)

    @staticmethod
    def lifetime() -> EffectLifetime:
        return EffectLifetime.ETERNAL


class WeaponCut(Effect):
    @staticmethod
    def instant(champion: characters.Champion) -> None:
        logging.debug(f"Champion {champion.controller.name} was damaged by weapon cut.")
        log(
            severity=LogSeverity.DEBUG,
            value=ChampionDamagedByWeaponCutReport(champion.controller.name, CUT_DAMAGE)
        )
        champion.damage(CUT_DAMAGE)

    @staticmethod
    def stay(champion: characters.Champion) -> None:
        pass

    @staticmethod
    def lifetime() -> EffectLifetime:
        return EffectLifetime.INSTANT


EFFECTS_ORDER = {
    Mist,
    WeaponCut,
}
for i, effect in enumerate(EFFECTS_ORDER):
    effect.order = i

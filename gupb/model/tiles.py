from __future__ import annotations
from abc import ABC, abstractmethod
import logging
from typing import NamedTuple, Optional

import sortedcontainers

from gupb.model import effects
from gupb.model import characters
from gupb.model import weapons


class TileDescription(NamedTuple):
    type: str
    loot: Optional[weapons.WeaponDescription]
    character: Optional[characters.ChampionDescription]
    effects: list[effects.EffectDescription]


class Tile(ABC):
    def __init__(self):
        self.loot: Optional[weapons.Weapon] = None
        self.character: Optional[characters.Champion] = None
        self.effects: sortedcontainers.SortedList[effects.Effect] = sortedcontainers.SortedList()

    def description(self) -> TileDescription:
        return TileDescription(
            self.__class__.__name__.lower(),
            self.loot.description() if self.loot else None,
            self.character.description() if self.character else None,
            [effect.description() for effect in self.effects]
        )

    @property
    def passable(self) -> bool:
        return self.terrain_passable() and not self.character

    @staticmethod
    @abstractmethod
    def terrain_passable() -> bool:
        raise NotImplementedError

    @property
    def transparent(self) -> bool:
        return self.terrain_transparent() and not self.character

    @staticmethod
    @abstractmethod
    def terrain_transparent() -> bool:
        raise NotImplementedError

    @property
    def empty(self) -> bool:
        return self.passable and not self.loot and not self.character

    def enter(self, champion: characters.Champion) -> None:
        self.character = champion
        if self.loot:
            champion.weapon, self.loot = self.loot, champion.weapon
            logging.debug(f"Champion {champion.controller.name} picked up a {champion.weapon.description().name}.")

    # noinspection PyUnusedLocal
    def leave(self, champion: characters.Champion) -> None:
        self.character = None

    def stay(self) -> None:
        self._activate_effects('stay')

    def instant(self) -> None:
        self._activate_effects('instant')
        self.effects = sortedcontainers.SortedList(
            effect for effect in self.effects if effect.lifetime() != effects.EffectLifetime.INSTANT
        )

    def _activate_effects(self, activation: str) -> None:
        if self.character:
            if self.effects:
                for effect in self.effects:
                    getattr(effect, activation)(self.character)


class Land(Tile):
    @staticmethod
    def terrain_passable() -> bool:
        return True

    @staticmethod
    def terrain_transparent() -> bool:
        return True


class Sea(Tile):
    @staticmethod
    def terrain_passable() -> bool:
        return False

    @staticmethod
    def terrain_transparent() -> bool:
        return True


class Wall(Tile):
    @staticmethod
    def terrain_passable() -> bool:
        return False

    @staticmethod
    def terrain_transparent() -> bool:
        return False


class Menhir(Tile):
    @staticmethod
    def terrain_passable() -> bool:
        return False

    @staticmethod
    def terrain_transparent() -> bool:
        return False

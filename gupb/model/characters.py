from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from functools import partial
import logging
import random
from typing import NamedTuple, Optional, Dict

from gupb import controller
from gupb.logger import core as logger_core
from gupb.model import arenas
from gupb.model import coordinates
from gupb.model import tiles
from gupb.model import weapons

verbose_logger = logging.getLogger('verbose')

CHAMPION_STARTING_HP: int = 5


class ChampionKnowledge(NamedTuple):
    position: coordinates.Coords
    visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]


class ChampionDescription(NamedTuple):
    controller_name: str
    health: int
    weapon: weapons.WeaponDescription
    facing: Facing


class Tabard(Enum):
    BLUE = 'Blue'
    BROWN = 'Brown'
    GREY = 'Grey'
    RED = 'Red'
    VIOLET = 'Violet'
    WHITE = 'White'
    YELLOW = 'Yellow'


class Champion:
    def __init__(self, starting_position: coordinates.Coords, arena: arenas.Arena) -> None:
        self.facing: Facing = Facing.random()
        self.weapon: weapons.Weapon = weapons.Knife()
        self.health: int = CHAMPION_STARTING_HP
        self.position: coordinates.Coords = starting_position
        self.arena: arenas.Arena = arena
        self.controller: Optional[controller.Controller] = None
        self.tabard: Optional[Tabard] = None

    def assign_controller(self, assigned_controller: controller.Controller) -> None:
        self.controller = assigned_controller
        self.tabard = self.controller.preferred_tabard

    def description(self) -> ChampionDescription:
        return ChampionDescription(self.controller.name, self.health, self.weapon.description(), self.facing)

    def act(self) -> None:
        if self.alive:
            action = self.pick_action()
            verbose_logger.debug(f"Champion {self.controller.name} picked action {action}.")
            ChampionPickedActionReport(self.controller.name, action.name).log(logging.DEBUG)
            action(self)
            self.arena.stay(self)

    # noinspection PyBroadException
    def pick_action(self) -> Action:
        if self.controller:
            visible_tiles = self.arena.visible_tiles(self)
            knowledge = ChampionKnowledge(self.position, visible_tiles)
            try:
                return self.controller.decide(knowledge)
            except Exception as e:
                verbose_logger.warning(f"Controller {self.controller.name} throw an unexpected exception: {repr(e)}.")
                ControllerExceptionReport(self.controller.name, repr(e)).log(logging.WARN)
                return Action.DO_NOTHING
        else:
            return Action.DO_NOTHING

    def turn_left(self) -> None:
        self.facing = self.facing.turn_left()
        verbose_logger.debug(f"Champion {self.controller.name} is now facing {self.facing}.")
        ChampionFacingReport(self.controller.name, self.facing.value).log(logging.DEBUG)

    def turn_right(self) -> None:
        self.facing = self.facing.turn_right()
        verbose_logger.debug(f"Champion {self.controller.name} is now facing {self.facing}.")
        ChampionFacingReport(self.controller.name, self.facing.value).log(logging.DEBUG)

    def step_forward(self) -> None:
        self.arena.step_forward(self)

    def attack(self) -> None:
        self.weapon.cut(self.arena, self.position, self.facing)
        verbose_logger.debug(f"Champion {self.controller.name} attacked with its {self.weapon.description().name}.")
        ChampionAttackReport(self.controller.name, self.weapon.description().name).log(logging.DEBUG)

    def do_nothing(self) -> None:
        pass

    def damage(self, wounds: int) -> None:
        self.health -= wounds
        self.health = self.health if self.health > 0 else 0
        verbose_logger.debug(f"Champion {self.controller.name} took {wounds} wounds, it has now {self.health} hp left.")
        ChampionWoundsReport(self.controller.name, wounds, self.health).log(logging.DEBUG)
        if not self.alive:
            self.die()

    def die(self) -> None:
        self.arena.terrain[self.position].character = None
        self.arena.terrain[self.position].loot = self.weapon
        verbose_logger.debug(f"Champion {self.controller.name} died.")
        ChampionDeathReport(self.controller.name).log(logging.DEBUG)

        die_callable = getattr(self.controller, "die", None)
        if die_callable:
            die_callable()

    @property
    def alive(self) -> bool:
        return self.health > 0


class Facing(Enum):
    UP = coordinates.Coords(0, -1)
    DOWN = coordinates.Coords(0, 1)
    LEFT = coordinates.Coords(-1, 0)
    RIGHT = coordinates.Coords(1, 0)

    @staticmethod
    def random() -> Facing:
        return random.choice([Facing.UP, Facing.DOWN, Facing.LEFT, Facing.RIGHT])

    def turn_left(self) -> Facing:
        if self == Facing.UP:
            return Facing.LEFT
        elif self == Facing.LEFT:
            return Facing.DOWN
        elif self == Facing.DOWN:
            return Facing.RIGHT
        elif self == Facing.RIGHT:
            return Facing.UP

    def turn_right(self) -> Facing:
        if self == Facing.UP:
            return Facing.RIGHT
        elif self == Facing.RIGHT:
            return Facing.DOWN
        elif self == Facing.DOWN:
            return Facing.LEFT
        elif self == Facing.LEFT:
            return Facing.UP


class Action(Enum):
    TURN_LEFT = partial(Champion.turn_left)
    TURN_RIGHT = partial(Champion.turn_right)
    STEP_FORWARD = partial(Champion.step_forward)
    ATTACK = partial(Champion.attack)
    DO_NOTHING = partial(Champion.do_nothing)

    def __call__(self, *args):
        self.value(*args)


@dataclass(frozen=True)
class ChampionPickedActionReport(logger_core.LoggingMixin):
    controller_name: str
    action_name: str


@dataclass(frozen=True)
class ChampionFacingReport(logger_core.LoggingMixin):
    controller_name: str
    facing_value: coordinates.Coords


@dataclass(frozen=True)
class ChampionAttackReport(logger_core.LoggingMixin):
    controller_name: str
    weapon_name: str


@dataclass(frozen=True)
class ChampionWoundsReport(logger_core.LoggingMixin):
    controller_name: str
    wounds: int
    rest_health: int


@dataclass(frozen=True)
class ChampionDeathReport(logger_core.LoggingMixin):
    controller_name: str


@dataclass(frozen=True)
class ControllerExceptionReport(logger_core.LoggingMixin):
    controller_name: str
    exception: str

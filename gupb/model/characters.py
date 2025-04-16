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
from gupb.model import consumables
from gupb.model import tiles
from gupb.model import weapons

verbose_logger = logging.getLogger('verbose')

CHAMPION_STARTING_HP: int = 8
PENALISED_IDLE_TIME = 16
IDLE_DAMAGE_PENALTY = 1

class ChampionKnowledge(NamedTuple):
    position: coordinates.Coords
    no_of_champions_alive: int
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
    GREEN = 'Green'
    LIME = 'Lime'
    ORANGE = 'Orange'
    PINK = 'Pink'
    RED = 'Red'
    STRIPPED = 'Stripped'
    TURQUOISE = 'Turquoise'
    VIOLET = 'Violet'
    WHITE = 'White'
    YELLOW = 'Yellow'
    GAREK = "G.A.R.E.K."
    REINFORCEDROGUE = 'ReinforcedRogue'
    NORGUL = 'Norgul'
    KIRBY = 'Kirby'
    KIMDZONGNEAT = 'KimDzongNeat'
    CAMPER = 'Camper'
    

class Champion:
    def __init__(self, starting_position: coordinates.Coords, arena: arenas.Arena) -> None:
        self.facing: Facing = Facing.random()
        self.weapon: weapons.Weapon = weapons.Knife()
        self.health: int = CHAMPION_STARTING_HP
        self.position: coordinates.Coords = starting_position
        self.arena: arenas.Arena = arena
        self.controller: Optional[controller.Controller] = None
        self.tabard: Optional[Tabard] = None
        self.previous_facing: Facing = self.facing
        self.previous_position: coordinates.Coords = self.position
        self.time_idle: int = 0

    def assign_controller(self, assigned_controller: controller.Controller) -> None:
        self.controller = assigned_controller
        self.tabard = self.controller.preferred_tabard

    def description(self) -> ChampionDescription:
        return ChampionDescription(self.controller.name, self.health, self.weapon.description(), self.facing)

    def verbose_name(self) -> str:
        return self.controller.name if self.controller else "NULL_CONTROLLER"

    def act(self) -> None:
        if self.alive:
            verbose_logger.debug(f"Champion {self.verbose_name()} starts acting.")
            self.store_previous_state()
            action = self.pick_action()
            verbose_logger.debug(f"Champion {self.verbose_name()} picked action {action}.")
            ChampionPickedActionReport(self.verbose_name(), action.name).log(logging.DEBUG)
            action(self)
            self.arena.stay(self)
            self.assess_idle_penalty()

    def store_previous_state(self) -> None:
        self.previous_position = self.position
        self.previous_facing = self.facing

    def assess_idle_penalty(self) -> None:
        if self.position == self.previous_position and self.previous_facing == self.facing:
            self.time_idle += 1
        else:
            self.time_idle = 0
        if self.time_idle >= PENALISED_IDLE_TIME:
            verbose_logger.debug(f"Champion {self.verbose_name()} penalised for idle time.")
            IdlePenaltyReport(self.verbose_name()).log(logging.DEBUG)
            self.damage(IDLE_DAMAGE_PENALTY)

    # noinspection PyBroadException
    def pick_action(self) -> Action:
        if self.controller:
            visible_tiles = self.arena.visible_tiles(self)
            knowledge = ChampionKnowledge(self.position, self.arena.no_of_champions_alive, visible_tiles)
            try:
                action = self.controller.decide(knowledge)
                if action is None:
                    verbose_logger.warning(f"Controller {self.verbose_name()} returned a non-action.")
                    controller.ControllerExceptionReport(self.verbose_name(), "a non-action returned").log(logging.WARN)
                    return Action.DO_NOTHING
                return action
            except Exception as e:
                verbose_logger.warning(f"Controller {self.verbose_name()} throw an unexpected exception: {repr(e)}. {e.__traceback__}")
                controller.ControllerExceptionReport(self.verbose_name(), repr(e)).log(logging.WARN)
                return Action.DO_NOTHING
        else:
            verbose_logger.warning(f"Controller {self.verbose_name()} was non-existent.")
            controller.ControllerExceptionReport(self.verbose_name(), "controller non-existent").log(logging.WARN)
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
        self.arena.step(self, arenas.StepDirection.FORWARD)

    def step_backward(self) -> None:
        self.arena.step(self, arenas.StepDirection.BACKWARD)

    def step_left(self) -> None:
        self.arena.step(self, arenas.StepDirection.LEFT)

    def step_right(self) -> None:
        self.arena.step(self, arenas.StepDirection.RIGHT)

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
        self.arena.terrain[self.position].consumable = consumables.Potion()
        self.arena.terrain[self.position].loot = self.weapon if self.weapon.droppable() else None
        verbose_logger.debug(f"Champion {self.controller.name} died.")
        ChampionDeathReport(self.controller.name).log(logging.DEBUG)

        die_callable = getattr(self.controller, "die", None)
        if die_callable and callable(die_callable):
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

    def opposite(self) -> Facing:
        if self == Facing.UP:
            return Facing.DOWN
        elif self == Facing.RIGHT:
            return Facing.LEFT
        elif self == Facing.DOWN:
            return Facing.UP
        elif self == Facing.LEFT:
            return Facing.RIGHT


class Action(Enum):
    TURN_LEFT = partial(Champion.turn_left)
    TURN_RIGHT = partial(Champion.turn_right)
    STEP_FORWARD = partial(Champion.step_forward)
    STEP_BACKWARD = partial(Champion.step_backward)
    STEP_LEFT = partial(Champion.step_left)
    STEP_RIGHT = partial(Champion.step_right)
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
class IdlePenaltyReport(logger_core.LoggingMixin):
    controller_name: str

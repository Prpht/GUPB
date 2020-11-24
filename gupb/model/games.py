from __future__ import annotations
from dataclasses import dataclass
import logging
import random
from typing import Iterator, NamedTuple, Optional

# noinspection PyPackageRequirements
import statemachine

from gupb import controller
from gupb.logger import core as logger_core
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

verbose_logger = logging.getLogger('verbose')

MIST_TTH: int = 5

ChampionDeath = NamedTuple('ChampionDeath', [('champion', characters.Champion), ('episode', int)])


class Game(statemachine.StateMachine):
    actions_done = statemachine.State('ActionsDone', value=9, initial=True)
    instants_triggered = statemachine.State('InstantsTriggered', value=1)

    cycle = actions_done.to(instants_triggered) | instants_triggered.to(actions_done)

    def __init__(
            self,
            arena_name: str,
            to_spawn: list[controller.Controller],
            menhir_position: Optional[coordinates.Coords] = None,
            initial_champion_positions: Optional[list[coordinates.Coords]] = None,
    ) -> None:
        self.arena: arenas.Arena = arenas.Arena.load(arena_name)
        self.arena.spawn_menhir(menhir_position)
        self._prepare_controllers(to_spawn)
        self.initial_champion_positions: Optional[list[coordinates.Coords]] = initial_champion_positions
        self.champions: list[characters.Champion] = self._spawn_champions(to_spawn)
        self.action_queue: list[characters.Champion] = []
        self.episode: int = 0
        self.deaths: list[ChampionDeath] = []
        self.finished = False
        super(statemachine.StateMachine, self).__init__()

    def on_enter_actions_done(self) -> None:
        if not self.action_queue:
            self._environment_action()
        else:
            self._champion_action()

    def on_enter_instants_triggered(self):
        self.arena.trigger_instants()

    def score(self) -> dict[str, int]:
        if not self.finished:
            raise RuntimeError("Attempted to score an unfinished game!")
        return {death.champion.controller.name: score for death, score in zip(self.deaths, self._fibonacci())}

    def _prepare_controllers(self, to_spawn: list[controller.Controller]):
        for controller_to_spawn in to_spawn:
            controller_to_spawn.reset(self.arena.description())

    def _spawn_champions(
            self,
            to_spawn: list[controller.Controller],
    ) -> list[characters.Champion]:
        champions = []
        if self.initial_champion_positions is None:
            self.initial_champion_positions = random.sample(self.arena.empty_coords(), len(to_spawn))
        if len(to_spawn) != len(self.initial_champion_positions):
            raise RuntimeError("Unable to spawn champions: not enough positions!")  # TODO: remove if works
        for controller_to_spawn, coords in zip(to_spawn, self.initial_champion_positions):
            champion = characters.Champion(coords, self.arena)
            self.arena.terrain[coords].character = champion
            champion.assign_controller(controller_to_spawn)
            champions.append(champion)
            verbose_logger.debug(f"{champion.tabard.value} champion for {controller_to_spawn.name}"
                                 f" spawned at {coords} facing {champion.facing}.")
            ChampionSpawnedReport(controller_to_spawn.name, coords, champion.facing.value).log(logging.DEBUG)
        return champions

    def _environment_action(self) -> None:
        self._clean_dead_champions()
        self.action_queue = self.champions.copy()
        self.episode += 1
        verbose_logger.debug(f"Starting episode {self.episode}.")
        EpisodeStartReport(self.episode).log(logging.DEBUG)
        if self.episode % MIST_TTH == 0:
            self.arena.increase_mist()

    def _clean_dead_champions(self):
        alive = []
        for champion in self.champions:
            if champion.alive:
                alive.append(champion)
            else:
                death = ChampionDeath(champion, self.episode)
                self.deaths.append(death)
        self.champions = alive
        if len(self.champions) == 1:
            verbose_logger.debug(f"Champion {self.champions[0].controller.name} was the last one standing.")
            LastManStandingReport(self.champions[0].controller.name).log(logging.DEBUG)
            champion = self.champions.pop()
            death = ChampionDeath(champion, self.episode)
            self.deaths.append(death)

            win_callable = getattr(champion.controller, "win", None)
            if win_callable:
                win_callable()

        if not self.champions:
            self.finished = True

    def _champion_action(self) -> None:
        champion = self.action_queue.pop()
        champion.act()

    @staticmethod
    def _fibonacci() -> Iterator[int]:
        a = 1
        b = 2
        while True:
            yield a
            a, b = b, a + b


@dataclass(frozen=True)
class ChampionSpawnedReport(logger_core.LoggingMixin):
    controller_name: str
    coords: coordinates.Coords
    facing_value: coordinates.Coords


@dataclass(frozen=True)
class EpisodeStartReport(logger_core.LoggingMixin):
    episode_number: int


@dataclass(frozen=True)
class LastManStandingReport(logger_core.LoggingMixin):
    controller_name: str

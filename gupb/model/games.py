from __future__ import annotations
import logging
import random
from typing import Iterator, NamedTuple

# noinspection PyPackageRequirements
import statemachine

from gupb import controller
from gupb.logger.core import log
from gupb.logger.primitives import LogSeverity, ChampionSpawnedReport, \
    EpisodeStartReport, LastManStandingReport
from gupb.model import arenas
from gupb.model import characters

MIST_TTH: int = 5

ChampionDeath = NamedTuple('ChampionDeath', [('champion', characters.Champion), ('episode', int)])


class Game(statemachine.StateMachine):
    actions_done = statemachine.State('ActionsDone', value=9, initial=True)
    instants_triggered = statemachine.State('InstantsTriggered', value=1)

    cycle = actions_done.to(instants_triggered) | instants_triggered.to(actions_done)

    def __init__(self, arena_name: str, to_spawn: list[controller.Controller]) -> None:
        self.arena: arenas.Arena = arenas.Arena.load(arena_name)
        self.arena.spawn_menhir()
        self._prepare_controllers(to_spawn)
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
        random.shuffle(to_spawn)
        for controller_to_spawn in to_spawn:
            controller_to_spawn.reset(self.arena.description())

    def _spawn_champions(self, to_spawn: list[controller.Controller]) -> list[characters.Champion]:
        champions = []
        champion_positions = random.sample(self.arena.empty_coords(), len(to_spawn))
        for controller_to_spawn, coords in zip(to_spawn, champion_positions):
            champion = characters.Champion(coords, self.arena)
            self.arena.terrain[coords].character = champion
            champion.controller = controller_to_spawn
            champions.append(champion)
            logging.debug(f"Champion for {controller_to_spawn.name} spawned at {coords} facing {champion.facing}.")
            log(
                severity=LogSeverity.DEBUG,
                value=ChampionSpawnedReport(controller_to_spawn.name, coords, champion.facing.value)
            )
        return champions

    def _environment_action(self) -> None:
        self._clean_dead_champions()
        self.action_queue = self.champions.copy()
        self.episode += 1
        logging.debug(f"Starting episode {self.episode}.")
        log(severity=LogSeverity.DEBUG, value=EpisodeStartReport(self.episode))
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
            logging.debug(f"Champion {self.champions[0].controller.name} was the last one standing.")
            log(
                severity=LogSeverity.DEBUG,
                value=LastManStandingReport(self.champions[0].controller.name)
            )
            champion = self.champions.pop()
            death = ChampionDeath(champion, self.episode)
            self.deaths.append(death)
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

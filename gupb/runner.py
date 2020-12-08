from __future__ import annotations
import collections
from dataclasses import dataclass
import logging
import random
from typing import Any, List, Optional

from tqdm import trange

from gupb import controller
from gupb.controller import keyboard
from gupb.model.profiling import PROFILE_RESULTS, print_stats
from gupb.logger import core as logger_core
from gupb.model import coordinates
from gupb.model import games
from gupb.view import render

verbose_logger = logging.getLogger('verbose')


class Runner:
    def __init__(self, config: dict[str, Any]) -> None:
        self.arenas: list[str] = config['arenas']
        self.controllers: list[controller.Controller] = config['controllers']
        self.keyboard_controller: Optional[keyboard.KeyboardController] = next(
            (c for c in self.controllers if isinstance(c, keyboard.KeyboardController)), None
        )
        self.show_sight: Optional[controller.Controller] = config['show_sight'] if 'show_sight' in config else None
        self.renderer: Optional[render.Renderer] = render.Renderer() if config['visualise'] else None
        self.runs_no: int = config['runs_no']
        self.start_balancing: bool = config['start_balancing']
        self.scores: dict[str, int] = collections.defaultdict(int)
        self.profiling_metrics = config['profiling_metrics'] if 'profiling_metrics' in config else None
        self._last_arena: Optional[str] = None
        self._last_menhir_position: Optional[coordinates.Coords] = None
        self._last_initial_positions: Optional[list[coordinates.Coords]] = None

    def run(self) -> None:
        for i in trange(self.runs_no, desc="Playing games"):
            verbose_logger.info(f"Starting game number {i + 1}.")
            GameStartReport(i + 1).log(logging.INFO)
            self.run_game(i)

    def run_game(self, game_no: int) -> None:
        arena = random.choice(self.arenas)
        verbose_logger.debug(f"Randomly picked arena: {arena}.")
        RandomArenaPickReport(arena).log(logging.DEBUG)
        if not self.start_balancing or game_no % len(self.controllers) == 0:
            random.shuffle(self.controllers)
            game = games.Game(arena, self.controllers)
        else:
            self.controllers = self.controllers[1:] + [self.controllers[0]]
            game = games.Game(self._last_arena, self.controllers, self._last_menhir_position, self._last_initial_positions)
        self._last_arena = game.arena.name
        self._last_menhir_position = game.arena.menhir_position
        self._last_initial_positions = game.initial_champion_positions
        show_sight = next((c for c in game.champions if c.controller == self.show_sight), None)
        if self.renderer:
            self.renderer.run(game, show_sight, self.keyboard_controller)
        else:
            self.run_in_memory(game)
        for name, score in game.score().items():
            logging.info(f"Controller {name} scored {score} points.")
            ControllerScoreReport(name, score).log(logging.DEBUG)
            self.scores[name] += score

    def print_scores(self) -> None:
        verbose_logger.info(f"Final scores.")
        scores_to_log = []
        for i, (name, score) in enumerate(sorted(self.scores.items(), key=lambda x: x[1], reverse=True)):
            score_line = f"{i + 1}.   {name}: {score}."
            verbose_logger.info(score_line)
            scores_to_log.append(ControllerScoreReport(name, score))
            print(score_line)
        FinalScoresReport(scores_to_log).log(logging.INFO)

        if self.profiling_metrics:
            for func in PROFILE_RESULTS.keys():
                print_stats(func, **{m: True for m in self.profiling_metrics})

    @staticmethod
    def run_in_memory(game: games.Game) -> None:
        while not game.finished:
            game.cycle()


@dataclass(frozen=True)
class GameStartReport(logger_core.LoggingMixin):
    game_number: int


@dataclass(frozen=True)
class RandomArenaPickReport(logger_core.LoggingMixin):
    arena_name: str


@dataclass(frozen=True)
class ControllerScoreReport(logger_core.LoggingMixin):
    controller_name: str
    score: int


@dataclass(frozen=True)
class FinalScoresReport(logger_core.LoggingMixin):
    scores: List[ControllerScoreReport]

from __future__ import annotations
import collections
import logging
import random
from typing import Any, Optional

from tqdm import trange

from gupb import controller
from gupb.controller import keyboard
from gupb.model import games
from gupb.view import render


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
        self.scores = collections.defaultdict(int)

    def run(self):
        for i in trange(self.runs_no, desc="Playing games"):
            logging.info(f"Starting game number {i + 1}.")
            self.run_game()

    def run_game(self):
        arena = random.choice(self.arenas)
        logging.debug(f"Randomly picked arena: {arena}.")
        game = games.Game(arena, self.controllers)
        show_sight = next((c for c in game.champions if c.controller == self.show_sight), None)
        if self.renderer:
            self.renderer.run(game, show_sight, self.keyboard_controller)
        else:
            self.run_in_memory(game)
        for name, score in game.score().items():
            logging.info(f"Controller {name} scored {score} points.")
            self.scores[name] += score

    def print_scores(self):
        logging.info(f"Final scores.")
        for i, (name, score) in enumerate(sorted(self.scores.items(), key=lambda x: x[1], reverse=True)):
            score_line = f"{i + 1}.   {name}: {score}."
            logging.info(score_line)
            print(score_line)

    @staticmethod
    def run_in_memory(game: games.Game) -> None:
        while not game.finished:
            game.cycle()

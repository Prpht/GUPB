from typing import Optional

from gupb import controller
from gupb.model import arenas

from gupb.controller.batman.heuristic.events import EventDetector
from gupb.controller.batman.heuristic.navigation import Navigation
from gupb.controller.batman.heuristic.passthrough import Passthrough
from gupb.controller.batman.heuristic.strategies import StrategiesFactory

from gupb.controller.batman.knowledge.knowledge import Knowledge

from gupb.model.characters import Action, ChampionKnowledge, Tabard


class BatmanHeuristicsController(controller.Controller):
    def __init__(self, name: str) -> None:
        super().__init__()

        self._name = name
        self._episode = 0
        self._game = 0

        self._event_detector = EventDetector()

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        assert (
            self._knowledge is not None and self._navigation is not None
        ), "Reset was not called before first decide() call"

        self._episode += 1
        self._knowledge.update(knowledge, self._episode)

        events = self._event_detector.detect(self._knowledge)

        action = None
        changed_strategies = 0
        while action is None and changed_strategies < 10:
            action, strategy = self._current_strategy.decide(
                self._knowledge, events, self._navigation
            )
            self._current_strategy = self._strategies.get(strategy)
            changed_strategies += 1

        # this should never happen (but it does happen xd)
        if action is None:
            # print('WARNING: endless loop in strategies changing')
            action = Action.DO_NOTHING

        return action

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._episode = 0
        self._game += 1
        self._knowledge = Knowledge(arena_description)
        self._navigation = Navigation(self._knowledge)
        self._passthrough = Passthrough(self._knowledge, self._navigation, samples=1000)
        self._strategies = StrategiesFactory(self._passthrough)
        self._current_strategy = self._strategies.get("hiding")

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.STRIPPED  # TODO change to batman

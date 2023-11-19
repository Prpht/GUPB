from typing import Optional
import time

from gupb import controller
from gupb.model import arenas
from gupb.controller.batman.navigation import Navigation
from gupb.controller.batman.passthrough import Passthrough
from gupb.controller.batman.environment.knowledge import Knowledge
from gupb.controller.batman.strategies import (
    DefendingStrategy,
    FightingStrategy,
    HidingStrategy,
    RotatingStrategy,
    RunningAwayStrategy,
    ScoutingStrategy,
)
from gupb.controller.batman.events import EventDetector
from gupb.model.characters import Action, ChampionKnowledge, Tabard


class BatmanHeuristicsController(controller.Controller):
    def __init__(self, name: str) -> None:
        super().__init__()

        self._name = name
        self._episode = 0
        self._game = 0
        self._knowledge: Optional[Knowledge] = None

        # TODO replace with statemachine?
        self._strategies = {
            "scouting": ScoutingStrategy(),
            "defending": DefendingStrategy(),
        }
        self._current_strategy = self._strategies["scouting"]

        self._event_detector = EventDetector()
        self._navigation = None
        self._passthrough = None

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
            self._current_strategy = self._strategies[strategy]
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
        self._strategies = {
            "defending": DefendingStrategy(),
            "fighting": FightingStrategy(),
            "hiding": HidingStrategy(self._passthrough),
            "rotating": RotatingStrategy(),
            "running_away": RunningAwayStrategy(),
            "scouting": ScoutingStrategy(),
        }
        self._current_strategy = self._strategies["hiding"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.STRIPPED  # TODO change to batman

from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.controller.batman.navigation import Navigation
from gupb.controller.batman.environment.knowledge import Knowledge
from gupb.controller.batman.strategies.scouting import ScoutingStrategy
from gupb.controller.batman.strategies.defending import DefendingStrategy
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

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        assert (
            self._knowledge is not None and self._navigation is not None
        ), "Reset was not called before first decide() call"

        self._episode += 1
        self._knowledge.update(knowledge, self._episode)

        events = self._event_detector.detect(self._knowledge)
        action, strategy = self._current_strategy.decide(self._knowledge, events, self._navigation)
        # print(self._current_strategy, action)
        self._current_strategy = self._strategies[strategy]

        return action

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._episode = 0
        self._game += 1
        self._knowledge = Knowledge(arena_description)
        self._navigation = Navigation(self._knowledge)
        self._strategies = {
            "scouting": ScoutingStrategy(),
            "defending": DefendingStrategy(),
        }
        self._current_strategy = self._strategies["scouting"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.STRIPPED  # TODO change to batman

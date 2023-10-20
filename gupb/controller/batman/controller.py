from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.controller.batman.environment.knowledge import Knowledge
from gupb.controller.batman.environment.observer import Observer, Observable
from gupb.model.characters import Action, ChampionKnowledge, Tabard


class BatmanController(controller.Controller, Observer[Action], Observable[Knowledge]):
    def __init__(self, name: str) -> None:
        super().__init__()
        Observer.__init__(self)
        Observable.__init__(self)
        self._name = name
        self._episode = 0
        self._knowledge: Optional[Knowledge] = None

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        assert (
            self._knowledge is not None
        ), "Reset was not called before first decide() call"

        self._episode += 1
        self._knowledge.update(knowledge, self._episode)

        self.observable_state = self._knowledge
        action = self.wait_for_observed()
        return action

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self._episode = 0
        self._knowledge = Knowledge(arena_description)

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.STRIPPED  # TODO change to batman

from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.controller.batman.rl.trainer import Trainer
from gupb.controller.batman.knowledge.knowledge import Knowledge
from gupb.controller.batman.utils.observer import Observer, Observable
from gupb.model.characters import Action, ChampionKnowledge, Tabard


class BatmanController(controller.Controller, Observer[Action], Observable[Knowledge]):
    def __init__(self, name: str) -> None:
        super().__init__()
        Observer.__init__(self)
        Observable.__init__(self)

        self._name = name
        self._episode = 0
        self._game = 0
        self._knowledge: Optional[Knowledge] = None

        self._trainer = Trainer(self, "./gupb/controller/batman/algo/resources/algo")

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        assert (
            self._knowledge is not None
        ), "Reset was not called before first decide() call"

        self._episode += 1
        self._knowledge.update(knowledge, self._episode)
        self.observable_state = self._knowledge

        action = self.wait_for_observed()

        self._trainer.next_step()

        return action

    def praise(self, score: int) -> None:
        self._trainer.stop(self._knowledge, save=self._game % 10 == 0)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._trainer.start(load=self._game == 0)
        self._episode = 0
        self._game += 1
        self._knowledge = Knowledge(arena_description)
        self.observable_state = self._knowledge

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.STRIPPED  # TODO change to batman

from typing import Optional

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.controller.batman.knowledge import Knowledge


class BatmanController(controller.Controller):
    def __init__(self, name: str) -> None:
        super().__init__()
        self._name = name
        self.episode = 0
        self.knowledge: Optional[Knowledge] = None

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        assert self.knowledge is not None, 'Reset was not called before first decide() call'

        self.episode += 1
        self.knowledge.update(knowledge, self.episode)

        # TODO implement
        return characters.Action.TURN_RIGHT

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.episode = 0
        self.knowledge = Knowledge(arena_description)

    @property
    def name(self) -> str:
        return self._name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.STRIPPED  # TODO change to batman

from __future__ import annotations

from dataclasses import dataclass

from gupb import controller
from gupb.model import arenas, characters

from .brain import SurvivorBrain


@dataclass
class BiwakSpot(controller.Controller):
    first_name: str

    def __post_init__(self) -> None:
        self._brain = SurvivorBrain()

    def __hash__(self) -> int:
        return hash(self.first_name)

    def __eq__(self, other: object) -> bool:
        return isinstance(other, BiwakSpot) and self.first_name == other.first_name

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self._brain.decide(knowledge)

    def praise(self, score: int) -> None:
        self._brain.note_score(score)

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self._brain.reset(game_no, arena_description.name)

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.STRIPPED

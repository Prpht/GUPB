import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.controller.pirat.menhir_finder import MenhirFinder

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class PiratController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.menhir_finder = None

        print("init")

    def __eq__(self, other: object) -> bool:
        print("eq")
        if isinstance(other, PiratController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        menhir_position = self.menhir_finder.update(knowledge)

        return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        print("praise")
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        print("reset")
        self.menhir_finder = MenhirFinder(arena_description)
        print("reset")

    @property
    def name(self) -> str:
        return f"PiratController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PIRAT


POTENTIAL_CONTROLLERS = [
    PiratController("Pirat"),
]

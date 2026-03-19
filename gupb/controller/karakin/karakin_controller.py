import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class KarakinController(controller.Controller):
    def __init__(self, first_name: str = "Karakin"):
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KarakinController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return random.choice([
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.ATTACK,
        ])

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KARAKIN

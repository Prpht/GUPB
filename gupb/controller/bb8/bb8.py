from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.profiling import profile
from gupb.controller.bb8.strategy import (RLStrategy, RandomStrategy, 
                                          BB8Strategy, FindBestWeaponStrategy, 
                                          EscapeToMenhirStrategy)


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BB8Controller(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.strategy = EscapeToMenhirStrategy()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BB8Controller):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def praise(self, score: int) -> None:
        pass

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        return self.strategy.decide(knowledge)

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ORANGE


POTENTIAL_CONTROLLERS = [
    BB8Controller("BB8")
]

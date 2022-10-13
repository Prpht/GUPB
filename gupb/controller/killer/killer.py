import numpy as np

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action


class KillerController(controller.Controller):
    MOVES_MAX_NUM = 3
    DO_NOTHING_PROBABILITY = 0.25

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.moves_before_change = KillerController.MOVES_MAX_NUM

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KillerController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if np.random.uniform() < KillerController.DO_NOTHING_PROBABILITY:
            return Action.DO_NOTHING

        self.moves_before_change = (self.moves_before_change - 1) \
                                   % KillerController.MOVES_MAX_NUM
        if self.moves_before_change > 0:
            return Action.STEP_FORWARD
        else:
            return Action.TURN_RIGHT

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED


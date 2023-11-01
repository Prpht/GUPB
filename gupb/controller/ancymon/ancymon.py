import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.explore import Explore
from gupb.controller.ancymon.strategies.path_finder import Path_Finder

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

class AncymonController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.environment: Environment = Environment()
        self.path_finder: Path_Finder = Path_Finder(self.environment)
        self.explore: Explore = Explore(self.environment, self.path_finder)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AncymonController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.environment.update_environment(knowledge)

        decision = None

        try:
            decision = self.explore.decide()
        except Exception as e:
            print(f"An exception occurred: {e}")

        if decision == characters.Action.STEP_FORWARD:
            new_position = self.environment.position + self.environment.discovered_map[self.environment.position].character.facing.value
            if self.environment.discovered_map[new_position].character != None:
                decision = characters.Action.ATTACK

        try:
            if self.neer_menhir():
                decision = random.choice(POSSIBLE_ACTIONS)
        except Exception as e:
            print(f"An exception occurred: {e}")

        return decision

    def neer_menhir(self):
        if self.environment.menhir != None:
            margin = 3
            if len(self.environment.discovered_map[self.environment.position].effects) > 0:
                margin = 0
            return (abs(self.environment.menhir[0] - self.environment.position.x) < margin and
                    abs(self.environment.menhir[1] - self.environment.position.y) < margin)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ANCYMON

import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.coordinates import Coords
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.explore import Explore
from gupb.controller.ancymon.strategies.hunter import Hunter
from gupb.controller.ancymon.strategies.path_finder import Path_Finder
from gupb.model.weapons import Knife

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
        self.hunter: Hunter = Hunter(self.environment, self.path_finder)

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
            decision = self.hunter.decide()
            if decision != None:
                return decision
        except Exception as e:
            print(f"An exception occurred in Hunter strategy: {e}")

        try:
            decision = self.explore.decide()
        except Exception as e:
            print(f"An exception occurred in Explore strategy: {e}")

        #After providing hunter decider nothing below should be requierd

        try:
            new_position = self.environment.position + self.environment.discovered_map[
                self.environment.position].character.facing.value
            if self.collect_loot(new_position):
                return POSSIBLE_ACTIONS[2]
            if self.is_menhir_neer():
                return random.choices(
                    population=POSSIBLE_ACTIONS[:3], weights=(20, 20, 60), k=1
                )[0]
        except Exception as e:
            print(f"An exception occurred: {e}")

        return decision

    def is_menhir_neer(self):
        if self.environment.menhir != None:
            margin = self.environment.enemies_left - 2
            if len(self.environment.discovered_map[self.environment.position].effects) > 0:
                margin = 0
            return (abs(self.environment.menhir[0] - self.environment.position.x) < margin and
                    abs(self.environment.menhir[1] - self.environment.position.y) < margin)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.environment = Environment()
        self.path_finder.environment = self.environment
        self.explore.environment = self.environment
        self.hunter.environment = self.environment

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ANCYMON

    def should_attack(self, new_position):
        if self.environment.discovered_map[new_position].character:
            if (
                    self.environment.discovered_map[new_position].character.health
                    <= self.environment.discovered_map[self.environment.position].character.health
            ):
                return True
            # opponent is not facing us
            elif (
                    new_position + self.environment.discovered_map[new_position].character.facing.value
                    == self.environment.position
            ):
                return False

        return False

    def collect_loot(self, new_position):
        return (
            self.environment.discovered_map[new_position].loot and self.environment.weapon == Knife
        ) or self.environment.discovered_map[new_position].consumable

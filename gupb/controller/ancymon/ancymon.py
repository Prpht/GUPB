import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.coordinates import Coords
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.explore import Explore
from gupb.controller.ancymon.strategies.hunter import Hunter
from gupb.controller.ancymon.strategies.item_finder import Item_Finder
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
        self.item_finder: Item_Finder = Item_Finder(self.environment, self.path_finder)
        self.hunter: Hunter = Hunter(self.environment, self.path_finder)
        self.i: int = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AncymonController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.environment.update_environment(knowledge)
        self.i +=1

        decision = None
        strategy = "HUNTER"

        try:
            decision = self.hunter.decide()
            if decision:
                # print(self.i, strategy)
                return decision
        except Exception as e:
            # print(f"An exception occurred in Hunter strategy: {e}")
            pass

        try:
            decision = self.item_finder.decide()
            strategy = "ITEM FINDER"
            if decision:
                # print(self.i, strategy)
                return decision
        except Exception as e:
            # print(f"An exception occurred in Item Finder strategy: {e}")
            pass

        try:
            decision = self.explore.decide()
            strategy = "EXPLORE"
        except Exception as e:
            # print(f"An exception occurred in Explore strategy: {e}")
            pass

        #After providing hunter decider nothing below should be requierd

        try:
            new_position = self.environment.position + self.environment.discovered_map[
                self.environment.position].character.facing.value
            if self.collect_loot(new_position):
                # print(self.i, "COLLECT LOOT")
                return POSSIBLE_ACTIONS[2]
            if self.is_menhir_neer():
                # print(self.i, "EXPLORE MENHIR")
                if self.environment.discovered_map.get(new_position).loot and self.environment.discovered_map.get(new_position).loot.name == 'amulet':
                    return random.choices(
                        population=POSSIBLE_ACTIONS[:2], weights=(50, 50), k=1
                    )[0]
                return random.choices(
                    population=POSSIBLE_ACTIONS[:3], weights=(20, 20, 60), k=1
                )[0]
        except Exception as e:
            # print(f"An exception occurred: {e}")
            pass

        # print(self.i, strategy)
        return decision

    def is_menhir_neer(self):
        if self.environment.menhir != None:
            margin = self.environment.enemies_left
            # margin = 4
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
        self.item_finder.environment = self.environment

    @property
    def name(self) -> str:
        return f"{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ANCYMON

    def collect_loot(self, new_position):
        return (
            self.environment.discovered_map[new_position].loot and self.environment.weapon == Knife
        ) or self.environment.discovered_map[new_position].consumable

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
from gupb.controller.ancymon.strategies.decision_enum import HUNTER_DECISION, ITEM_FINDER_DECISION, EXPLORER_DECISION
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
        self.explorer: Explore = Explore(self.environment, self.path_finder)
        self.item_finder: Item_Finder = Item_Finder(self.environment, self.path_finder)
        self.hunter: Hunter = Hunter(self.environment, self.path_finder)
        self.i: int = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AncymonController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide2(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.environment.update_environment(knowledge)
        self.path_finder.update_paths(self.environment.position)
        self.i += 1

        hunter_decision, item_finder_decision, explorer_decision = None, None, None

        try:
            hunter_decision = self.hunter.decide2()
        except Exception as e:
            print(f"An exception occurred in Hunter strategy: {e}")
            pass

        try:
            item_finder_decision = self.item_finder.decide2()
        except Exception as e:
            print(f"An exception occurred in Item Finder strategy: {e}")
            pass

        try:
            explorer_decision = self.explorer.decide2()
        except Exception as e:
            print(f"An exception occurred in Explorer strategy: {e}")
            pass

        if hunter_decision != HUNTER_DECISION.NO_ENEMY and item_finder_decision != ITEM_FINDER_DECISION.NO_ITEMS and item_finder_decision != ITEM_FINDER_DECISION.ENEMY_ON_NEXT_MOVE:
            if hunter_decision == HUNTER_DECISION.LONG_RANGE_ATTACK:
                print('I see items but i do range attack')
                return self.hunter.next_move
            if hunter_decision == HUNTER_DECISION.ATTACK and self.environment.champion.health > self.hunter.next_target.health:
                print('I see items but i can attack week opponent')
                return self.hunter.next_move
            if hunter_decision == HUNTER_DECISION.CHASE and self.environment.champion.health > self.hunter.next_target.health and self.hunter.path is not None and len(self.hunter.path) <= 5:
                print('I see items but i can chase week opponent')
                return self.hunter.next_move
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_POTION:
                print('I see enemy but i can get fast potion')
                return self.item_finder.next_move
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_LOOT and (self.environment.weapon.name == 'knife' or self.environment.weapon.name == 'bow' or self.hunter.next_target.weapon.name != 'knife'):
                print('I see enemy but i can get fast weapon')
                return self.item_finder.next_move
            return self.hunter.next_move

        if hunter_decision != HUNTER_DECISION.NO_ENEMY:
            if hunter_decision == HUNTER_DECISION.LONG_RANGE_ATTACK:
                print('Long range attack')
                return self.hunter.next_move
            if hunter_decision == HUNTER_DECISION.ATTACK and self.environment.champion.health >= self.hunter.next_target.health:
                print('Classic Attack')
                return self.hunter.next_move
            if self.environment.champion.health >= self.hunter.next_target.health and self.hunter.path is not None and len(self.hunter.path) <= 5:
                print('Classic chase')
                return self.hunter.next_move

        if item_finder_decision != ITEM_FINDER_DECISION.NO_ITEMS:
            if item_finder_decision == ITEM_FINDER_DECISION.ENEMY_ON_NEXT_MOVE:
                print('ENEMY NEXT TODO')
                return characters.Action.ATTACK #TODO
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_POTION:
                if self.item_finder.path is not None and len(self.item_finder.path) < self.environment.enemies_left:
                    print('Go for potion')
                    return self.item_finder.next_move
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_LOOT:
                if self.item_finder.path is not None and len(self.item_finder.path) < self.environment.enemies_left:
                    print('Go for loot')
                    return self.item_finder.next_move

        if explorer_decision:
            print('Explore')
            return self.explorer.next_move

        print(self.i, "EXPLORE MENHIR")
        return random.choices(
            population=POSSIBLE_ACTIONS[:3], weights=(40, 40, 20), k=1
        )[0]

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.decide2(knowledge)
        self.environment.update_environment(knowledge)
        self.path_finder.update_paths(self.environment.position)
        self.i +=1

        decision = None
        strategy = "HUNTER"

        try:
            decision, path = self.hunter.decide()
            if decision:
                print(self.i, strategy)
                return decision
        except Exception as e:
            print(f"An exception occurred in Hunter strategy: {e}")
            pass

        try:
            decision = self.item_finder.decide()
            strategy = "ITEM FINDER"
            if decision:
                print(self.i, strategy)
                return decision
        except Exception as e:
            print(f"An exception occurred in Item Finder strategy: {e}")
            pass

        try:
            decision = self.explorer.decide()
            strategy = "EXPLORE"
        except Exception as e:
            print(f"An exception occurred in Explore strategy: {e}")
            pass

        # After providing hunter decider nothing below should be requierd

        if self.is_menhir_neer():
            print(self.i, "EXPLORE MENHIR")
            return random.choices(
                population=POSSIBLE_ACTIONS[:3], weights=(40, 40, 20), k=1
            )[0]

        print(self.i, strategy)
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
        self.explorer.environment = self.environment
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

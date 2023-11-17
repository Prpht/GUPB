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

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.environment.update_environment(knowledge)
        self.path_finder.update_paths(self.environment.position)
        self.i += 1
        print(self.i, end=' ')

        hunter_decision, item_finder_decision, explorer_decision = None, None, None

        try:
            hunter_decision = self.hunter.decide()
        except Exception as e:
            print(f"An exception occurred in Hunter strategy: {e}")
            pass

        try:
            item_finder_decision = self.item_finder.decide()
        except Exception as e:
            print(f"An exception occurred in Item Finder strategy: {e}")
            pass

        try:
            explorer_decision = self.explorer.decide()
        except Exception as e:
            print(f"An exception occurred in Explorer strategy: {e}")
            pass

        if hunter_decision != HUNTER_DECISION.NO_ENEMY and item_finder_decision != ITEM_FINDER_DECISION.NO_ITEMS: #Podnoś potki zamiast gonić
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_POTION:
                if hunter_decision == HUNTER_DECISION.CHASE:
                    if len(self.hunter.path) > len(self.item_finder.path) or self.environment.champion.health <= self.hunter.next_target.health:
                        print('Go for potion instead of chasing')
                        return self.item_finder.next_move


        if hunter_decision != HUNTER_DECISION.NO_ENEMY:
            if hunter_decision == HUNTER_DECISION.LONG_RANGE_ATTACK: # Jeżeli przeciwnik sam nie ma jakiejś dalekosiężnej broni
                print('Long range attack')
                return self.hunter.next_move
            if hunter_decision == HUNTER_DECISION.ATTACK:
                if self.environment.champion.health >= self.hunter.next_target.health:
                    print('Classic Attack')
                    return self.hunter.next_move
            if hunter_decision == HUNTER_DECISION.CHASE: #Ostatnio goniliśmy gościa przez pół mapy więc trzeba to uwzględnić że gość może się pchać w mgłę, więc jeżeli się pcha to odpuszczamy
                if (self.environment.champion.health >= self.hunter.next_target.health
                        and self.hunter.path is not None and (len(self.hunter.path) <= 4) or self.is_menhir_neer()):
                    print('Classic chase')
                    return self.hunter.next_move

        if item_finder_decision != ITEM_FINDER_DECISION.NO_ITEMS:
            if item_finder_decision == ITEM_FINDER_DECISION.ENEMY_ON_NEXT_MOVE:
                if self.item_finder.next_move == characters.Action.STEP_FORWARD:
                    print('Item finder, enemy next TODO')
                    return characters.Action.ATTACK #TODO
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_POTION:
                if self.item_finder.path is not None and len(self.item_finder.path) <= self.environment.enemies_left + 3:
                    print('Go for potion')
                    return self.item_finder.next_move
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_LOOT:
                if (self.item_finder.path is not None and len(self.item_finder.path) <= self.environment.enemies_left + 3 and
                        (self.environment.weapon.name == 'knife' or self.environment.weapon.name.find('bow') >= 0)):
                    print('Go for loot')
                    return self.item_finder.next_move

        if explorer_decision:
            if explorer_decision == EXPLORER_DECISION.ENEMY_ON_NEXT_MOVE:
                if self.explorer.next_move == characters.Action.STEP_FORWARD:
                    print('Explorer: enemy next')
                    return characters.Action.ATTACK #TODO
            if explorer_decision == EXPLORER_DECISION.EXPLORE and self.is_menhir_neer() is False:
                print('Explore')
                return self.explorer.next_move

            print("EXPLORE MENHIR")
            return random.choices(
                population=POSSIBLE_ACTIONS[:3], weights=(40, 40, 20), k=1
            )[0]

        print('UNEXPECTED MOVE - EXCEPTION')
        return characters.Action.TURN_RIGHT

    def is_menhir_neer(self):
        if self.environment.menhir is None:
            return False
        if len(self.explorer.path) <= self.environment.enemies_left:
            return True
        return False

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.environment = Environment()
        self.path_finder.environment = self.environment
        self.explorer.environment = self.environment
        self.explorer.reset()
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

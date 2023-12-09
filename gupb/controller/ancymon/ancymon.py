import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
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
        self.path_finder: Path_Finder = Path_Finder(self.environment, False)
        self.alternative_path_finder: Path_Finder = Path_Finder(self.environment, True)
        self.explorer: Explore = Explore(self.environment)
        self.item_finder: Item_Finder = Item_Finder(self.environment)
        self.hunter: Hunter = Hunter(self.environment)
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
        self.alternative_path_finder.update_paths(self.environment.position)
        self.i += 1

        hunter_decision, item_finder_decision, explorer_decision = None, None, None
        took_damage = self.environment.took_damage()

        try:
            hunter_decision = self.hunter.decide(self.path_finder)
        except Exception as e:
            # print(f"An exception occurred in Hunter strategy: {e}")
            pass

        try:
            temporary_item_finder_decision = self.item_finder.decide(self.alternative_path_finder)
            if temporary_item_finder_decision == ITEM_FINDER_DECISION.NO_ALTERNATIVE_PATH:
                item_finder_decision = self.item_finder.decide(self.path_finder)
            else:
                item_finder_decision = temporary_item_finder_decision
        except Exception as e:
            # print(f"An exception occurred in Item Finder strategy: {e}")
            pass

        try:
            temporary_explorer_decision = self.explorer.decide(self.alternative_path_finder)
            if temporary_explorer_decision == EXPLORER_DECISION.NO_ALTERNATIVE_PATH:
                explorer_decision = self.explorer.decide(self.path_finder)
            else:
                explorer_decision = temporary_explorer_decision
        except Exception as e:
            # print(f"An exception occurred in Explorer strategy: {e}")
            pass

        if took_damage:
            self.environment.flee_moves = 3
        try:
            if self.environment.flee_moves > 0:
                self.environment.flee_moves -= 1
                self.item_finder.next_move = self.path_finder.next_action(self.item_finder.path, True)
                self.explorer.next_move = self.path_finder.next_action(self.explorer.path, True)
        except Exception as e:
            # print(f"An exception occurred in Flee Startegy: {e}")
            pass

        if hunter_decision != HUNTER_DECISION.NO_ENEMY and item_finder_decision != ITEM_FINDER_DECISION.NO_ITEMS:
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_POTION:
                if hunter_decision == HUNTER_DECISION.CHASE:
                    if len(self.hunter.path) >= len(self.item_finder.path) or self.environment.champion.health <= self.hunter.next_target.health:
                        if len(self.item_finder.path) <= self.environment.enemies_left + 4:
                            # print('Go for potion instead of chasing')
                            return self.item_finder.next_move
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_LOOT:
                if hunter_decision == HUNTER_DECISION.CHASE:
                    if len(self.hunter.path) >= len(self.item_finder.path) or self.environment.champion.health <= self.hunter.next_target.health:
                        if len(self.item_finder.path) <= self.environment.enemies_left + 3:
                            if self.environment.weapon.name == 'knife' or self.environment.weapon.name.find('bow') >= 0:
                                # print('Go for weapon instead of chasing')
                                return self.item_finder.next_move


        if hunter_decision != HUNTER_DECISION.NO_ENEMY:
            if hunter_decision == HUNTER_DECISION.ATTACK:
                if self.environment.champion.health >= self.hunter.next_target.health:
                    # print('Classic Attack')
                    return self.hunter.next_move
                if self.hunter.next_target.weapon.name.find('bow') >= 0:
                    if self.environment.champion.health * 3 >= self.hunter.next_target.health * 2:
                        # print('Attack BowMan')
                        return self.hunter.next_move
            if hunter_decision == HUNTER_DECISION.CHASE:
                if (self.environment.champion.health >= self.hunter.next_target.health
                        and self.hunter.path is not None and len(self.hunter.path) <= 4):
                    # print('Classic chase')
                    return self.hunter.next_move
                if self.hunter.next_target.weapon.name.find('bow') >= 0:
                    if self.environment.champion.health * 3 >= self.hunter.next_target.health * 2:
                        # print('Chase BowMan')
                        return self.hunter.next_move

        if item_finder_decision is not ITEM_FINDER_DECISION.NO_ITEMS:
            if item_finder_decision == ITEM_FINDER_DECISION.ENEMY_ON_NEXT_MOVE:
                if self.item_finder.next_move == characters.Action.STEP_FORWARD:
                    # print('Item finder, enemy on way, no other path, attack')
                    return characters.Action.ATTACK
                if hunter_decision == HUNTER_DECISION.CHASE:
                    # print('Item finder, enemy on way, chase path')
                    return self.hunter.next_move
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_POTION:
                if self.item_finder.path is not None and len(self.item_finder.path) <= self.environment.enemies_left + 3:
                    # print('Go for potion')
                    return self.item_finder.next_move
            if item_finder_decision == ITEM_FINDER_DECISION.GO_FOR_LOOT:
                if (self.item_finder.path is not None and len(self.item_finder.path) <= self.environment.enemies_left + 3 and
                        (self.environment.weapon.name == 'knife' or self.environment.weapon.name.find('bow') >= 0)):
                    # print('Go for loot')
                    return self.item_finder.next_move

        if explorer_decision:
            if explorer_decision == EXPLORER_DECISION.ENEMY_ON_NEXT_MOVE:
                if self.explorer.next_move == characters.Action.STEP_FORWARD:
                    # print('Explorer, enemy on way, no other path, attack')
                    return characters.Action.ATTACK
                if hunter_decision == HUNTER_DECISION.CHASE:
                    # print('Explorer, enemy on way, chase path')
                    return self.hunter.next_move
            if explorer_decision == EXPLORER_DECISION.EXPLORE and self.is_menhir_neer() is False:
                # print('Explore')
                return self.explorer.next_move

            # print("EXPLORE MENHIR")
            return random.choices(
                population=POSSIBLE_ACTIONS[:3], weights=(40, 40, 20), k=1
            )[0]

        # print('UNEXPECTED MOVE - EXCEPTION')
        return characters.Action.TURN_RIGHT

    def is_menhir_neer(self):
        if self.environment.menhir is None:
            return False
        if self.environment.mist_seen is True and len(self.explorer.path) <= self.environment.enemies_left:
            return True
        return False

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.environment = Environment()
        self.path_finder.environment = self.environment
        self.alternative_path_finder.environment = self.environment
        self.hunter.environment = self.environment
        self.item_finder.environment = self.environment
        self.explorer.environment = self.environment

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

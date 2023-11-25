import random
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.path_finder import Path_Finder
from gupb.controller.ancymon.strategies.decision_enum import ITEM_FINDER_DECISION
from gupb.model import characters
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Sword, Bow, Amulet, Axe

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class Item_Finder:
    def __init__(self, environment: Environment):
        self.environment: Environment = environment
        self.path_finder: Path_Finder = None

        self.potion_coord: Coords = None
        self.loot_coord: Coords = None

        self.decision: ITEM_FINDER_DECISION = None
        self.next_move: characters.Action = None
        self.path: list[Coords] = None

    def decide(self, path_finder: Path_Finder):
        self.path_finder = path_finder
        self.next_move = None
        self.path = None
        self.update_items_knowladge()

        if self.potion_coord:
            self.next_move, self.path = self.path_finder.calculate_next_move(self.potion_coord)
            if self.next_move is None or self.path is None:
                # print('Potion Finder Alternate path case')
                return ITEM_FINDER_DECISION.NO_ALTERNATIVE_PATH
            if self.is_enemy_on_path():
                return ITEM_FINDER_DECISION.ENEMY_ON_NEXT_MOVE
            return ITEM_FINDER_DECISION.GO_FOR_POTION

        if self.loot_coord:
            self.next_move, self.path = self.path_finder.calculate_next_move(self.loot_coord)
            if self.next_move is None or self.path is None:
                # print('Potion Finder Alternate path case')
                return ITEM_FINDER_DECISION.NO_ALTERNATIVE_PATH
            if self.is_enemy_on_path():
                return ITEM_FINDER_DECISION.ENEMY_ON_NEXT_MOVE
            return ITEM_FINDER_DECISION.GO_FOR_LOOT

        return ITEM_FINDER_DECISION.NO_ITEMS

    def is_enemy_on_path(self) -> bool:
        if self.path and len(self.path) >= 2:
            field = self.environment.discovered_map.get(self.path[1])
            if field and field.character and field.character.controller_name != self.environment.champion.controller_name:
                return True
        return False

    def update_items_knowladge(self):
        potion_dist = float('inf')
        loot_dist = float('inf')
        self.potion_coord = None
        self.loot_coord = None

        for coords, description in self.environment.discovered_map.items():
            coords = Coords(coords[0], coords[1])
            path_len_to_coords = self.path_finder.calculate_path_length(coords)
            if description.consumable and description.consumable.name == 'potion':
                if self.potion_coord is None or path_len_to_coords < potion_dist:
                    self.potion_coord = coords
                    potion_dist = path_len_to_coords
            if description.loot and (description.loot.name.find('bow') < 0 or (description.loot.name.find('bow') >= 0 and self.environment.weapon.name == 'knife')):
                if self.loot_coord is None or path_len_to_coords < loot_dist:
                    self.loot_coord = coords
                    loot_dist = path_len_to_coords



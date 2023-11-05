import random
from gupb.controller.ancymon.environment import Environment
from gupb.controller.ancymon.strategies.path_finder import Path_Finder
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
    def __init__(self, environment: Environment, path_finder: Path_Finder):
        self.environment: Environment = environment
        self.path_finder: Path_Finder = path_finder
        self.potion_coord: Coords = None
        self.loot_coord: Coords = None

    def decide(self) -> characters.Action:
        self.update_items_knowladge()

        if self.potion_coord and self.manhatan_distance(self.environment.position, self.potion_coord) < self.environment.enemies_left + 3:
            # print("GO FOR POTION")
            decision = self.path_finder.caluclate(self.environment.position, self.potion_coord)
            return self.should_attack(decision)


        if self.loot_coord and (self.environment.weapon.name == 'knife' or self.environment.weapon.name == 'amulet') and self.manhatan_distance(self.environment.position, self.loot_coord) < self.environment.enemies_left + 3:
            # print("GO FOR LOOT")
            decision = self.path_finder.caluclate(self.environment.position, self.loot_coord)
            return self.should_attack(decision)

        return None

    def should_attack(self, decision):
        if decision == characters.Action.STEP_FORWARD:
            new_position = self.environment.position + self.environment.discovered_map[
                self.environment.position].character.facing.value
            if self.environment.discovered_map[new_position].character != None:
                # print("KILL WHILE ITEM SEARCH")
                return characters.Action.ATTACK
        return decision
    def manhatan_distance(self, start: Coords, end: Coords):
        return abs(start.x - end.x) + abs(start.y - end.y)
    def update_items_knowladge(self):
        potion_dist = float('inf')
        loot_dist = float('inf')
        self.potion_coord = None
        self.loot_coord = None

        for coords, desciption in self.environment.discovered_map.items():
            coords = Coords(coords[0], coords[1])
            if desciption.consumable and desciption.consumable.name == 'potion':
                if self.potion_coord is None or self.manhatan_distance(self.environment.position, coords) < potion_dist:
                    self.potion_coord = coords
                    potion_dist = self.manhatan_distance(self.environment.position, coords)
            if desciption.loot and desciption.loot.name != 'amulet':
                if self.loot_coord is None or self.manhatan_distance(self.environment.position, coords) < loot_dist:
                    self.loot_coord = coords
                    loot_dist = self.manhatan_distance(self.environment.position, coords)



import random
import traceback

import numpy as np
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from scipy.ndimage import label

from gupb import controller
from gupb.controller.bupg.knowledge.map import MapKnowledge
from gupb.controller.bupg.strategies.find_menhir import MenhirEstimator
from gupb.controller.bupg.utils import position_change_to_move
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import Facing, Action
from gupb.model.coordinates import Coords
from gupb.model.weapons import Axe, Bow, Sword, Knife, Scroll, Amulet, PropheticWeapon

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BUPGController(controller.Controller):
    WEAPON_PRIORITY = ["axe", "sword", "bow_unloaded", "bow_loaded", "amulet", "scroll", "propheticweapon", "knife"]

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.map_knowledge: MapKnowledge | None = None
        self.menhir_estimator = None
        self.grid = None
        self.weapon = None
        self.health = None
        self.facing = None
        self.pathfinder = AStarFinder()
        self.position = None
        self.tries = 0
        self.ticks = 0
        self.me = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BUPGController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def estimate_menhir(self, knowledge: characters.ChampionKnowledge):
        menhir_estimate, weight = self.menhir_estimator.estimate_menhir(knowledge)

        if menhir_estimate is not None:
            self.map_knowledge.update_menhir_location(menhir_estimate, weight)
            print(f"Estimated menhir location: {self.map_knowledge.estimated_menhir_location}")

    def update_knowledge(self, knowledge: characters.ChampionKnowledge):
        self.map_knowledge.update_terrain(knowledge)
        # self.map_knowledge.episode_tick()
        # self.estimate_menhir(knowledge)

        self.me = knowledge.visible_tiles[knowledge.position].character
        self.weapon = self.me.weapon
        self.health = self.me.health
        self.facing = self.me.facing

    def facing_enemy(self, knowledge: characters.ChampionKnowledge):
        tile_in_front = knowledge.visible_tiles[self.position + self.facing.value]
        return tile_in_front.character is not None and tile_in_front.character != self.me

    def enemy_in_range(self, knowledge: characters.ChampionKnowledge):
        if self.weapon.name == "axe":
            wpn_class = Axe
        elif self.weapon.name == "sword":
            wpn_class = Sword
        elif self.weapon.name == "bow_unloaded" or self.weapon.name == "bow_loaded":
            wpn_class = Bow
        elif self.weapon.name == "knife":
            wpn_class = Knife
        elif self.weapon.name == "scroll":
            wpn_class = Scroll
        elif self.weapon.name == "amulet":
            wpn_class = Amulet
        elif self.weapon.name == "propheticweapon":
            wpn_class = PropheticWeapon
        else:
            return False

        coords = wpn_class.cut_positions(self.map_knowledge.terrain, self.position, self.facing)

        all_coords = set(coords) & set(knowledge.visible_tiles.keys())

        for coord in coords:
            tile = knowledge.visible_tiles[coord]
            if tile.character is not None and tile.character != self.me:
                return True

        return False

    def find_best_weapon(self):
        for weapon in self.WEAPON_PRIORITY:
            # we already have the best available weapon
            if weapon == self.weapon.name:
                return None

            weapon_coords = self.map_knowledge.find_closest_weapon(self.position, weapon)
            if weapon_coords is not None:
                return weapon_coords

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.ticks += 1
            position_changed = knowledge.position != self.position

            self.update_knowledge(knowledge)
            self.position = knowledge.position

            most_unknown_point = self.map_knowledge.get_most_unknown_point()

            dist_to_potion, point = self.map_knowledge.distance_to_potion(self.position)
            if dist_to_potion <= 3:
                point_to_go = point
            else:
                if weapon_coords := self.find_best_weapon():
                    point_to_go = weapon_coords
                elif self.map_knowledge.menhir_location:
                    dist_to_mist = self.map_knowledge.distance_to_mist(self.position)
                    tree_coord = self.map_knowledge.find_closest_tree(self.map_knowledge.menhir_location)

                    if dist_to_mist > 5 and tree_coord and abs(self.map_knowledge.menhir_location[0] - tree_coord[0]) + abs(self.map_knowledge.menhir_location[1] - tree_coord[1]) <= 8:
                        point_to_go = tree_coord

                        if self.position == point_to_go:
                            if self.enemy_in_range(knowledge):
                                return characters.Action.ATTACK
                    else:
                        point_to_go = self.map_knowledge.menhir_location
                else:
                    point_to_go = most_unknown_point

            if not position_changed and self.tries <= 1:
                self.tries += 1
                if action := self.go(knowledge.position, Coords(*point_to_go), self.facing):
                    return action

            if not position_changed and self.tries <= 3:
                if self.facing_enemy(knowledge):
                    return characters.Action.ATTACK
                else:
                    self.tries += 1
                    return characters.Action.TURN_LEFT

            self.tries = 0
        except:
            print(traceback.print_exc())
        # Just Dance
        return characters.Action.TURN_LEFT if random.random() > 0.5 else characters.Action.TURN_RIGHT

    def go(self, start: Coords, end: Coords, facing: Facing) -> Action | None:
        """
        Args:
            start (Coords): The current position (x, y)
            end (Coords): The target position (x, y)
            facing (Facing): The current facing direction of the champion.
        """
        self.grid.cleanup()

        start = self.grid.node(*start)
        end = self.grid.node(*end)

        path, runs = self.pathfinder.find_path(start, end, self.grid)
        if len(path) > 1:
            return position_change_to_move(
                (path[1].y, path[1].x),
                (start.y, start.x),
                facing
            )

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.map_knowledge = MapKnowledge(terrain=Arena.load(arena_description.name).terrain)
        self.menhir_estimator = MenhirEstimator(self.map_knowledge)
        self.ticks = 0
        self.create_grid()

    def create_grid(self):
        W = max(self.map_knowledge.terrain, key=lambda x: x[0])[0] + 1
        H = max(self.map_knowledge.terrain, key=lambda x: x[1])[1] + 1
        self.grid = np.zeros(shape=(H, W))

        for (x, y), tile in self.map_knowledge.terrain.items():
            if tile.terrain_passable():
                self.grid[y, x] = 1

        def find_largest_blob(arr):
            # Label connected components (4-connectivity by default)
            labeled_array, num_features = label(arr)

            # Count sizes of all blobs (excluding background label 0)
            sizes = np.bincount(labeled_array.ravel())
            sizes[0] = 0  # ignore background

            # Get label of largest blob
            max_label = sizes.argmax()
            max_size = sizes[max_label]

            # Create a mask for the largest blob
            largest_blob = (labeled_array == max_label)

            return largest_blob.astype(np.uint8)

        self.grid = find_largest_blob(self.grid)

        self.map_knowledge.looked_at = self.grid
        self.map_knowledge.remove_unreachable_weapons()

        for (x, y), tile in self.map_knowledge.terrain.items():
            if tile.loot and self.grid[x, y] > 0:
                self.grid[x, y] = 3 + self.WEAPON_PRIORITY.index(tile.loot.description().name)

        self.grid = Grid(matrix=self.grid)

    @property
    def name(self) -> str:
        return f'BUPG {self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.MINION


POTENTIAL_CONTROLLERS = [
    BUPGController("Minion")
]

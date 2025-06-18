import random
import traceback

import numpy as np
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from scipy.ndimage import label

from gupb import controller
from gupb.controller.bupg.knowledge.map import MapKnowledge
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
    WEAPON_PRIORITY = ["knife", "sword", "axe", "bow_unloaded", "bow_loaded", "amulet", "scroll"]

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
        self.knowledge: characters.ChampionKnowledge | None = None
        self.initial_grid = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BUPGController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def update_knowledge(self, knowledge: characters.ChampionKnowledge):
        self.map_knowledge.update_terrain(knowledge)
        self.knowledge = knowledge

        self.me = knowledge.visible_tiles[knowledge.position].character
        self.weapon = self.me.weapon
        self.health = self.me.health
        self.facing = self.me.facing

    def facing_enemy(self, knowledge: characters.ChampionKnowledge):
        tile_in_front = knowledge.visible_tiles[self.position + self.facing.value]
        return tile_in_front.character is not None and tile_in_front.character != self.me

    def is_safe(self, position: Coords):
        """
        Check if the position is safe based on the danger map.
        """
        return self.map_knowledge.danger_map[position[1], position[0]] == 0

    def enemy_in_range(self):
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

        all_coords = set(coords) & set(self.knowledge.visible_tiles.keys())

        for coord in coords:
            if coord not in self.map_knowledge.terrain:
                continue
            tile = self.knowledge.visible_tiles[coord]
            if tile.character is not None and tile.character != self.me:
                return True

        return False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.ticks += 1
            position_changed = knowledge.position != self.position

            self.update_knowledge(knowledge)
            self.position = knowledge.position


            is_safe_here = self.map_knowledge.danger_map[self.position[1], self.position[0]] == 0

            if is_safe_here and self.enemy_in_range():
                return characters.Action.ATTACK

            most_unknown_point = self.map_knowledge.get_most_unknown_point()

            dist_to_potion, potion_point = self.distance_to_potion()
            dist_to_weapon, weapon_point = self.distance_to_weapon()
            dist_to_mist = self.map_knowledge.distance_to_mist(self.position)

            field_up = self.position + Facing.DOWN.value
            field_down = self.position + Facing.UP.value
            field_left = self.position + Facing.LEFT.value
            field_right = self.position + Facing.RIGHT.value

            fields = [field_up, field_down, field_left, field_right]

            safety_flags = {}
            safety_values = {}
            for field in fields:
                if field not in self.map_knowledge.terrain:
                    safety_values[field] = float("inf")
                    safety_flags[field] = False
                    continue
                if not self.map_knowledge.terrain[field].terrain_passable():
                    safety_values[field] = float("inf")
                    safety_flags[field] = False
                    continue

                safety_values[field] = self.map_knowledge.danger_map[field[1], field[0]]
                safety_flags[field] = self.is_safe(field)

            if dist_to_potion < 4 and potion_point:
                next_position = self.plan_path(self.position, potion_point, self.facing)
                if next_position and safety_flags[next_position]:
                    action = self.go(knowledge.position, Coords(*next_position), self.facing)
                    if is_safe_here:
                        return self.rotate_if_possible(action)
                    return action

            if dist_to_weapon < 4 and weapon_point:
                next_position = self.plan_path(self.position, weapon_point, self.facing)
                if next_position and safety_flags[next_position]:
                    action = self.go(knowledge.position, Coords(*next_position), self.facing)
                    if is_safe_here:
                        return self.rotate_if_possible(action)
                    return action

            if self.map_knowledge.menhir_location is None:
                next_position = self.plan_path(self.position, most_unknown_point, self.facing)
                if next_position and safety_flags[next_position]:
                    action = self.go(knowledge.position, Coords(*next_position), self.facing)
                    if is_safe_here:
                        return self.rotate_if_possible(action)
                    return action

            if self.map_knowledge.menhir_location:
                if dist_to_mist > 3 and self.is_in_tree():
                    if self.enemy_in_range():
                        return characters.Action.ATTACK
                    else:
                        return characters.Action.TURN_LEFT

                if dist_to_mist > 3 and not self.is_in_tree():
                    dist_to_tree, tree_cord = self.distance_to_tree()

                    if tree_cord:
                        next_position = self.plan_path(self.position, tree_cord, self.facing)
                        if next_position and safety_flags[next_position]:
                            action = self.go(knowledge.position, Coords(*next_position), self.facing)
                            if is_safe_here:
                                return self.rotate_if_possible(action)
                            return action

                menhir_coord = self.map_knowledge.menhir_location
                next_position = self.plan_path(self.position, menhir_coord, self.facing)
                if next_position and safety_flags[next_position]:
                    action = self.go(knowledge.position, Coords(*next_position), self.facing)
                    if is_safe_here:
                        return self.rotate_if_possible(action)
                    return action

            min_safe_level = min(safety_values.values())
            min_safe_coords = [k for k, v in safety_values.items() if v == min_safe_level]

            if min_safe_coords:
                next_position = self.plan_path(self.position, min_safe_coords[0], self.facing)
                if next_position and safety_flags[next_position]:
                    action = self.go(knowledge.position, Coords(*next_position), self.facing)
                    if is_safe_here:
                        return self.rotate_if_possible(action)
                    return action
        except:
            print(traceback.print_exc())
        # Just Dance
        return characters.Action.TURN_LEFT if random.random() > 0.5 else characters.Action.TURN_RIGHT

    def is_in_tree(self):
        """
        Check if the champion is currently in a tree tile.
        """
        return self.map_knowledge.terrain[self.position].description().type == 'forest'

    def rotate_if_possible(self, action: characters.Action) -> characters.Action:
        """
        Rotate the facing direction if the action is a turn action.
        """
        if action == characters.Action.STEP_FORWARD:
            return action
        elif action in [characters.Action.STEP_LEFT, characters.Action.STEP_BACKWARD]:
            return characters.Action.TURN_LEFT
        else:
            return characters.Action.TURN_RIGHT

    def plan_path(self, start: Coords, end: Coords, facing: Facing) -> Coords | None:
        """
        Args:
            start (Coords): The current position (x, y)
            end (Coords): The target position (x, y)
        """
        grid = Grid(matrix=self.initial_grid + self.map_knowledge.danger_map * self.initial_grid)
        img = matrix=self.initial_grid + self.map_knowledge.danger_map * self.initial_grid

        start = grid.node(*start)
        end = grid.node(*end)

        path, runs = self.pathfinder.find_path(start, end, grid)
        if len(path) > 1:
            return Coords(path[1].x, path[1].y)
        return None

    def go(self, start: Coords, end: Coords, facing: Facing) -> Action | None:
        """
        Args:
            start (Coords): The current position (x, y)
            end (Coords): The target position (x, y)
            facing (Facing): The current facing direction of the champion.
        """
        return position_change_to_move(
            (end.y, end.x),
            (start.y, start.x),
            facing
        )

    def distance_to_potion(self) -> tuple[float, Coords | None]:
        if not self.map_knowledge.consumables:
            return float("inf"), None

        grid = Grid(matrix=self.initial_grid + self.map_knowledge.danger_map * self.initial_grid)
        min_path_length = float("inf")
        min_path_coords = None

        for coords in self.map_knowledge.consumables:
            if coords in self.map_knowledge.mist:
                continue

            grid.cleanup()
            start = grid.node(self.position[0], self.position[1])
            end = grid.node(coords.x, coords.y)

            path, runs = self.pathfinder.find_path(start, end, grid)

            if 0 < len(path) < min_path_length:
                min_path_length = len(path)
                min_path_coords = coords

        return min_path_length, min_path_coords

    def distance_to_weapon(self) -> tuple[float, Coords | None]:
        if not self.map_knowledge.weapons:
            return float("inf"), None

        grid = Grid(matrix=self.initial_grid + self.map_knowledge.danger_map * self.initial_grid)

        min_path_length = float("inf")
        min_path_coords = None

        for coords, weapon in self.map_knowledge.weapons.items():
            if coords in self.map_knowledge.opponents or coords in self.map_knowledge.mist:
                continue

            if self.WEAPON_PRIORITY.index(weapon.name) <= self.WEAPON_PRIORITY.index(self.weapon.name):
                continue

            grid.cleanup()
            start = grid.node(*self.position)
            end = grid.node(*coords)

            path, runs = self.pathfinder.find_path(start, end, grid)

            if 0 < len(path) < min_path_length:
                min_path_length = len(path)
                min_path_coords = coords

        return min_path_length, min_path_coords

    def distance_to_tree(self) -> tuple[float, Coords | None]:
        if not self.map_knowledge.trees:
            return float("inf"), None

        grid = Grid(matrix=self.initial_grid + self.map_knowledge.danger_map * self.initial_grid)

        min_path_length = float("inf")
        min_path_coords = None

        for coords in self.map_knowledge.trees:
            if coords in self.map_knowledge.opponents or coords in self.map_knowledge.mist:
                continue

            grid.cleanup()
            start = grid.node(*self.position)
            end = grid.node(*coords)

            path, runs = self.pathfinder.find_path(start, end, grid)

            if 0 < len(path) < min_path_length:
                min_path_length = len(path)
                min_path_coords = coords

        return min_path_length, min_path_coords


    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.map_knowledge = MapKnowledge(terrain=Arena.load(arena_description.name).terrain)
        self.ticks = 0
        self.create_grid()

    def create_grid(self):
        W = max(self.map_knowledge.terrain, key=lambda x: x[0])[0] + 1
        H = max(self.map_knowledge.terrain, key=lambda x: x[1])[1] + 1
        self.initial_grid = np.zeros(shape=(H, W))

        for (x, y), tile in self.map_knowledge.terrain.items():
            if tile.terrain_passable():
                self.initial_grid[y, x] = 1

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

        self.initial_grid = find_largest_blob(self.initial_grid)

        self.map_knowledge.looked_at = self.initial_grid.copy()
        self.map_knowledge.remove_unreachable_weapons()

        for (x, y), tile in self.map_knowledge.terrain.items():
            if tile.loot and self.initial_grid[y, x] > 0:
                self.initial_grid[y, x] = 3 + self.WEAPON_PRIORITY.index(tile.loot.description().name)

        self.grid = Grid(matrix=self.initial_grid.copy())

    @property
    def name(self) -> str:
        return f'BUPG {self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.MINION


POTENTIAL_CONTROLLERS = [
    BUPGController("Minion")
]

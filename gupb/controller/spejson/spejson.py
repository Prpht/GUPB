import random
import numpy as np

from gupb import controller
from gupb.controller.spejson.static_map_processing import analyze_map
from gupb.controller.spejson.dynamic_map_processing import analyze_weapons_on_map, find_closest_weapon
from gupb.controller.spejson.pathfinding import find_path, pathfinding_next_move, pathfinding_next_move_in_cluster
from gupb.controller.spejson.utils import POSSIBLE_ACTIONS, weapons, facing_to_letter, weapons_name_to_letter
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action
from gupb.model.coordinates import Coords


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Spejson(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.position = None
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.menhir_location = Coords(16, 16)
        self.target = Coords(16, 16)
        self.jitter = 0
        self.weapons_knowledge = None
        self.closest_weapon = None
        self.mist_spotted = False
        self.panic_mode = 0
        self.touched_by_mist = False
        self.clusters = None
        self.adj = None
        self.terrain = None
        self.latest_states = []
        self.map_height = 0
        self.map_width = 0

        self.scalars = {
            'my_hp': [0],  # Health points rescaled to 0-1
            'my_weapon': [0, 0, 0, 0, 0],  # One-hot encoding of current weapon (Knife, Axe, Bow, Sword, Amulet)
            'someone_in_range': [0],  # 1 if yes, 0 otherwise
            'me_in_dmg_range': [0],  # 1 if yes, 0 otherwise
            'epoch_num': [0],  # Rescaled by 0.02 factor
            'move_to_axe': [0, 0, 0],  # One-hot encoding of move type (Left, Right, Forward) - to Axe
            'move_to_bow': [0, 0, 0],  # One-hot encoding of move type (Left, Right, Forward) - to Bow
            'move_to_sword': [0, 0, 0],  # One-hot encoding of move type (Left, Right, Forward) - to Sword
            'move_to_amulet': [0, 0, 0],  # One-hot encoding of move type (Left, Right, Forward) - to Amulet
            'move_to_menhir': [0, 0, 0],  # One-hot encoding of move type (Left, Right, Forward)
            'keypoint_dist': [0, 0, 0, 0, 0],  # Graph-hop dists to each weapon type and menhir
            'menhir_found': [0],  # 1 if yes, 0 otherwise
            'mist_spotted': [0],  # 1 if yes, 0 otherwise
            'mist_close': [0],  # 1 if yes, 0 otherwise
            'bow_unloaded': [0],  # 1 if yes, 0 otherwise
        }

        self.matrices = {
            'walkability': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'visibility': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'is_wall': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'someone_here': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'character_hp': np.zeros([13, 13, 1], dtype=float),  # Health points rescaled to 0-1
            'character_weapon': np.zeros([13, 13, 5], dtype=float),  # One-hot encoding of current weapon (Knife, Axe, Bow, Sword, Amulet)
            'menhir_loc': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'weapon_loc': np.zeros([13, 13, 5], dtype=float),  # 1 if yes, 0 otherwise (Knife, Axe, Bow, Sword, Amulet)
            'mist_effect': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'damage_effect': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'my_dmg_range': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'others_dmg_range': np.zeros([13, 13, 1], dtype=float),  # 1 if yes, 0 otherwise
            'min_distance': np.zeros([13, 13, 1], dtype=float),  # log(1 + value) of graph-hop distance
            'attackability_fct': np.zeros([13, 13, 5], dtype=float),  # value
            'betweenness_centr': np.zeros([13, 13, 1], dtype=float),  # value
            'non_cluster_coeff': np.zeros([13, 13, 1], dtype=float),  # value
            'borderedness': np.zeros([13, 13, 1], dtype=float),  # value
        }

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Spejson):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.move_number += 1
        self.panic_mode -= 1
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        available_actions = POSSIBLE_ACTIONS.copy()

        me = knowledge.visible_tiles[position].character
        self.position = position
        self.facing = me.facing
        self.health = me.health
        self.weapon = me.weapon

        self.latest_states = (self.latest_states + [(self.position, self.facing)])[-5:]
        if len(self.latest_states) >= 5 and (
                self.latest_states[0] == self.latest_states[1] == self.latest_states[2]
                == self.latest_states[3] == self.latest_states[4]
        ):
            self.panic_mode = 6
            for _ in range(50):  # Just to avoid while True lol
                rx, ry = np.random.randint(min(self.map_height, self.map_width), size=[2])
                if self.clusters[(ry, rx)]:
                    self.target = Coords(x=rx, y=ry)
                    break

        to_del = []
        for pos in self.weapons_knowledge:
            pos = Coords(x=pos[1], y=pos[0])
            if pos in visible_tiles:
                loot = visible_tiles[pos].loot
                if loot is None:
                    to_del += [(pos.y, pos.x)]
                else:
                    self.weapons_knowledge[(pos.y, pos.x)] = weapons_name_to_letter[loot.name]

        if (position.y, position.x) in self.weapons_knowledge:
            to_del += [(position.y, position.x)]

        for pos in to_del:
            del self.weapons_knowledge[pos]

        for tile_coord in visible_tiles:
            tile = visible_tiles[tile_coord]
            if (tile_coord[1], tile_coord[0]) not in self.weapons_knowledge and tile.loot is not None \
                    and tile.loot.name != 'knife':
                self.weapons_knowledge[(tile_coord[1], tile_coord[0])] = weapons_name_to_letter[tile.loot.name]

        self.closest_weapon = analyze_weapons_on_map(self.weapons_knowledge, self.clusters)

        if not self.menhir_found:
            for tile_coord in visible_tiles:
                if visible_tiles[tile_coord].type == 'menhir':
                    self.target = Coords(tile_coord[0], tile_coord[1])
                    self.menhir_found = True
                    self.menhir_location = self.target

        if not self.mist_spotted:
            for tile_coord in visible_tiles:
                if "mist" in list(map(lambda x: x.type, visible_tiles[tile_coord].effects)):
                    self.target = self.menhir_location
                    self.mist_spotted = True

        if self.panic_mode <= 0 and self.weapon.name == 'knife':
            self.target = find_closest_weapon(
                self.weapons_knowledge, position, self.closest_weapon[(position.y, position.x)], self.clusters, self.adj, self.menhir_location)
            if self.target == position:
                self.target = self.menhir_location
                return Action.STEP_FORWARD
            self.jitter = 0
        elif self.panic_mode <= 0:
            self.target = self.menhir_location
            self.jitter = 0 if self.touched_by_mist else 10

        bad_neighborhood_factor = 0
        if not self.mist_spotted:
            for i in range(-3, 4):
                for j in range(-3, 4):
                    pos = Coords(x=position.x + i, y=position.y + j)
                    if pos in visible_tiles:
                        if visible_tiles[pos].character is not None:
                            bad_neighborhood_factor += 1
        else:
            for i in range(-2, 3):
                for j in range(-2, 3):
                    pos = Coords(x=position.x + i, y=position.y + j)
                    if pos in visible_tiles:
                        if "mist" in list(map(lambda x: x.type, visible_tiles[pos].effects)):
                            self.touched_by_mist = True

        if bad_neighborhood_factor > 2 and self.panic_mode < 2:
            self.panic_mode = 6
            for _ in range(50):  # Just to avoid while True lol
                rx, ry = np.random.randint(min(self.map_height, self.map_width), size=[2])
                if self.clusters[(ry, rx)]:
                    self.target = Coords(x=rx, y=ry)
                    break

        # Positions in reach
        in_reach = weapons[self.weapon.name].cut_positions(self.terrain, position, self.facing)
        if self.weapon.name != "bow_unloaded":
            for pos in in_reach:
                if pos in visible_tiles and visible_tiles[pos].character is not None:
                    self.latest_states += ["att"]
                    return Action.ATTACK

        if self.weapon.name == "bow_unloaded":
            self.latest_states += ["att"]
            return Action.ATTACK
        available_actions = [x for x in available_actions if x not in [Action.ATTACK]]

        # Rule out stupid moves
        next_block = position + self.facing.value
        if next_block in visible_tiles:
            if visible_tiles[next_block].type in ['sea', 'wall'] or visible_tiles[next_block].character is not None:
                available_actions = [x for x in available_actions if x not in [Action.STEP_FORWARD]]

        distance_from_target = self.target - position
        distance_from_target = distance_from_target.x ** 2 + distance_from_target.y ** 2

        if distance_from_target < self.jitter and self.target == self.menhir_location:
            if Action.STEP_FORWARD in available_actions:
                if np.random.rand() < 0.7:
                    return Action.STEP_FORWARD

            left_ahead = self.target - (position + self.facing.turn_left().value)
            left_ahead = left_ahead.x ** 2 + left_ahead.y ** 2
            right_ahead = self.target - (position + self.facing.turn_right().value)
            right_ahead = right_ahead.x ** 2 + right_ahead.y ** 2

            if left_ahead < right_ahead:
                return Action.TURN_LEFT if np.random.rand() < 0.7 else Action.TURN_RIGHT
            else:
                return Action.TURN_RIGHT if np.random.rand() < 0.7 else Action.TURN_LEFT

        else:
            cluster_path_to_target = find_path(
                self.adj, self.clusters[(position.y, position.x)], self.clusters[(self.target.y, self.target.x)])

            if len(cluster_path_to_target) > 1:
                move = pathfinding_next_move(
                    (position.y, position.x), facing_to_letter[self.facing], cluster_path_to_target[1], self.clusters)
                if move is None:
                    self.panic_mode = 8
                    for _ in range(50):  # Just to avoid while True lol
                        rx, ry = np.random.randint(min(self.map_height, self.map_width), size=[2])
                        if self.clusters[(ry, rx)]:
                            self.target = Coords(x=rx, y=ry)
                            break
                else:
                    available_actions = (
                        ([move] if move in available_actions else [])
                        + ([Action.ATTACK] if Action.ATTACK in available_actions else [])
                    )
            else:
                move = pathfinding_next_move_in_cluster(
                    (position.y, position.x), facing_to_letter[self.facing], (self.target.y, self.target.x), self.clusters)
                if move is None:
                    self.panic_mode = 8
                    for _ in range(50):  # Just to avoid while True lol
                        rx, ry = np.random.randint(min(self.map_height, self.map_width), size=[2])
                        if self.clusters[(ry, rx)]:
                            self.target = Coords(x=rx, y=ry)
                            break
                else:
                    available_actions = (
                        ([move] if move in available_actions else [])
                        + ([Action.ATTACK] if Action.ATTACK in available_actions else [])
                    )

        if len(available_actions) == 0:
            return random.choice([Action.ATTACK, Action.TURN_LEFT])

        return random.choice(available_actions)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.position = None
        self.facing = None
        self.health = None
        self.weapon = None
        self.move_number = 0
        self.menhir_found = False
        self.menhir_location = Coords(16, 16)
        self.closest_weapon = None
        self.mist_spotted = False
        self.panic_mode = 0
        self.touched_by_mist = False
        self.latest_states = []

        self.arena_name = arena_description.name
        self.terrain = arenas.Arena.load(self.arena_name).terrain

        analytics = analyze_map(self.arena_name)

        self.target = Coords(x=analytics['start'][1], y=analytics['start'][0])
        self.menhir_location = self.target
        self.clusters = analytics['clusters']
        self.adj = analytics['adj']
        self.weapons_knowledge = analytics['weapons_knowledge']
        self.map_height = analytics['height']
        self.map_width = analytics['width']

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK


POTENTIAL_CONTROLLERS = [
    Spejson("Spejson"),
]

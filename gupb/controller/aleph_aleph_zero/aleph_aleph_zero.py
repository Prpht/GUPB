import random
from copy import copy

import numpy as np

from gupb import controller
from gupb.controller.aleph_aleph_zero.high_level_strategies.hide_run import HideRun
from gupb.controller.aleph_aleph_zero.high_level_strategies.loot_conquer import LootConquer
from gupb.controller.aleph_aleph_zero.high_level_strategies.loot_hide import LootHide
from gupb.controller.aleph_aleph_zero.shortest_path import build_graph
from gupb.controller.aleph_aleph_zero.strategies.weapon_rush_strategy import weapons_score
from gupb.controller.aleph_aleph_zero.utils import get_knowledge_from_file, get_save_spots, get_height_width_from_file, \
    if_character_to_kill
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model.arenas import FIXED_MENHIRS

from gupb.model.characters import Facing
from gupb.model.coordinates import sub_coords
from gupb.model.tiles import TileDescription


class Knowledge:
    def __init__(self, position = None, visible_tiles = None, facing = None, no_of_champions_alive = 0):
        if visible_tiles is None:
            visible_tiles = dict()
        self.position = position
        self.visible_tiles = visible_tiles
        self.facing = facing
        self.no_of_champions_alive = no_of_champions_alive


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class AlephAlephZeroBot(controller.Controller):
    HLSs = (
        HideRun,
        LootHide
    )

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.mists = set()
        self.epoch = 0

        self.knowledge = Knowledge()

        self.menhir_seen = False
        self.menhir_pos_updated = False

        self.life_points = 8
        self.killed_now = False

        self.map_knowledge_cache = {}
        self.save_spots_cache = {}

        self.rewards_dict = dict()


    def __eq__(self, other: object) -> bool:
        if isinstance(other, AlephAlephZeroBot):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def _check_tile_mist_free(self, knowledge: characters.ChampionKnowledge, coord):
        if coord in self.knowledge.visible_tiles:
            for effect_desc in self.knowledge.visible_tiles[coord].effects:
                if effect_desc.type == "mist":
                    return False
            return True
        return False  # if we don't know, assume it's mist

    def _get_visible_mist(self, knowledge):
        for coord, tile_desc in knowledge.visible_tiles.items():
            if coord in self.mists:
                self.mists.remove(coord)
            for effect_desc in tile_desc.effects:
                if effect_desc.type == "mist":
                    for i in (-1, 1):
                        adj_coord_x = coordinates.add_coords(coord, coordinates.Coords(i, 0))
                        adj_coord_y = coordinates.add_coords(coord, coordinates.Coords(0, i))
                        if self._check_tile_mist_free(knowledge, adj_coord_x) or self._check_tile_mist_free(knowledge,
                                                                                                            adj_coord_y):
                            self.mists.add(coord)

    def _calculate_menhir_center(self):
        from scipy import optimize

        mist_x = np.array([coord[0] for coord in self.mists])
        mist_y = np.array([coord[1] for coord in self.mists])

        x_m = np.mean(mist_x)
        y_m = np.mean(mist_y)

        # adapted from https://scipy-cookbook.readthedocs.io/items/Least_Squares_Circle.html

        def calc_R(xc, yc):
            """ calculate the distance of each 2D points from the center (xc, yc) """
            return np.sqrt((mist_x - xc) ** 2 + (mist_y - yc) ** 2)

        def f_2(c):
            """ calculate the algebraic distance between the data points and the mean circle centered at c=(xc, yc) """
            Ri = calc_R(*c)
            return Ri - Ri.mean()

        center_estimate = x_m, y_m
        center_2, ier = optimize.leastsq(f_2, center_estimate)

        xc_2, yc_2 = center_2
        Ri_2 = calc_R(*center_2)
        R_2 = Ri_2.mean()
        residu_2 = sum((Ri_2 - R_2) ** 2)
        return coordinates.Coords(round(xc_2), round(yc_2))

    def _calculate_facing(self, new_knowledge):  # afaik, we have to calculate this
        facing_vals = {f.value: f for f in Facing}
        for coord in new_knowledge.visible_tiles:
            if sub_coords(coord, new_knowledge.position) in facing_vals:
                return facing_vals[sub_coords(coord, new_knowledge.position)]

    def _update_knowledge(self, new_knowledge):

        #forget all of the old character info
        to_be_updated = dict()
        for coords, tile_desc in self.knowledge.visible_tiles.items():
            if tile_desc.character is not None:
                to_be_updated[coords] = TileDescription(tile_desc[0],tile_desc[1],None,[])
        for coords, tile_desc in to_be_updated.items():
            self.knowledge.visible_tiles[coords] = tile_desc

        self.knowledge.position = new_knowledge.position
        for coords, tile_desc in new_knowledge.visible_tiles.items():
            self.knowledge.visible_tiles[coords] = tile_desc
        self.knowledge.facing = self._calculate_facing(new_knowledge)

        for coords, tile_desc in new_knowledge.visible_tiles.items():
            if tile_desc.type == "menhir":
                self.menhir_position = coords
                self.menhir_seen = True
                self.menhir_pos_updated = True
        if new_knowledge.visible_tiles[self.knowledge.position].character.health != self.life_points:
            self.killed_now = True
            self.life_points = new_knowledge.visible_tiles[self.knowledge.position].character.health

    def _convert_knowledge(self, knowledge):
        return Knowledge(knowledge.position, copy(knowledge.visible_tiles), knowledge.visible_tiles[knowledge.position].character.facing, knowledge.no_of_champions_alive)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        knowledge = self._convert_knowledge(knowledge)  # change to our api
        self._update_knowledge(knowledge)
        self.epoch += 1
        graph = self.graph

        self._get_visible_mist(knowledge)
        if len(self.mists)>3 and (not self.menhir_seen):
            self.menhir_pos_updated = True
            try:
                self.menhir_position = self._calculate_menhir_center()
            except:
                pass  # shouldn't go wrong, but just in case, do nothing


        if if_character_to_kill(self.knowledge):
            return characters.Action.ATTACK

        return self.high_level_strategy.decide()


    def praise(self, score: int) -> None:
        n = self.rewards_dict[self.map_name][type(self.high_level_strategy)]["n"]
        self.rewards_dict[self.map_name][type(self.high_level_strategy)]["reward_estimate"] = score/(n+1)+(n*self.rewards_dict[self.map_name][type(self.high_level_strategy)]["reward_estimate"])/(n+1)
        self.rewards_dict[self.map_name][type(self.high_level_strategy)]["n"] = n+1

    def _choose_hls(self, map_name, epsilon=0.15):
        if random.uniform(0,1)<epsilon:  # take random
            return random.choice(AlephAlephZeroBot.HLSs)(self)
        else:  # take argmax
            max_estimate = 0
            best_hls = None
            for hls in AlephAlephZeroBot.HLSs:
                general_estimate = sum(self.rewards_dict[map_name][hls]["reward_estimate"] for map_name in self.rewards_dict.keys())
                map_specific_estimate = self.rewards_dict[self.map_name][hls]["reward_estimate"]
                estimate = (general_estimate + map_specific_estimate)/2
                if estimate>=max_estimate:
                    best_hls = hls
                    max_estimate = estimate
            return best_hls(self)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        if arena_description.name in self.map_knowledge_cache.keys():
            self.map_knowledge = self.map_knowledge_cache[arena_description.name]
        else:
            self.map_knowledge = get_knowledge_from_file(arena_description.name)
            self.map_knowledge_cache[arena_description.name] = self.map_knowledge

        if arena_description.name in self.save_spots_cache.keys():
            self.save_spots = self.save_spots_cache[arena_description.name]
        else:
            self.save_spots = get_save_spots(self.map_knowledge)
            self.save_spots_cache[arena_description.name] = self.save_spots

        self.graph = build_graph(self.map_knowledge)

        if arena_description.name in FIXED_MENHIRS.keys():
            self.menhir_position = FIXED_MENHIRS[arena_description.name]
            self.menhir_seen = True
            self.menhir_pos_updated = True

        self.map_name = arena_description.name
        if self.map_name not in self.rewards_dict.keys():
            self.rewards_dict[self.map_name] = {hls:{"reward_estimate": 0, "n": 0} for hls in AlephAlephZeroBot.HLSs}

        self.high_level_strategy = self._choose_hls(arena_description.name)

        self.height_width = get_height_width_from_file(arena_description.name)

        self.epoch = 0
        self._first_estimate = False
        self.mists = set()
        self.knowledge = Knowledge()
        self.menhir_position = None
        self.menhir_seen = False
        self.menhir_pos_updated = False

        self.life_points = 8
        self.killed_now = False

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.LIME

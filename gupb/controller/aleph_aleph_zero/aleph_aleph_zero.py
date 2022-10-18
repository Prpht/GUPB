import random
from copy import copy
from time import sleep

import numpy as np
from typing import List

from gupb import controller
from gupb.controller.aleph_aleph_zero.guarding_strategy import GuardingStrategy
from gupb.controller.aleph_aleph_zero.one_action_strategys import AttackStrategy, RunStrategy
from gupb.controller.aleph_aleph_zero.menhir_rush_strategy import MenhirRushStrategy
from gupb.controller.aleph_aleph_zero.scouting_strategy import ScoutingStrategy
from gupb.controller.aleph_aleph_zero.shortest_path import build_graph, find_shortest_path, get_closest_points
from gupb.controller.aleph_aleph_zero.strategy import StrategyPriority
from gupb.controller.aleph_aleph_zero.strategy import StrategyPriority
from gupb.controller.aleph_aleph_zero.travel_strategy import TravelStrategy
from gupb.controller.aleph_aleph_zero.utils import if_character_to_kill, get_knowledge_from_file, get_save_spots
from gupb.controller.aleph_aleph_zero.weapon_rush_strategy import WeaponRushStrategy
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model.arenas import FIXED_MENHIRS

from gupb.model.characters import Facing
from gupb.model.coordinates import sub_coords, Coords


class Knowledge:
    def __init__(self, position = None, visible_tiles = None, facing = None, no_of_champions_alive = 0):
        if visible_tiles is None:
            visible_tiles = dict()
        self.position = position
        self.visible_tiles = visible_tiles
        self.facing = facing
        self.no_of_champions_alive = no_of_champions_alive

EPOCH_TO_BE_IN_MELCHIR = 150

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class AlephAlephZeroBot(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.mists = set()
        self.epoch = 0

        self.strategy = ScoutingStrategy()

        self.knowledge = Knowledge()

        self.menhir_seen = False
        self.menhir_pos_updated = False

        self.life_points = 8
        self.killed_now = False

        self.map_knowledge_cache = {}
        self.save_spots_cache = {}

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

        if self.menhir_pos_updated or self.menhir_seen:
            curr = graph[(knowledge.position, self.knowledge.facing)]
            shortest_path = find_shortest_path(curr, self.menhir_position)
            if (not self.menhir_seen) or shortest_path is None or self.epoch + len(shortest_path) > EPOCH_TO_BE_IN_MELCHIR:
                self.menhir_pos_updated = False
                self.strategy = self.strategy.get_more_important(MenhirRushStrategy(self.menhir_position, priority=StrategyPriority.TIME_SENSITIVE))

            elif self.menhir_seen: #widzielismy juz menhira, znamy do niego droge i mamy duzo czasu
                if self.knowledge.visible_tiles[knowledge.position].character.weapon.name=="knife":
                    self.strategy = self.strategy.get_more_important(WeaponRushStrategy(StrategyPriority.PURPOSEFUL))
                else:
                    self.strategy = self.strategy.get_more_important(
                        TravelStrategy(
                            get_closest_points(self.save_spots, self.graph, graph[knowledge.position,knowledge.facing])[0],
                            GuardingStrategy(priority=StrategyPriority.PURPOSEFUL),
                            priority=StrategyPriority.PURPOSEFUL
                        ))

        if if_character_to_kill(knowledge):
            self.strategy = self.strategy.get_more_important(AttackStrategy(priority=StrategyPriority.AGGRESSIVE))

        if self.killed_now:
            self.strategy = self.strategy.get_more_important(RunStrategy(self.strategy, priority=StrategyPriority.CRITICAL))
            self.killed_now = False

        while True:
            action, self.strategy = self.strategy.decide_and_proceed(self.knowledge, graph=graph, map_knowlege=self.map_knowledge)
            if action is not None:
                return action

    def praise(self, score: int) -> None:
        pass

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

        self.strategy = ScoutingStrategy()
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

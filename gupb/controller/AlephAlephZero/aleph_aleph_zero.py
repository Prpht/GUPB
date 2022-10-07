import random
from time import sleep

import numpy as np
from typing import List

from gupb import controller
from gupb.controller.AlephAlephZero.attack_strategy import AttackStrategy
from gupb.controller.AlephAlephZero.menhir_rush_strategy import MenhirRushStrategy
from gupb.controller.AlephAlephZero.scouting_strategy import ScoutingStrategy
from gupb.controller.AlephAlephZero.shortest_path import build_graph, find_shortest_path
from gupb.controller.AlephAlephZero.utils import if_character_to_kill
from gupb.controller.AlephAlephZero.weapon_rush_strategy import WeaponRushStrategy
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates


from gupb.model.characters import Facing
from gupb.model.coordinates import sub_coords


class Knowledge:
    def __init__(self):
        self.position = None
        self.visible_tiles = dict()
        self.facing = None

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

        self.menhir_position = None
        self.menhir_seen = False
        self.menhir_pos_updated = False

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

    def _get_visible_mist(self, knowledge: characters.ChampionKnowledge):
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

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self._update_knowledge(knowledge)
        self.epoch += 1
        graph = build_graph(self.knowledge)

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
                self.strategy = MenhirRushStrategy(self.menhir_position)

            elif self.menhir_seen: #widzielismy juz menhira, znamy do niego droge i mamy duzo czasu
                self.strategy = WeaponRushStrategy()

        if if_character_to_kill(knowledge):
            self.strategy = AttackStrategy()

        while True:
            action, self.strategy = self.strategy.decide_and_proceed(self.knowledge, graph=graph)
            if action is not None:
                return action

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.strategy = ScoutingStrategy()
        self.epoch = 0
        self._first_estimate = False
        self.mists = set()
        self.knowledge = Knowledge()
        self.menhir_position = None
        self.menhir_seen = False
        self.menhir_pos_updated = False

    @property
    def name(self) -> str:
        return f'\u2135\u2135\u2080:{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.LIME

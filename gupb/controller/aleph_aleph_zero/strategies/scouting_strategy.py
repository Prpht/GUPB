import random
from enum import Enum

from gupb.controller.aleph_aleph_zero.strategies.scanning_strategy import ScanningStrategy
from gupb.controller.aleph_aleph_zero.shortest_path import build_graph, get_reachable, find_shortest_path, \
    find_closest_orientation
from gupb.controller.aleph_aleph_zero.strategies.strategy import Strategy
from gupb.controller.aleph_aleph_zero.strategies.travel_strategy import TravelStrategy
from gupb.controller.aleph_aleph_zero.utils import get_edge_of_vision


class ScoutingPhase(Enum):
    SCANNING = 0,
    TRAVELLING = 1


class ScoutingStrategy(Strategy):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.curr_target = None
        self.phase = ScoutingPhase.TRAVELLING

    def set_new_target(self, knowledge, graph):
        reachable = get_reachable(graph[(knowledge.position, knowledge.facing)])
        edge_of_vision = get_edge_of_vision(knowledge)

        potential_targets = edge_of_vision.intersection(reachable)
        potential_targets_ord = list(potential_targets)

        shortest_paths = find_shortest_path(graph[(knowledge.position, knowledge.facing)], end=None)  # find all

        i = 0
        while self.phase == ScoutingPhase.TRAVELLING:
            self.curr_target = random.choices(potential_targets_ord,
                                              weights=[
                                                  1 / (1 + find_closest_orientation(shortest_paths, graph, coords)[1])
                                                  for coords in potential_targets_ord])[0]
            if knowledge.visible_tiles[self.curr_target].type in {"land", "menhir"} \
                    and knowledge.position != self.curr_target:
                break
            i += 1
            if i > 100:
                self.phase = ScoutingPhase.SCANNING  # can't find a valid target - start with a scan

    def decide_and_proceed(self, knowledge, graph=None, **kwargs):
        if graph is None:
            graph = build_graph(knowledge)
        if self.phase == ScoutingPhase.TRAVELLING:
            if self.curr_target is None or knowledge.position == self.curr_target:
                self.set_new_target(knowledge, graph)
            if self.phase == ScoutingPhase.TRAVELLING:
                self.phase = ScoutingPhase.SCANNING
                return None, TravelStrategy(self.curr_target, self)
        if self.phase == ScoutingPhase.SCANNING:
            self.phase = ScoutingPhase.TRAVELLING
            return None, ScanningStrategy(self)

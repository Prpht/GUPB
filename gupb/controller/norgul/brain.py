from gupb.controller.norgul.memory import Memory
from gupb.controller.norgul.movement import MotorCortex
from gupb.controller.norgul.navigation import Navigator
from gupb.controller.norgul.exploration import Explorator
from gupb.controller.norgul.collection import Collector
from gupb.controller.norgul.combat import CombatEngine
from gupb.controller.norgul.config import COMBAT_THRESHOLD
from gupb.controller.norgul.misc import max_dist

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates

import numpy as np

from math import sqrt
from itertools import product


# --------------------
# Norgul's brain class
# --------------------

# This class menages all the submodules (navigation, exploration, etc.) and produces a final decision
# - NOTE: all complex decision making should be put here (not in the NorgulController!)
class Brain:

    def __init__(self, memory: Memory):
        # Memory connection
        self.memory = memory

        # Brain components
        self.navigator = Navigator(self.memory)
        self.motor = MotorCortex(self.memory)
        self.explorator = Explorator(self.memory)
        self.collector = Collector(self.memory)
        self.combat = CombatEngine(self.memory, self.navigator, self.motor)

        # Hyperparameters
        # TODO: move into separate config file
        self.radius = 4
        self.mist_vec_weight = 50
        self.enemy_vec_weight = 5
    
    # -------------------------------------
    # Norgul's brain - main decision making
    # -------------------------------------

    def decide(self) -> characters.Action | None:
        target = self.collector.best_pickup()

        if target is None or not self.navigator.find_path(self.memory.pos, target)[1]:
            # Try to fight someone
            avoid_mnist = True
            if self.memory.arena.obelisk_pos is not None and max_dist(self.memory.pos, self.memory.arena.obelisk_pos) < 8:
                avoid_mnist = False
            easy_target, chances = self.combat.find_target(avoid_mist=avoid_mnist)

            if easy_target is not None:
                if not isinstance(easy_target, coordinates.Coords):
                    easy_target = coordinates.Coords(easy_target[0], easy_target[1])

                if chances > COMBAT_THRESHOLD:
                    # print("Fighting:", easy_target)
                    action = self.combat.fight_control(easy_target, safe_mode=False)
                    return action

            # If you can't fight, then try to explore instead
            target = self.explorator.pick_area()

            # print("Exploring:", target)
        else:
            if target == self.memory.pos:
                target = self.memory.pos + characters.Facing.random().value      # TODO: This is a total shit and must be changed
                return self.move_to_target(target, fast=True)
            # print("Collecting:", target)
        
        if target is None or self.mist_close():
            target = self.memory.arena.obelisk_pos

        return self.move_to_target(target, fast=False)

    # TODO: replace with better code
    def move_to_target(norgul, target, fast=False):
        """If Fast -> do not waste moves to turn"""

        next_sq, _ = norgul.navigator.find_path(norgul.memory.pos, target)

        if norgul.memory.pos != next_sq:
            return norgul.motor.move_to(next_sq, quick=fast)
        
        elif norgul.memory.arena[norgul.memory.pos + norgul.memory.dir.value].character is not None:
            if norgul.memory.arena[norgul.memory.pos + norgul.memory.dir.value].type == "forest":
                return None
            return characters.Action.ATTACK
    
    def mist_close(self) -> bool:
        for i in range(-2, 3):
            for j in range(-2, 3):
                tile = coordinates.Coords(self.memory.pos[0] + i, self.memory.pos[1] + j)
                if tile in self.memory.arena and ("mist",) in self.memory.arena[tile].effects:
                    return True
        
        return False
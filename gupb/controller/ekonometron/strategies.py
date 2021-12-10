import random

from typing import Tuple, Optional, Dict

from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription


class Strategy:
    def __init__(self, controller, name):
        self.controller = controller
        self.name = name
        self.value = 0.0
        self.n = 0

    def proceed(self, knowledge):
        pass

    def update_value(self, reward):
        self.n += 1
        self.value += (reward - self.value) / self.n


class TryingMyBest(Strategy):
    def __init__(self, controller):
        super().__init__(controller, "trying_my_best")

    def proceed(self, knowledge):
        return characters.Action.TURN_LEFT


class LetsHide(Strategy):
    def __init__(self, controller):
        super().__init__(controller, "lets_hide")

    def proceed(self, knowledge):
        return characters.Action.TURN_LEFT


class KillThemAll(Strategy):
    def __init__(self, controller):
        super().__init__(controller, "kill_them_all")

    def proceed(self, knowledge):
        return characters.Action.TURN_LEFT

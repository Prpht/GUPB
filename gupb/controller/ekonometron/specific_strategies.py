import random

from typing import Tuple, Optional, Dict

from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription
from .base_strategy import Strategy


class TryingMyBest(Strategy):
    """ Default strategy; bot wanders over map without a goal; picks up potential weapons and attacks enemies on sight;
     if notices a mist, it goes to the menhir (if it found it earlier) """
    def __init__(self, controller):
        super().__init__(controller, "trying_my_best")

    def proceed(self, knowledge):
        return characters.Action.TURN_LEFT


class LetsHide(Strategy):
    """ Defensive strategy; bot explores the map and tries to avoid any conflict; it likes to hide in specific places;
     if it has no choice, it attacks; goes to menhir when the mist is noticed """
    def __init__(self, controller):
        super().__init__(controller, "lets_hide")

    def proceed(self, knowledge):
        return characters.Action.TURN_LEFT


class KillThemAll(Strategy):
    """ Offensive strategy; bot tries to find the best weapon and then - it goes after enemies to take them down;
     it is not concerned about finding the menhir unless the mist comes too close """
    def __init__(self, controller):
        super().__init__(controller, "kill_them_all")

    def proceed(self, knowledge):
        return characters.Action.TURN_LEFT

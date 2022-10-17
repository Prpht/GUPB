from collections import defaultdict
from queue import Queue
import random
from typing import List

import numpy as np

from gupb import controller
from gupb.controller.lord_icon.distance import Point2d, dist, find_path
from gupb.controller.lord_icon.knowledge import Knowledge
from gupb.controller.lord_icon.move import MoveController
from gupb.controller.lord_icon.strategy import StrategyController
from gupb.model import arenas, characters, coordinates
from gupb.model.arenas import Arena
from gupb.model.weapons import WeaponDescription

mapper = defaultdict(lambda: 1)
mapper["land"] = 0
mapper["menhir"] = 0

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class LordIcon(controller.Controller):
    def __init__(self, first_name: str) -> None:
        self.first_name: str = first_name

        # Movement
        self.current_direction = None

        # Knowledge
        self.knowledge = Knowledge()

        # Weapons

    def __eq__(self, other: object) -> bool:
        if isinstance(other, LordIcon):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(
        self, knowledge: characters.ChampionKnowledge
    ) -> characters.Action:
        self.knowledge.update(knowledge)

        action = StrategyController.decide(self.knowledge)

        # if action:
        #     return action

        return random.choice(POSSIBLE_ACTIONS)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.knowledge.reset(arena_description.name)

    @property
    def name(self) -> str:
        return f"Marek łowca wiertarek {self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW

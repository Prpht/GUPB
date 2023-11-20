from gupb.controller.r2d2.knowledge import R2D2Knowledge
from gupb.controller.r2d2.navigation import get_move_towards_target
from gupb.controller.r2d2.r2d2_helpers import walking_distance
from gupb.controller.r2d2.r2d2_state_machine import R2D2StateMachine
from gupb.controller.r2d2.strategies import Strategy
from gupb.model.characters import Action
import numpy as np 
from gupb.controller.r2d2.utils import *


class PotionPicker(Strategy):
    def __init__(self):
        pass

    def decide(self, knowledge: R2D2Knowledge, state_machine: R2D2StateMachine) -> Action:
        nearby_potions = get_nearby_potions(knowledge)
        # get closest potion
        y, x = min(nearby_potions, key=lambda x: walking_distance(knowledge.champion_knowledge.position, x, knowledge.world_state.matrix_walkable))
        return get_move_towards_target(knowledge.champion_knowledge.position, Coords(x, y), knowledge, allow_moonwalk=True)[0]


def get_nearby_potions(knowledge: R2D2Knowledge) -> list[tuple[int, int]]:
    xs, ys = np.where(knowledge.world_state.matrix == tiles_mapping["potion"])
    # get potions that are within 3 tiles of the champion
    nearby_potions = [(x, y) for x, y in zip(xs, ys) if walking_distance(knowledge.champion_knowledge.position, (x, y), knowledge.world_state.matrix_walkable) <= 3]
    return nearby_potions



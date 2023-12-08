import numpy as np 
from skg import nsphere_fit

from gupb.controller.r2d2.knowledge import R2D2Knowledge
from gupb.controller.r2d2.navigation import get_move_towards_target
from gupb.controller.r2d2.r2d2_helpers import walking_distance
from gupb.controller.r2d2.r2d2_state_machine import R2D2StateMachine
from gupb.controller.r2d2.strategies import Strategy
from gupb.model.characters import Action
from gupb.controller.r2d2.utils import *


class MistAvoider(Strategy):
    def __init__(self):
        pass

    def decide(self, knowledge: R2D2Knowledge) -> Action:

        # Get the menhir destination
        destination_coords = get_menhir_destination(knowledge)

        # Return the action towards the destination
        return get_move_towards_target(knowledge.champion_knowledge.position, destination_coords, knowledge, allow_moonwalk=True)[0]
        

def get_menhir_destination(knowledge: R2D2Knowledge) -> Coords:
    
    # If the menhir is already found, return its position
    if knowledge.world_state.menhir_position:
        return knowledge.world_state.menhir_position
    
    # If the menhir is not found, return the estimated position
    mist_boundary = get_mist_boundary(knowledge)

    # - If the mist boundary is empty, return the previous estimation
    if len(mist_boundary) == 0:
        return knowledge.world_state.menhir_estimated_position
    
    # - If the mist boundary is not empty, estimate the menhir position and return it
    _, (cx, cy) = nsphere_fit(mist_boundary)
    cx, cy = int(round(cx)), int(round(cy))
    cx, cy = max(1, cx), max(1, cy)
    cx, cy = min(cx, knowledge.world_state.arena_shape[0] - 2), min(cy, knowledge.world_state.arena_shape[1] - 2)
    knowledge.world_state.menhir_estimated_position = Coords(cy, cx)

    return knowledge.world_state.menhir_estimated_position

def get_mist_boundary(knowledge: R2D2Knowledge) -> list[list[int]]:

    # If there is no visible mist, return empty boundary
    if not knowledge.world_state.mist_present:
        return []
    
    # Calculate the boundary
    boundary = []
    delta_x, delta_y = [0, 0, 1, 1], [0, 1, 0, 1]
    # - based on the visible_tiles dict
    for coords, tile_description in knowledge.champion_knowledge.visible_tiles.items():
        if "mist" in list(map(lambda x: x.type, tile_description.effects)):
            for dx, dy in zip(delta_x, delta_y):
                try:
                    y, x = coords[0] + dx, coords[1] + dy
                    tile = knowledge.champion_knowledge.visible_tiles[Coords(y ,x)]
                    if "mist" not in list(map(lambda x: x.type, tile.effects)):
                        boundary.append([x, y])
                except KeyError:
                    pass

    # - based on the world_state.matrix - have some garbadge tiles, works not that well
    # for x in range(knowledge.world_state.arena_shape[0]):
    #     for y in range(knowledge.world_state.arena_shape[1]):

    #         # Check only NON MIST tiles
    #         if knowledge.world_state.matrix[x, y] != tiles_mapping["mist"]:
    #             for dx, dy in zip(delta_x, delta_y):

    #                 # If any of the neighbours is mist, add the tile to the boundary
    #                 try:
    #                     if knowledge.world_state.matrix[x + dx, y + dy] == tiles_mapping["mist"]:
    #                         boundary.append([x, y])
    #                 except IndexError:
    #                     pass
    
    # Return the boundary
    return boundary
    
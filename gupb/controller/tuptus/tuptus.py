import random
from xmlrpc.client import Boolean

from gupb import controller
from gupb.model import arenas
from gupb.model import characters, effects
from gupb.model import coordinates

from typing import Optional, List

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class TuptusController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.facing: Optional[characters.Facing] = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, TuptusController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        
        # if not self.facing:
        self.find_facing_direction(knowledge.position, knowledge.visible_tiles.keys())
        # print(knowledge.visible_tiles.keys())
        # for key in knowledge.visible_tiles.keys():
            # print(f"{key} ==> {type(key)}")
        # for key, val in knowledge.visible_tiles.items():
        #     print(f"{key} ==> {val}")
        # print("\n\n")
        # print(knowledge.position)
        next_block_position = knowledge.position + self.facing.value
        next_block = knowledge.visible_tiles[next_block_position]
        # print(f"{next_block_position} ==> {next_block}")
        
        if next_block.type in ["wall", "sea"]: 
            choice = POSSIBLE_ACTIONS[random.randint(0,1)]
        elif self.is_mist(knowledge.visible_tiles):
            choice = POSSIBLE_ACTIONS[random.randint(0,1)]
        elif next_block.character:
            choice = POSSIBLE_ACTIONS[3]
        else:
            choice = POSSIBLE_ACTIONS[2]
        
        # print(f"Chosen action ==> {choice}")
        return choice

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.facing = None

    def find_facing_direction(self, position, visible_tiles_positions) -> None:
        facing_dct = {(0, -1): characters.Facing.UP,
                      (0, 1): characters.Facing.DOWN,
                      (-1, 0): characters.Facing.LEFT,
                      (1, 0): characters.Facing.RIGHT}

        x_pos, y_pos = position

        for x_tile, y_tile in visible_tiles_positions:
            difference = (x_tile - x_pos, y_tile - y_pos)

            if difference in facing_dct.keys():
                self.facing = facing_dct[difference]
                break
    
    def is_mist(self, visible_tiles) -> Boolean:
        for tile in visible_tiles.values():
            if effects.EffectDescription(type='mist') in tile.effects:
                return True
        return False

    @property
    def name(self) -> str:
        return f'RandomController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREEN


POTENTIAL_CONTROLLERS = [
    TuptusController("CiCik")
]
from gupb.model import arenas
from gupb.model import characters
from typing import Dict
from enum import Enum
import operator

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotElkaController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.directions_info: Dict[characters.Facing, int] = {characters.Facing.UP: 0, characters.Facing.LEFT: 0, characters.Facing.RIGHT: 0, characters.Facing.DOWN: 0}
        self.counter: int = 0
        self.moves_queue = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotElkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    def get_moves(self, starting_position, desired_position):
        


    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.moves_queue: 
            return self.moves_queue.pop(0)
        champion_facing = next((visible_tile.character.facing 
        for visible_tile in knowledge.visible_tiles.values() 
        if visible_tile.character and visible_tile.character.controller_name == self.name),
        None)
        self.counter += 1
        self.directions_info[champion_facing] = len([visible_tile for visible_tile in knowledge.visible_tiles.values() if visible_tile.type == 'land'])
        if self.counter == 4:
            self.counter = 0
            direction = max(self.directions_info, key=operator.itemgetter(1))[0]
            if (direction == champion_facing) return characters.Action.STEP_FORWARD
            moves = self.get_moves(champion_facing, direction)
            first_move = moves.pop(0)
            self.moves_queue += moves
            return first_move
       
        return characters.Action.TURN_LEFT

    @property
    def name(self) -> str:
        return f'BotElka{self.first_name}'


POTENTIAL_CONTROLLERS = [
    BotElkaController("")
]

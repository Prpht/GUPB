import random
from typing import Dict
from xmlrpc.client import Boolean
from math import sqrt

from gupb import controller

from gupb.model import arenas, effects, tiles
from gupb.model import characters
from gupb.model import coordinates
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]
ArenaDescription = Dict[coordinates.Coords, tiles.TileDescription]

class CynamonkaController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.weapon = Knife
        self.champion = None
        self.position = None
        self.facing = None
        self.menhir_position = None
        self.discovered_arena: ArenaDescription = dict()
        self.move_count = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CynamonkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.move_count+=1
        self.update_discovered_arena(knowledge.visible_tiles)
        self.position = knowledge.position
        self.facing = knowledge.visible_tiles[self.position].character.facing

        next_position = self.position + self.facing.value
        if self.discovered_arena[next_position].character:
            if self.discovered_arena[next_position].character.health < self.discovered_arena[self.position].character.health:
                return POSSIBLE_ACTIONS[3]
            else:
                return random.choice(POSSIBLE_ACTIONS[:2])
        if self.menhir_position:
            if (distance(next_position, self.menhir_position) < distance(self.position, self.menhir_position)) and self.can_i_move_forward():
                return POSSIBLE_ACTIONS[2]
        if self.can_i_move_forward():
            return random.choices(POSSIBLE_ACTIONS[:3], [1,1,8], k=1)[0]
        else:
            return random.choice(POSSIBLE_ACTIONS[:2])

    def can_i_move_forward(self):
        next_position = self.position + self.facing.value
        return self.discovered_arena[next_position].type != 'sea' and self.discovered_arena[next_position].type != 'wall'
            
    def update_discovered_arena(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, description in visible_tiles.items():
            self.discovered_arena[coords] = description
            if not self.menhir_position and self.is_menhir(coords):
                self.menhir_position = coords

    def is_menhir(self, coords: coordinates.Coords) -> Boolean:
        return self.discovered_arena[coords].type == 'menhir'

    # def is_mist(self, visible_tiles) -> Boolean:
    #     for tile in visible_tiles.values():
    #         if effects.EffectDescription(type='mist') in tile.effects:
    #             return True
    #     return False


    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.weapon = Knife
        self.champion = None
        self.position = None
        self.facing = None
        self.discovered_arena: ArenaDescription = dict()
        self.menhir_position = None
        self.move_count = 0
        self.target = Coords(25,25)

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK

def distance(coords, other_coords):
    return sqrt((coords[0] - other_coords[0]) ** 2 + (coords[1] - other_coords[1]) ** 2)




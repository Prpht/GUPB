import random
from typing import Dict
from xmlrpc.client import Boolean

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
TerrainDescription = Dict[coordinates.Coords, tiles.TileDescription]

# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class CynamonkaController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.weapon = Knife
        self.champion = None
        self.position = None

        self.menhir_coords = None
        self.discovered_arena: TerrainDescription = dict()
        self.target = Coords(25, 25)
        self.move_count = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CynamonkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self._update_discovered_terrain(knowledge.visible_tiles)
        self.position = knowledge.position
        self.facing = knowledge.visible_tiles[self.position].character.facing
        visible_tiles = knowledge.visible_tiles

        next_position = self.position + self.facing.value
        if self.discovered_arena[next_position].character:
            if self.discovered_arena[next_position].character.health < self.discovered_arena[self.position].character.health:
                return POSSIBLE_ACTIONS[3]
            else:
                return random.choice(POSSIBLE_ACTIONS[:2])
        if self.is_mist(knowledge.visible_tiles):
            return random.choice(POSSIBLE_ACTIONS[:2])
        else: pass

        if self.discovered_arena[next_position].type != 'sea' and self.discovered_arena[next_position].type != 'wall':
            return random.choices(POSSIBLE_ACTIONS[:3], [1,1,8], k=1)[0]
        else:
            return random.choice(POSSIBLE_ACTIONS[:2])

        
    def _update_discovered_terrain(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, description in visible_tiles.items():
            self.discovered_arena[coords] = description
            # o chuj chodzi
            if not self.menhir_coords and self.check_menhir(coords):
                self.menhir_coords = coords

    def check_menhir(self, coords: coordinates.Coords):
        return self.discovered_arena[coords].type == 'menhir'

    def is_mist(self, visible_tiles) -> Boolean:
        for tile in visible_tiles.values():
            if effects.EffectDescription(type='mist') in tile.effects:
                return True
        return False


    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.weapon = Knife
        self.champion = None
        self.position = None
        self.facing = None
        self.discovered_arena: TerrainDescription = dict()
        self.menhir_coords = None
        self.move_count = 0
        self.target = Coords(25, 25)

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK




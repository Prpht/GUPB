import random

from typing import Dict

from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.arenas import Terrain, terrain_size
from gupb.model.characters import ChampionDescription

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


def tile_map(tile):
    if not tile:
        return 1
    return {

    }.get(tile, 1)


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class ShallowMind:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.menhir_position: coordinates.Coords = None
        self.terrain: Dict[coordinates.Coords, tiles.TileDescription] = dict()
        self.prev_champion: ChampionDescription = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, ShallowMind):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def __get_champion(self, knowledge: characters.ChampionKnowledge) -> ChampionDescription:
        return self.terrain.get(knowledge.position).character

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.menhir_position = arena_description.menhir_position
        arena = arenas.Arena.load(arena_description.name)
        if arena:
            self.terrain = {k: v.description() for k, v in arena.terrain.items()}
        else:
            self.terrain = dict()
        pass

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.terrain = {**self.terrain, **knowledge.visible_tiles}
        champ = self.__get_champion(knowledge)
        # todo write code
        fields = sorted(self.terrain.items())
        x, y = terrain_size(self.terrain)
        map = {k: v for k, v in sorted(self.terrain.items())}

        self.prev_champion = champ
        return random.choice(POSSIBLE_ACTIONS)

    @property
    def name(self) -> str:
        return f'ShallowMindController{self.first_name}'


POTENTIAL_CONTROLLERS = [
    ShallowMind('test'),
]

import random
from typing import Dict
from math import sqrt
from gupb import controller
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.characters import CHAMPION_STARTING_HP
from gupb.model.weapons import Knife

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

MOVE = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD
]

TURN = [characters.Action.TURN_LEFT,
        characters.Action.TURN_RIGHT]

TerrainDescription = Dict[coordinates.Coords, tiles.TileDescription]


class IntercontinentalBajers(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.weapon = Knife
        self.champion = None
        self.position = None
        self.discovered_arena: TerrainDescription = dict()
        self.menhir_coords = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, IntercontinentalBajers):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self._update_discovered_terrain(knowledge.visible_tiles)
        self.position = knowledge.position
        self.champion = knowledge.visible_tiles[knowledge.position].character

        if self.is_enemy_in_front_of() and self.champion.health >= 0.3 * CHAMPION_STARTING_HP:
            return characters.Action.ATTACK

        if self.menhir_coords:
            coords_after_step_forward = self.position + self.champion.facing.value
            if distance(coords_after_step_forward, self.menhir_coords) < distance(self.position,
                                                                                  self.menhir_coords) and self.is_available_step_forward():
                return characters.Action.STEP_FORWARD
            else:
                return random.choice(TURN)
        if self.is_available_step_forward():
            return random.choices(MOVE, weights=[1, 1, 8], k=1)[0]

        return random.choice(TURN)

    def _update_discovered_terrain(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]):
        for coords, description in visible_tiles.items():
            self.discovered_arena[coords] = description
            if not self.menhir_coords and self.check_menhir(coords):
                self.menhir_coords = coords

    def is_available_step_forward(self):
        next_position_coords = self.position + self.champion.facing.value
        return self.discovered_arena[next_position_coords].type != 'wall' and self.discovered_arena[
            next_position_coords].type != 'sea'

    def is_enemy_in_front_of(self):
        front_coords = self.position + self.champion.facing.value
        return self.discovered_arena[front_coords].character

    def check_menhir(self, coords: coordinates.Coords):
        return self.discovered_arena[coords].type == 'menhir'

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.weapon = Knife
        self.champion = None
        self.position = None
        self.discovered_arena: TerrainDescription = dict()
        self.menhir_coords = None

    @property
    def name(self) -> str:
        return f'Intercontinetal_bajers{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.BLUE


def distance(coords, other_coords):
    return sqrt((coords[0] - other_coords[0]) ** 2 + (coords[1] - other_coords[1]) ** 2)

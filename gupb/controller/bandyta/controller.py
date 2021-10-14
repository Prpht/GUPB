import random
from typing import Dict, List

from gupb.controller.bandyta.utils import POSSIBLE_ACTIONS, get_distance, get_direction, Direction, left_walk
from gupb.model import characters, tiles
from gupb.model.characters import ChampionKnowledge
from gupb.model import arenas
from gupb.model.coordinates import Coords
from gupb.controller.bandyta.bfs import find_path


class Bandyta:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.landscape_map: Dict[int, Dict[int, str]] = {}
        self.path: List[Coords] = []

    def __eq__(self, other: object):
        if isinstance(other, Bandyta):
            return self.first_name == other.first_name
        return False

    def __hash__(self):
        return hash(self.first_name)

    def decide(self, knowledge: ChampionKnowledge):
        try:
            self.memorize_landscape(knowledge)
            direction = get_direction(knowledge)
            player = self.find_player(knowledge.visible_tiles)

            if player is not None or len(self.path) != 0:
                if len(self.path) == 0 and get_distance(knowledge.position, player) < 10:
                    self.path = find_path(knowledge.position, player, self.landscape_map)
                    if len(self.path) != 0:
                        self.path.pop(0)

                if len(self.path) != 0:
                    action = self.move_on_path(knowledge.position, direction)
                    return action
            return random.choice(POSSIBLE_ACTIONS)
        except Exception as e:
            print(e)
            return random.choice(POSSIBLE_ACTIONS)

    def reset(self, arena_description: arenas.ArenaDescription):
        pass

    @property
    def name(self):
        return f'Bandyta{self.first_name}'

    @property
    def preferred_tabard(self):
        return characters.Tabard.GREY

    def memorize_landscape(self, knowledge: ChampionKnowledge):
        for cords, tile in knowledge.visible_tiles.items():
            if cords[0] not in self.landscape_map:
                self.landscape_map[cords[0]] = {}
            self.landscape_map[cords[0]][cords[1]] = tile.type

    def find_player(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for cords, tile in visible_tiles.items():
            if tile.character is not None and tile.character.controller_name != self.name:
                return cords
        return None

    def move_on_path(self, position: Coords, direction: Direction) -> characters.Action:
        if position + direction.value == self.path[0]:
            self.path.pop(0)
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_LEFT


POTENTIAL_CONTROLLERS = [
    Bandyta('test'),
]

from __future__ import annotations
import random
from typing import Dict

from gupb.controller.bandyta.utils import POSSIBLE_ACTIONS, get_direction, Direction, Path, \
    find_target_player, is_attack_possible, find_furthest_point, find_menhir
from gupb.model import characters, tiles
from gupb.model.characters import ChampionKnowledge
from gupb.model import arenas
from gupb.model.coordinates import Coords
from gupb.controller.bandyta.bfs import find_path


class Bandyta:
    """
    Dziary na pół ryja...
    """

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.landscape_map: Dict[int, Dict[int, str]] = {}
        self.path = Path(None, [])
        self.menhir: Coords | None = None

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
            player = find_target_player(self.name, knowledge, self.path.dest)
            self.menhir = find_menhir(knowledge.visible_tiles) if self.menhir is None else self.menhir

            if player is not None and \
                    is_attack_possible(knowledge.position, player[1], self.get_my_weapon(knowledge.visible_tiles)):
                self.path = Path('', [])
                return characters.Action.ATTACK

            if player is not None and (len(self.path.route) == 0 or self.path.dest is player[0]):
                self.path = Path(player[0], find_path(knowledge.position, player[1], self.landscape_map))

            if len(self.path.route) == 0 and self.menhir is not None:
                self.path = Path('menhir', find_path(knowledge.position, self.menhir, self.landscape_map))

            if len(self.path.route) == 0 and self.menhir is None:
                self.path = Path('furthest_point',
                                 find_path(knowledge.position,
                                           find_furthest_point(knowledge),
                                           self.landscape_map))

            if len(self.path.route) != 0:
                return self.move_on_path(knowledge.position, direction)

            return random.choice(POSSIBLE_ACTIONS)
        except Exception as e:
            # print(e)
            return random.choice(POSSIBLE_ACTIONS)

    def reset(self, arena_description: arenas.ArenaDescription):
        pass

    def get_my_weapon(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for cords, tile in visible_tiles.items():
            if tile.character is not None and tile.character.controller_name == self.name:
                return tile.character.weapon

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

    def move_on_path(self, position: Coords, direction: Direction) -> characters.Action:
        if position + direction.value == self.path.route[0]:
            self.path.route.pop(0)
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_LEFT


POTENTIAL_CONTROLLERS = [
    Bandyta('v1.2'),
]

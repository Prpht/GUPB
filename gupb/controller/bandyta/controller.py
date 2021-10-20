from __future__ import annotations

import random
from typing import Dict

from gupb.controller.bandyta.bfs import find_path
from gupb.controller.bandyta.utils import POSSIBLE_ACTIONS, get_direction, Path, \
    find_target_player, is_attack_possible, find_furthest_point, find_menhir, DirectedCoords, rotate_cw_dc, \
    get_distance, Weapon, get_rank_weapons
from gupb.model import arenas
from gupb.model import characters, tiles
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords
from gupb.model.profiling import profile, print_stats
from gupb.model.weapons import WeaponDescription


class Bandyta:
    """
    Dziary na pół ryja...
    """

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.landscape_map: Dict[int, Dict[int, str]] = {}
        self.item_map: Dict[Coords, WeaponDescription] = {}
        self.path = Path(None, [])
        self.menhir: Coords | None = None

    def __eq__(self, other: object):
        if isinstance(other, Bandyta):
            return self.first_name == other.first_name
        return False

    def __hash__(self):
        return hash(self.first_name)

    def decide(self, knowledge: ChampionKnowledge):
        action = self.__decide(knowledge)
        return action

    def __decide(self, knowledge: ChampionKnowledge):
        try:
            self.memorize_landscape(knowledge)
            direction = get_direction(knowledge)
            directed_position = DirectedCoords(knowledge.position, direction)
            player = find_target_player(self.name, knowledge, self.path.dest)
            weapon = self.get_my_weapon(knowledge.visible_tiles)
            self.menhir = find_menhir(knowledge.visible_tiles) if self.menhir is None else self.menhir

            if player is not None and \
                    is_attack_possible(knowledge.position, player[1], weapon):
                self.path = Path('', [])
                return characters.Action.ATTACK

            if weapon.name == Weapon.knife.value and self.path.dest != 'weapon':
                self.path = self.get_weapon_path(directed_position)

            if player is not None and (len(self.path.route) == 0 or self.path.dest is player[0]):
                self.path = Path(player[0], find_path(directed_position, player[1], self.landscape_map))

            if len(self.path.route) == 0 and self.menhir is not None:
                if get_distance(self.menhir, knowledge.position) > 1:
                    self.path = Path('menhir', find_path(directed_position, self.menhir, self.landscape_map))
                else:
                    return characters.Action.TURN_LEFT

            if len(self.path.route) == 0 and self.menhir is None:
                self.path = Path('furthest_point',
                                 find_path(directed_position,
                                           find_furthest_point(knowledge),
                                           self.landscape_map))

            if len(self.path.route) != 0:
                return self.move_on_path(directed_position)

            return random.choice(POSSIBLE_ACTIONS)
        except Exception as e:
            return random.choice(POSSIBLE_ACTIONS)

    def reset(self, arena_description: arenas.ArenaDescription):
        pass

    def get_my_weapon(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for cords, tile in visible_tiles.items():
            if tile.character is not None and tile.character.controller_name == self.name:
                return tile.character.weapon

    def get_weapon_path(self, dc: DirectedCoords):
        for ranked_weapon in get_rank_weapons():
            for coords, weapon in self.item_map.items():
                if weapon.name == ranked_weapon.name:
                    return Path('weapon', find_path(dc, coords, self.landscape_map))
        return Path('', [])

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

            if tile.loot is not None:
                self.item_map[cords] = Weapon(tile.loot.name)

            if tile.loot is None and cords in self.item_map:
                del self.item_map[cords]

    def move_on_path(self, dc: DirectedCoords) -> characters.Action:
        next_node = self.path.route.pop(0)

        if dc.direction is not next_node.direction:
            return characters.Action.TURN_RIGHT if \
                rotate_cw_dc(dc).direction is next_node.direction else \
                characters.Action.TURN_LEFT
        else:
            return characters.Action.STEP_FORWARD


POTENTIAL_CONTROLLERS = [
    Bandyta('v1.2'),
]

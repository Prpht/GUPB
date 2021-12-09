from __future__ import annotations
import random
from enum import Enum
from typing import Tuple

from gupb.controller.bandyta.bfs import find_path
from gupb.controller.bandyta.utils import get_direction, DirectedCoords, safe_find_target_player, Weapon, \
    safe_attack_possible, Path, get_distance, find_furthest_point, POSSIBLE_ACTIONS, find_target_player, \
    is_attack_possible, find_menhir, Direction, find_players
from gupb.model import characters
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from gupb.controller.bandyta import Bandyta


class Tactics(Enum):
    PASSIVE = 0
    AGGRESSIVE = 1
    ARCHER = 2

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


def init(self: Bandyta, knowledge: ChampionKnowledge) -> Tuple[DirectedCoords, Weapon]:
    self.memorize_landscape(knowledge)
    direction: Direction = get_direction(knowledge)
    directed_position: DirectedCoords = DirectedCoords(knowledge.position, direction)
    weapon: Weapon = self.get_my_weapon(knowledge.visible_tiles)
    self.menhir = find_menhir(knowledge.visible_tiles) if self.menhir is None else self.menhir

    return directed_position, weapon


def passive_tactic(self: Bandyta, knowledge: ChampionKnowledge):
    directed_position, weapon = init(self, knowledge)
    player: Tuple[str, Coords] = safe_find_target_player(self.name, knowledge, self.path.dest)

    if player is not None and \
            safe_attack_possible(knowledge, weapon, self.name):
        self.path = Path('', [])
        return characters.Action.ATTACK

    if weapon in [Weapon.knife, Weapon.amulet] and self.path.dest != 'weapon':
        possible_path: Path = self.get_weapon_path(directed_position)
        self.path = possible_path if len(possible_path.route) > 0 else self.path

    if player is not None and (len(self.path.route) == 0 or self.path.dest is player[0]):
        position_to_attack = self.nearest_coord_to_attack([player[1]], directed_position.coords,
                                                          Weapon.from_string(weapon.name))
        self.path = Path(player[0], find_path(directed_position, position_to_attack, self.landscape_map))

    if len(self.path.route) == 0 and self.menhir is not None:
        if get_distance(self.menhir, knowledge.position) > 0:
            self.path = Path('menhir', find_path(directed_position, DirectedCoords(self.menhir, None),
                                                 self.landscape_map))
        else:
            return characters.Action.TURN_LEFT

    if len(self.path.route) == 0 and self.menhir is None:
        self.path = Path('furthest_point',
                         find_path(directed_position,
                                   DirectedCoords(find_furthest_point(self.landscape_map, knowledge.position), None),
                                   self.landscape_map))

    if len(self.path.route) != 0:
        return self.move_on_path(directed_position)

    return random.choice(POSSIBLE_ACTIONS)


def aggressive_tactic(self, knowledge: ChampionKnowledge):
    directed_position, weapon = init(self, knowledge)
    player: Tuple[str, Coords] = find_target_player(self.name, knowledge, self.path.dest)

    if player is not None and \
            is_attack_possible(knowledge, weapon, self.name):
        self.path = Path('', [])
        return characters.Action.ATTACK

    if weapon is Weapon.knife and self.path.dest != 'weapon':
        possible_path: Path = self.get_weapon_path(directed_position)
        self.path = possible_path if len(possible_path.route) > 0 else self.path

    if player is not None and (len(self.path.route) == 0 or self.path.dest is player[0]):
        position_to_attack = self.nearest_coord_to_attack([player[1]], directed_position.coords,
                                                          Weapon.from_string(weapon.name))
        self.path = Path(player[0], find_path(directed_position, position_to_attack, self.landscape_map))

    if len(self.path.route) == 0 and self.menhir is not None:
        if get_distance(self.menhir, knowledge.position) > 0:
            self.path = Path('menhir', find_path(directed_position, DirectedCoords(self.menhir, None),
                                                 self.landscape_map))
        else:
            return characters.Action.TURN_LEFT

    # if self.path.dest == 'menhir':
    #     if self.menhir_move_cycle < 5:
    #         self.menhir_move_cycle += 1
    #         return characters.Action.TURN_LEFT
    #     else:
    #         self.menhir_move_cycle = 0

    if len(self.path.route) == 0 and self.menhir is None:
        self.path = Path('furthest_point',
                         find_path(directed_position,
                                   DirectedCoords(find_furthest_point(self.landscape_map, knowledge.position), None),
                                   self.landscape_map))

    if len(self.path.route) != 0:
        return self.move_on_path(directed_position)

    return random.choice(POSSIBLE_ACTIONS)


def archer_tactic(self: Bandyta, knowledge: ChampionKnowledge):
    directed_position, weapon = init(self, knowledge)
    player: Tuple[str, Coords] = safe_find_target_player(self.name, knowledge, self.path.dest)
    players = find_players(self.name, knowledge.visible_tiles)

    if is_attack_possible(knowledge, weapon, self.name):
        self.path = Path('', [])
        return characters.Action.ATTACK

    if weapon not in [Weapon.bow_loaded, Weapon.bow_unloaded] and self.path.dest != 'weapon':
        possible_path: Path = self.get_weapon_path(directed_position)
        self.path = possible_path if len(possible_path.route) > 0 else self.path

    if players and (len(self.path.route) == 0 or self.path.dest in ['furthest_point', *list(players.keys()), 'menhir']):
        position_to_attack = self.nearest_coord_to_attack(list(players.values()), directed_position.coords,
                                                          Weapon.from_string(weapon.name))
        self.path = Path(player[0], find_path(directed_position, position_to_attack, self.landscape_map))

    if len(self.path.route) == 0 and self.menhir is not None:
        if get_distance(self.menhir, knowledge.position) > 0:
            self.path = Path('menhir', find_path(directed_position, DirectedCoords(self.menhir, None),
                                                 self.landscape_map))
        else:
            return characters.Action.TURN_LEFT

    if len(self.path.route) == 0 and self.menhir is None:
        self.path = Path('furthest_point',
                         find_path(directed_position,
                                   DirectedCoords(find_furthest_point(self.landscape_map, knowledge.position), None),
                                   self.landscape_map))

    if len(self.path.route) != 0:
        return self.move_on_path(directed_position)

    return random.choice(POSSIBLE_ACTIONS)

from __future__ import annotations

import random
from typing import Dict, List, Tuple

from gupb.controller.bandyta.bfs import find_path
from gupb.controller.bandyta.utils import POSSIBLE_ACTIONS, get_direction, Path, \
    find_target_player, is_attack_possible, find_furthest_point, find_menhir, DirectedCoords, rotate_cw_dc, \
    get_distance, Weapon, get_rank_weapons, read_arena, line_weapon_attack_coords, axe_attack_coords, \
    amulet_attack_coords, Direction, knife_attack_possible
from gupb.model import arenas
from gupb.model import characters, tiles
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords, sub_coords
from gupb.model.profiling import profile, print_stats
from gupb.model.weapons import WeaponDescription


class Bandyta:
    """
    Dziary na pół ryja...
    """

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.landscape_map: Dict[int, Dict[int, str]] = {}
        self.item_map: Dict[Coords, Weapon] = {}
        self.path = Path(None, [])
        self.menhir: Coords = Coords(9, 9)
        self.arena = None
        self.menhir_move_cycle = 0

    def __eq__(self, other: object):
        if isinstance(other, Bandyta):
            return self.first_name == other.first_name
        return False

    def __hash__(self):
        return hash(self.first_name)

    def decide(self, knowledge: ChampionKnowledge):
        action = self.__decide(knowledge)
        return action

    @profile
    def __decide(self, knowledge: ChampionKnowledge):
        try:
            self.memorize_landscape(knowledge)
            direction = get_direction(knowledge)
            directed_position = DirectedCoords(knowledge.position, direction)
            player: Tuple[str, Coords] = find_target_player(self.name, knowledge, self.path.dest)
            weapon: Weapon = self.get_my_weapon(knowledge.visible_tiles)
            # self.menhir = find_menhir(knowledge.visible_tiles) if self.menhir is None else self.menhir

            if player is not None and \
                    is_attack_possible(knowledge, weapon, self.name):
                self.path = Path('', [])
                return characters.Action.ATTACK

            if weapon in [Weapon.knife, Weapon.amulet] and self.path.dest != 'weapon':
                possible_path: Path = self.get_weapon_path(directed_position)
                self.path = possible_path if len(possible_path.route) > 0 else self.path

            if player is not None and (len(self.path.route) == 0 or self.path.dest is player[0]):
                position_to_attack = self.nearest_coord_to_attack(player[1], directed_position.coords,
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
                                           DirectedCoords(find_furthest_point(knowledge), None),
                                           self.landscape_map))

            if len(self.path.route) != 0:
                return self.move_on_path(directed_position)

            return random.choice(POSSIBLE_ACTIONS)
        except Exception as e:
            print(e)
            return random.choice(POSSIBLE_ACTIONS)

    def reset(self, arena_description: arenas.ArenaDescription):
        self.arena = read_arena(arena_description)
        for sword in self.arena['sword']:
            self.item_map[sword] = Weapon.sword
        for axe in self.arena['axe']:
            self.item_map[axe] = Weapon.axe
        for bow in self.arena['bow']:
            self.item_map[bow] = Weapon.bow
        for amulet in self.arena['amulet']:
            self.item_map[amulet] = Weapon.amulet
        for knife in self.arena['knife']:
            self.item_map[knife] = Weapon.knife
        for land in self.arena['land']:
            if land[0] not in self.landscape_map:
                self.landscape_map[land[0]] = {}
            self.landscape_map[land[0]][land[1]] = 'land'

    def get_my_weapon(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for cords, tile in visible_tiles.items():
            if tile.character is not None and tile.character.controller_name == self.name:
                return Weapon.from_string(tile.character.weapon.name)

    def get_weapon_path(self, dc: DirectedCoords):
        for ranked_weapon in get_rank_weapons():
            weapon_list: List[Tuple[Coords, int]] = []

            for coords, weapon in self.item_map.items():
                if weapon.name == ranked_weapon.name:
                    weapon_list.append((coords, get_distance(dc.coords, coords)))

            if len(weapon_list) > 0:
                sorted_by_distance = sorted(weapon_list, key=lambda tup: tup[1])
                return Path('weapon', find_path(dc, DirectedCoords(sorted_by_distance[0][0], None), self.landscape_map))
        return Path('', [])

    @property
    def name(self):
        return f'Bandyta{self.first_name}'

    @property
    def preferred_tabard(self):
        return characters.Tabard.GREY

    def memorize_landscape(self, knowledge: ChampionKnowledge):
        for cords, tile in knowledge.visible_tiles.items():
            cords = Coords(cords[0], cords[1])
            if cords[0] not in self.landscape_map:
                self.landscape_map[cords[0]] = {}
            self.landscape_map[cords[0]][cords[1]] = tile.type

            if tile.loot is not None:
                self.item_map[cords] = Weapon.from_string(tile.loot.name)

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

    def nearest_coord_to_attack(self, enemy_position: Coords, my_position: Coords, weapon: Weapon) -> DirectedCoords:
        possible = self.possible_attack_coords(enemy_position, weapon)

        def remove_front_coords(c: DirectedCoords) -> bool:
            return c.coords in [sub_coords(enemy_position, Direction.S.value),
                                sub_coords(enemy_position, Direction.N.value),
                                sub_coords(enemy_position, Direction.E.value),
                                sub_coords(enemy_position, Direction.W.value)]

        possible = list(filter(remove_front_coords, possible))
        min_distance = 10000
        best_coord = DirectedCoords(enemy_position, None)
        for p in possible:
            distance = get_distance(my_position, p.coords)
            if distance < min_distance:
                min_distance = distance
                best_coord = p
        if best_coord.direction is None:
            best_coord = DirectedCoords(best_coord.coords, Direction.random())  # maybe better tactic for amulet
        return best_coord

    def possible_attack_coords(self, enemy_position: Coords, weapon: Weapon) -> List[DirectedCoords]:
        if weapon == Weapon.knife:
            return line_weapon_attack_coords(enemy_position, 1, self.is_valid_coords, self.is_wall)
        elif weapon in [Weapon.bow, Weapon.bow_unloaded, Weapon.bow_loaded]:
            return line_weapon_attack_coords(enemy_position, 50, self.is_valid_coords, self.is_wall)
        elif weapon == Weapon.sword:
            return line_weapon_attack_coords(enemy_position, 3, self.is_valid_coords, self.is_wall)
        elif weapon == Weapon.axe:
            return axe_attack_coords(enemy_position, self.is_valid_coords)
        elif weapon == Weapon.amulet:
            return amulet_attack_coords(enemy_position, self.is_valid_coords)
        else:
            raise KeyError(f"Not known weapon {weapon.name}.")

    def is_wall(self, coords: Coords) -> bool:
        return coords in self.arena['wall']

    def is_valid_coords(self, coords: DirectedCoords) -> bool:
        c = coords.coords
        return c in self.arena['land'] or c == self.menhir


POTENTIAL_CONTROLLERS = [
    Bandyta('v1.2'),
]

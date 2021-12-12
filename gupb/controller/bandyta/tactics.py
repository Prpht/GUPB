from __future__ import annotations

import random
from enum import Enum
from typing import Tuple

from gupb.controller.bandyta.bfs import find_path
from gupb.controller.bandyta.utils import DirectedCoords, safe_find_target_player, Weapon, \
    safe_attack_possible, Path, get_distance, find_furthest_point, POSSIBLE_ACTIONS, find_target_player, \
    is_attack_possible, find_players, get_weapon_path, State, move_on_path, extract_pytagorian_nearest, \
    nearest_coord_to_attack
from gupb.model import characters
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords


class Tactics(Enum):
    PASSIVE = 0
    AGGRESSIVE = 1
    ARCHER = 2

    @classmethod
    def list(cls):
        return list(map(lambda c: c.value, cls))


def passive_tactic(state: State, knowledge: ChampionKnowledge):
    player: Tuple[str, Coords] = safe_find_target_player(state.name, knowledge, state.path.dest)
    preferred_weapons = [Weapon.bow_loaded, Weapon.bow_unloaded, Weapon.bow]

    if player is not None and \
            safe_attack_possible(knowledge, state.weapon, state.name):
        state.path = Path('', [])
        return characters.Action.ATTACK

    if state.weapon not in preferred_weapons and state.path.dest != 'weapon' and not state.mist_coming:
        possible_path: Path = get_weapon_path(state.directed_position, state.item_map, state.not_reachable_items,
                                              state.landscape_map, preferred_weapons)
        state.path = possible_path if len(possible_path.route) > 0 else state.path

    if state.weapon in preferred_weapons and state.menhir is None and len(state.exploration_points) > 0 and state.path.dest != 'scan':
        exploration_checkpoint = extract_pytagorian_nearest(state)
        state.path = Path('scan', find_path(state.directed_position, exploration_checkpoint, state.landscape_map))

    if player is not None and not state.mist_coming and (len(state.path.route) == 0 or state.path.dest is player[0]):
        position_to_attack = nearest_coord_to_attack(state, [player[1]], state.directed_position.coords,
                                                     Weapon.from_string(state.weapon.name))
        state.path = Path(player[0], find_path(state.directed_position, position_to_attack, state.landscape_map))

    if (len(state.path.route) == 0 or (state.mist_coming and state.path.dest != 'menhir')) and state.menhir is not None:
        if get_distance(state.menhir, knowledge.position) > 0:
            state.path = Path('menhir', find_path(state.directed_position, DirectedCoords(state.menhir, None),
                                                  state.landscape_map))
        else:
            return characters.Action.TURN_LEFT

    if len(state.path.route) == 0 and state.menhir is None:
        state.path = Path('furthest_point',
                          find_path(state.directed_position,
                                    DirectedCoords(find_furthest_point(state.landscape_map, knowledge.position), None),
                                    state.landscape_map))

    if len(state.path.route) != 0:
        return move_on_path(state, state.directed_position)

    return random.choice(POSSIBLE_ACTIONS)


def aggressive_tactic(state: State, knowledge: ChampionKnowledge):
    player: Tuple[str, Coords] = find_target_player(state.name, knowledge, state.path.dest)
    preferred_weapons = [Weapon.axe, Weapon.amulet, Weapon.sword]

    if player is not None and \
            is_attack_possible(knowledge, state.weapon, state.name):
        state.path = Path('', [])
        return characters.Action.ATTACK

    if state.weapon not in preferred_weapons and state.path.dest != 'weapon':
        possible_path: Path = get_weapon_path(state.directed_position, state.item_map, state.not_reachable_items,
                                              state.landscape_map, preferred_weapons)
        state.path = possible_path if len(possible_path.route) > 0 else state.path

    if state.weapon in preferred_weapons and state.menhir is None and len(state.exploration_points) > 0 and state.path.dest != 'scan':
        exploration_checkpoint = extract_pytagorian_nearest(state)
        state.path = Path('scan', find_path(state.directed_position, exploration_checkpoint, state.landscape_map))

    if player is not None and (len(state.path.route) == 0 or state.path.dest is player[0]):
        position_to_attack = nearest_coord_to_attack(state, [player[1]], state.directed_position.coords,
                                                     Weapon.from_string(state.weapon.name))
        state.path = Path(player[0], find_path(state.directed_position, position_to_attack, state.landscape_map))

    if (len(state.path.route) == 0 or (state.mist_coming and state.path.dest != 'menhir')) and state.menhir is not None:
        if get_distance(state.menhir, knowledge.position) > 0:
            state.path = Path('menhir', find_path(state.directed_position, DirectedCoords(state.menhir, None),
                                                  state.landscape_map))
        else:
            return characters.Action.TURN_LEFT

    if len(state.path.route) == 0 and state.menhir is None:
        state.path = Path('furthest_point',
                          find_path(state.directed_position,
                                    DirectedCoords(find_furthest_point(state.landscape_map, knowledge.position), None),
                                    state.landscape_map))

    if len(state.path.route) != 0:
        return move_on_path(state, state.directed_position)

    return random.choice(POSSIBLE_ACTIONS)


def archer_tactic(state: State, knowledge: ChampionKnowledge):
    player: Tuple[str, Coords] = safe_find_target_player(state.name, knowledge, state.path.dest)
    players = find_players(state.name, knowledge.visible_tiles)
    preferred_weapons = [Weapon.bow_loaded, Weapon.bow_unloaded, Weapon.bow]

    if is_attack_possible(knowledge, state.weapon, state.name):
        state.path = Path('', [])
        return characters.Action.ATTACK

    if state.weapon not in preferred_weapons and state.path.dest != 'weapon':
        possible_path: Path = get_weapon_path(state.directed_position, state.item_map, state.not_reachable_items,
                                              state.landscape_map, preferred_weapons)
        state.path = possible_path if len(possible_path.route) > 0 else state.path

    if state.weapon in preferred_weapons and state.menhir is None and len(state.exploration_points) > 0 and state.path.dest != 'scan':
        exploration_checkpoint = extract_pytagorian_nearest(state)
        state.path = Path('scan', find_path(state.directed_position, exploration_checkpoint, state.landscape_map))

    if (len(state.path.route) == 0 or (state.mist_coming and state.path.dest != 'menhir')) and state.menhir is not None:
        if get_distance(state.menhir, knowledge.position) > 0:
            state.path = Path('menhir', find_path(state.directed_position, DirectedCoords(state.menhir, None),
                                                  state.landscape_map))
        else:
            return characters.Action.TURN_LEFT

    if len(state.path.route) == 0 and state.menhir is None:
        state.path = Path('furthest_point',
                          find_path(state.directed_position,
                                    DirectedCoords(find_furthest_point(state.landscape_map, knowledge.position), None),
                                    state.landscape_map))

    if len(state.path.route) != 0:
        return move_on_path(state, state.directed_position)

    return random.choice(POSSIBLE_ACTIONS)

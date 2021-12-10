import random

from typing import Tuple, Optional, Dict

from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.model.tiles import TileDescription


def forward_action(controller, position: coordinates.Coords, action=characters.Action.STEP_FORWARD):
    if action == characters.Action.STEP_FORWARD and controller.direction is not None:
        front_coords = position + controller.direction.value
        front_tile = controller.tiles_memory[front_coords]
        if front_tile.loot is not None:
            controller.hold_weapon = front_tile.loot.name
    return action


def rand_turn(controller):
    rand_gen = random.random()
    if rand_gen <= 0.5:
        controller.direction = controller.direction.turn_left()
        return characters.Action.TURN_LEFT
    else:
        controller.direction = controller.direction.turn_right()
        return characters.Action.TURN_RIGHT


def take_a_turn(controller, position: coordinates.Coords):
    """Bot chooses, whether to turn left or right"""
    left_coords = position + controller.direction.turn_left().value
    right_coords = position + controller.direction.turn_right().value
    try:
        left_tile = controller.tiles_memory[left_coords]
        right_tile = controller.tiles_memory[right_coords]
    except KeyError:
        return rand_turn(controller)
    else:
        if left_tile.type not in ["land", "menhir"] and right_tile.type in ["land", "menhir"]:
            controller.direction = controller.direction.turn_right()
            return characters.Action.TURN_RIGHT
        elif right_tile.type not in ["land", "menhir"] and left_tile.type in ["land", "menhir"]:
            controller.direction = controller.direction.turn_left()
            return characters.Action.TURN_LEFT
        else:
            return rand_turn(controller)


def obstacle_in_front(controller, position: coordinates.Coords):
    """Bots identifies the tile right in front of it"""
    coords_in_front = position + controller.direction.value
    tile_in_front = controller.tiles_memory[coords_in_front]
    if tile_in_front.type not in ["land", "menhir"]:
        return True
    return False


def check_if_mist_visible(controller, visible_tiles: Dict[coordinates.Coords, TileDescription]):
    for coord, tile in visible_tiles.items():
        for e in tile.effects:
            if e.type == 'mist':
                controller.mist_incoming = True


def weapon_in_reach(controller, position: coordinates.Coords):
    """Bot checks if it is next to a potential weapon it can reach"""
    front_coords = position + controller.direction.value
    left_coords = position + controller.direction.turn_left().value
    right_coords = position + controller.direction.turn_right().value
    # front tile had to be inspected independently to right and left tiles because bot doesn't need to know
    # neither right or left tile to pick up a weapon that is right in front of it
    front_tile = controller.tiles_memory[front_coords]
    if front_tile.loot is not None:
        return True
    try:
        left_tile = controller.tiles_memory[left_coords]
        right_tile = controller.tiles_memory[right_coords]
    except KeyError:
        return False
    else:
        if left_tile.loot is not None or right_tile.loot is not None:
            return True
        return False


def react_to_weapon(controller, position: coordinates.Coords):
    """Bot picks a proper action to a weapon laying on the ground"""
    front_coords = position + controller.direction.value
    left_coords = position + controller.direction.turn_left().value
    right_coords = position + controller.direction.turn_right().value
    front_tile = controller.tiles_memory[front_coords]
    # front tile had to be inspected independently to right and left tiles because bot doesn't need to know
    # neither right or left tile to pick up a weapon that is right in front of it;
    if front_tile.loot is not None:
        if controller.weapons_priorities[front_tile.loot.name] > controller.weapons_priorities[controller.hold_weapon]:
            controller.hold_weapon = front_tile.loot.name
            return characters.Action.STEP_FORWARD
        else:
            if controller.chosen_strategy != "strategy1":
                return take_a_turn(controller, position)
    try:
        left_tile = controller.tiles_memory[left_coords]
        right_tile = controller.tiles_memory[right_coords]
    except KeyError:
        if front_tile.loot is not None:
            controller.hold_weapon = front_tile.loot.name
        return characters.Action.STEP_FORWARD
    if left_tile.loot is not None:
        if controller.weapons_priorities[left_tile.loot.name] > controller.weapons_priorities[controller.hold_weapon]:
            controller.direction = controller.direction.turn_left()
            return characters.Action.TURN_LEFT
    if right_tile.loot is not None:
        if controller.weapons_priorities[right_tile.loot.name] > controller.weapons_priorities[controller.hold_weapon]:
            controller.direction = controller.direction.turn_right()
            return characters.Action.TURN_RIGHT
    return characters.Action.DO_NOTHING


""" Think about aggro """


def get_area_of_attack(controller, position, direction):
    aoa = []
    if controller.hold_weapon in ["knife", "sword", "bow_loaded"]:
        for i in range(controller.line_weapons_reach[controller.hold_weapon]):
            attack_coords = position + direction.value * (i + 1)
            aoa.append(attack_coords)
    else:
        attack_coords = position + direction.value
        if controller.hold_weapon == "axe":
            aoa.append(attack_coords)
        for turn in [controller.direction.turn_left().value, controller.direction.turn_right().value]:
            aoa.append(attack_coords + turn)
    return aoa


def enemy_to_the_side(controller, position):
    """ Bots tries to remember if there were any enemies on their left or right """
    area_left = get_area_of_attack(controller, position, controller.direction.turn_left())
    area_right = get_area_of_attack(controller, position, controller.direction.turn_right())
    left_out_of_reach = False
    right_out_of_reach = False
    for i in range(len(area_left)):
        try:
            left_tile = controller.tiles_memory[area_left[i]]
        except KeyError:
            left_out_of_reach = True
        else:
            if left_tile.type == "wall":
                left_out_of_reach = True
            if not left_out_of_reach and left_tile.character is not None:
                if left_tile.character.controller_name != controller.name:
                    controller.direction = controller.direction.turn_left()
                    return characters.Action.TURN_LEFT
        try:
            right_tile = controller.tiles_memory[area_right[i]]
        except KeyError:
            right_out_of_reach = True
        else:
            if right_tile.type == "wall":
                right_out_of_reach = True
            if not right_out_of_reach and right_tile.character is not None:
                if right_tile.character.controller_name != controller.name:
                    controller.direction = controller.direction.turn_right()
                    return characters.Action.TURN_RIGHT
        if left_out_of_reach and right_out_of_reach:
            break
    return characters.Action.DO_NOTHING


def enemy_in_reach(controller, knowledge: characters.ChampionKnowledge):
    """Bot checks whether the enemy is in potential area of attack"""
    area_of_attack = get_area_of_attack(controller, knowledge.position, controller.direction)
    # getting coordinates for visible tiles that bot can attack
    area_of_attack = list(set(area_of_attack) & set(knowledge.visible_tiles.keys()))
    for coords in area_of_attack:
        current_tile = knowledge.visible_tiles[coords]
        if current_tile.character is not None:
            return True
    return False

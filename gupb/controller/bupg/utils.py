from gupb.model import characters
from gupb.model.characters import Facing
from gupb.model.coordinates import Coords
from gupb.model.weapons import Axe, Sword, Bow, Knife, Scroll, Amulet


def position_change_to_move(curr_pos: tuple, new_pos: tuple, facing: Facing):
    move = Coords(
        curr_pos[1] - new_pos[1],
        (curr_pos[0] - new_pos[0])
    )

    if facing.value == move:
        return characters.Action.STEP_FORWARD
    elif facing.opposite().value == move:
        return characters.Action.STEP_BACKWARD
    elif facing.turn_left().value == move:
        return characters.Action.STEP_LEFT
    elif facing.turn_right().value == move:
        return characters.Action.STEP_RIGHT

    return characters.Action.DO_NOTHING


def weapon_class(weapon_name: str):
    if weapon_name == "axe":
        return Axe
    if weapon_name == "sword":
        return Sword
    if weapon_name == "bow_unloaded" or weapon_name == "bow_loaded":
        return Bow
    if weapon_name == "knife":
        return Knife
    if weapon_name == "scroll":
        return Scroll
    if weapon_name == "amulet":
        return Amulet
    raise Exception("No such weapon: " + weapon_name)

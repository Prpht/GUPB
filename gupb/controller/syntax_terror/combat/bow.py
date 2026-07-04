from gupb.model import characters, coordinates
from ..memory import MapMemory


def handle_my_bow(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    my_hp: int,
    my_weapon: str,
    enemy_pos: coordinates.Coords,
    opp_facing: characters.Facing,
    opp_hp: int,
    opp_weapon: str,
) -> tuple[characters.Action | None, str]:
    return characters.Action.TURN_LEFT, "BOW_TEMPORARY"


def handle_opp_bow(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    my_hp: int,
    my_weapon: str,
    enemy_pos: coordinates.Coords,
    opp_facing: characters.Facing,
    opp_hp: int,
    opp_weapon: str,
) -> tuple[characters.Action | None, str]:
    return characters.Action.TURN_LEFT, "BOW_TEMPORARY"


def handle_both_bows(
    memory: MapMemory,
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    my_hp: int,
    my_weapon: str,
    enemy_pos: coordinates.Coords,
    opp_facing: characters.Facing,
    opp_hp: int,
    opp_weapon: str,
) -> tuple[characters.Action | None, str]:
    return characters.Action.TURN_LEFT, "BOW_TEMPORARY"

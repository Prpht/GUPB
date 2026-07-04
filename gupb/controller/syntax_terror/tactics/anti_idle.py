import random
from gupb.model import characters, coordinates
from ..utils.visibility import is_visible

_ANTI_IDLE_TURNS = (characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT)

def get_random_anti_idle_turn() -> characters.Action:
    return random.choice(_ANTI_IDLE_TURNS)

def get_anti_idle_turn_preferring_enemy(
    my_pos: coordinates.Coords,
    my_facing: characters.Facing,
    enemy_pos: coordinates.Coords,
    transparent_coords: set[coordinates.Coords],
) -> characters.Action:
    valid_turns = []
    for t in _ANTI_IDLE_TURNS:
        new_facing = my_facing.turn_left() if t == characters.Action.TURN_LEFT else my_facing.turn_right()
        if is_visible(my_pos, new_facing, enemy_pos, transparent_coords, omnidirectional=False):
            valid_turns.append(t)
    if valid_turns:
        return random.choice(valid_turns)
    return get_random_anti_idle_turn()

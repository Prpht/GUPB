from gupb.model import characters
from gupb.model import coordinates


def manhattan_dist(a: coordinates.Coords, b: coordinates.Coords) -> int:
    return abs(a.x - b.x) + abs(a.y - b.y)


def simulate_action(
    position: coordinates.Coords,
    facing: characters.Facing,
    action: characters.Action,
) -> tuple[coordinates.Coords, characters.Facing]:
    match action:
        case characters.Action.TURN_LEFT:
            next_position, next_facing = position, facing.turn_left()
        case characters.Action.TURN_RIGHT:
            next_position, next_facing = position, facing.turn_right()
        case characters.Action.STEP_FORWARD:
            next_position, next_facing = position + facing.value, facing
        case characters.Action.STEP_BACKWARD:
            next_position, next_facing = position + facing.opposite().value, facing
        case characters.Action.STEP_LEFT:
            next_position, next_facing = position + facing.turn_left().value, facing
        case characters.Action.STEP_RIGHT:
            next_position, next_facing = position + facing.turn_right().value, facing
        case characters.Action.ATTACK | characters.Action.DO_NOTHING:
            next_position, next_facing = position, facing

    return next_position, next_facing

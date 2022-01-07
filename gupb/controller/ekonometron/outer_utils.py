from gupb.model import characters
from gupb.model import coordinates


LINE_WEAPONS_REACH = {
        "knife": 1,
        "sword": 3,
        "bow_loaded": 50
    }

WEAPONS_PRIORITIES = {
        "knife": 1,
        "amulet": 2,
        "axe": 3,
        "sword": 4,
        "bow_unloaded": 5,
        "bow_loaded": 5
    }


FORBIDDEN_COORDS = {
    'archipelago': [coordinates.Coords(x=14, y=45)],
    'dungeon': [
        coordinates.Coords(x=1, y=6),
        coordinates.Coords(x=1, y=7),
        coordinates.Coords(x=1, y=8),
        coordinates.Coords(x=1, y=9),
        coordinates.Coords(x=1, y=10),
        coordinates.Coords(x=7, y=37)
    ],
    'fisher_island': [coordinates.Coords(x=37, y=24), coordinates.Coords(x=9, y=10)],
    'wasteland': []
}


def forward_action(controller, position: coordinates.Coords, action=characters.Action.STEP_FORWARD):
    if action == characters.Action.STEP_FORWARD and controller.direction is not None:
        front_coords = position + controller.direction.value
        front_tile = controller.tiles_memory[front_coords]
        if front_tile.loot is not None:
            controller.hold_weapon = front_tile.loot.name
    return action


def right_action(controller):
    controller.direction = controller.direction.turn_right()
    return characters.Action.TURN_RIGHT


def left_action(controller):
    controller.direction = controller.direction.turn_left()
    return characters.Action.TURN_LEFT

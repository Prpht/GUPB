from gupb.model import characters
from gupb.model import tiles


def logger(msg):
    with open("gupb\\controller\\ares\\logs.txt", "a") as myfile:
        myfile.write(f"{msg}\n") 


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT
]

def tileIsMist(tile):
    for effect in tile.effects:
        if effect.type == 'mist':
            return True
    return False

def tilePassable(tile):
    if type(tile) == tiles.TileDescription:
        if tile.type in ['land', 'menhir']:
            return True
    elif type(tile) == tiles.Tile:
        return tile.passable
    return False
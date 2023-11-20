from typing import List
from gupb.model.coordinates import Coords
from gupb.model import arenas
from gupb.model import characters
from gupb.model import weapons

def get_weapon(arena: arenas.Arena, pos: Coords, facing: characters.Facing,
                         weapon: weapons) -> List[Coords]:
    pos = Coords(x=pos[0], y=pos[1])
    if weapon == 'knife':
        weapon_tile = weapons.Knife.cut_positions(arena.terrain, pos, facing)
    elif weapon == 'sword':
        weapon_tile = weapons.Sword.cut_positions(arena.terrain, pos, facing)
    elif weapon == 'bow_loaded':
        weapon_tile = weapons.Bow.cut_positions(arena.terrain, pos, facing)
    elif weapon == 'amulet':
        weapon_tile = weapons.Amulet.cut_positions(arena.terrain, pos, facing)
    else:
        weapon_tile = weapons.Axe.cut_positions(arena.terrain, pos, facing)
    return weapon_tile

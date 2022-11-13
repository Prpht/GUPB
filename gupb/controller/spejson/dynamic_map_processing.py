import numpy as np
from gupb.controller.spejson.utils import weapons, weapons_onehot, facing_onehot
from gupb.model.coordinates import Coords


def analyze_visible_region(visible_tiles, position, terrain, facing, weapon):
    """
    Analyze visible area.
    """
    visibility = {
        'someone_in_range': np.array([0], dtype=float),  # [VISIBLE] 1 if yes, 0 otherwise
        'me_in_dmg_range': np.array([0], dtype=float),  # [VISIBLE] 1 if yes, 0 otherwise
        'me_in_snipe_range': np.array([0], dtype=float),  # [VISIBLE] 1 if yes, 0 otherwise
        'visibility': np.zeros([13, 13, 1], dtype=float),  # [VISIBLE] 1 if yes, 0 otherwise
        'someone_here': np.zeros([13, 13, 1], dtype=float),  # [VISIBLE] 1 if yes, 0 otherwise
        'character_hp': np.zeros([13, 13, 1], dtype=float),  # [VISIBLE] Health points rescaled to 0-1
        'character_weapon': np.zeros([13, 13, 5], dtype=float), # [VISIBLE] One-hot encoding of current weapon (Knife, Axe, Bow, Sword, Amulet)
        'weapon_loc': np.zeros([13, 13, 5], dtype=float), # [VISIBLE] 1 if yes, 0 otherwise (Knife, Axe, Bow, Sword, Amulet)
        'mist_effect': np.zeros([13, 13, 1], dtype=float),  # [VISIBLE] 1 if yes, 0 otherwise
        'my_dmg_range': np.zeros([13, 13, 1], dtype=float),  # [VISIBLE] 1 if yes, 0 otherwise
        'others_dmg_range': np.zeros([13, 13, 1], dtype=float),  # [VISIBLE] 1 if yes, 0 otherwise
    }
    someone_in_range = 0
    me_in_dmg_range = 0
    me_in_snipe_range = 0
    menhir_seen = False
    menhir_loc = None
    mist_seen = False
    tiles = {}

    for k, v in visible_tiles.items():
        pos = (k[1] - position.y, k[0] - position.x)
        if abs(pos[0]) <= 6 and abs(pos[1]) <= 6:
            # Add to the short list of visible tiles
            tiles[pos] = v
        elif pos[0] == 0 or pos[1] == 0:
            if v.character:
                if 'bow' in v.character.weapon.name:
                    # Can someone snipe me?
                    me_in_snipe_range = 1
                if 'bow' in weapon.name and (pos[0] * facing.value[1] > 0 or pos[1] * facing.value[0] > 0):
                    # Can I snipe someone?
                    someone_in_range = 1

        if v.type == 'menhir':
            menhir_seen = True
            menhir_loc = Coords(x=k[0], y=k[1])
        if not mist_seen and v.effects and "mist" in list(map(lambda x: x.type, v.effects)):
            mist_seen = True

    my_att_range = []
    adversaries_pos = []

    for pos, tile in tiles.items():
        idx = (pos[0] + 6, pos[1] + 6)
        visibility['visibility'][idx] = 1

        if tile.character:
            visibility['someone_here'][idx] = 1
            visibility['character_hp'][idx] = 0.125 * tile.character.health
            weapon = tile.character.weapon
            visibility['character_weapon'][idx] = weapons_onehot[weapon.name]

            in_reach = weapons[weapon.name].cut_positions(
                terrain, Coords(x=position.x + pos[1], y=position.y + pos[0]), tile.character.facing)
            in_reach = [(att_tile[1] - position.y, att_tile[0] - position.x) for att_tile in in_reach]
            in_reach = [(p[0] + 6, p[1] + 6) for p in in_reach if abs(p[0]) <= 6 and abs(p[1]) <= 6]

            if pos == (0, 0):
                my_att_range = in_reach

                for p in in_reach:
                    visibility['my_dmg_range'][p] = 1
            else:
                adversaries_pos += [idx]
                if (6, 6) in in_reach:
                    me_in_dmg_range = 1

                for p in in_reach:
                    visibility['others_dmg_range'][p] = 1

        if tile.loot:
            visibility['weapon_loc'][idx] = weapons_onehot[tile.loot.name]

        if tile.effects:
            effects = list(map(lambda x: x.type, tile.effects))
            if "mist" in effects:
                visibility['mist_effect'][idx] = 1

    for adv in adversaries_pos:
        if adv in my_att_range:
            someone_in_range = 1

    visibility['someone_in_range'][0] = someone_in_range
    visibility['me_in_dmg_range'][0] = me_in_dmg_range
    visibility['me_in_snipe_range'][0] = me_in_snipe_range

    return visibility, menhir_seen, menhir_loc, mist_seen


def get_state_summary(position, menhir_location, facing, hp, weapon, epoch, menhir_found, mist_spotted, mist_close):
    state = {
        'facing': np.array([0, 0, 0, 0], dtype=float),  # [STATE] One-hot of current facing (U, R, D, L)
        'my_hp': np.array([0], dtype=float),  # [STATE] Health points rescaled to 0-1
        'my_weapon': np.array([0, 0, 0, 0, 0], dtype=float),  # [STATE] One-hot encoding of current weapon (Knife, Axe, Bow, Sword, Amulet)
        'epoch_num': np.array([0], dtype=float),  # [STATE] Rescaled by 0.02 factor
        'menhir_found': np.array([0], dtype=float),  # [STATE] 1 if yes, 0 otherwise
        'mist_spotted': np.array([0], dtype=float),  # [STATE] 1 if yes, 0 otherwise
        'mist_close': np.array([0], dtype=float),  # [STATE] 1 if yes, 0 otherwise
        'bow_unloaded': np.array([0], dtype=float),  # [STATE] 1 if yes, 0 otherwise
        'menhir_loc': np.zeros([13, 13, 1], dtype=float),  # [STATE] 1 if yes, 0 otherwise
    }

    state['facing'][0:4] = facing_onehot[facing]
    state['my_hp'][0] = 0.125 * hp
    state['my_weapon'][0:5] = weapons_onehot[weapon.name]
    state['epoch_num'][0] = 0.02 * epoch
    state['menhir_found'][0] = int(menhir_found)
    state['mist_spotted'][0] = int(mist_spotted)
    state['mist_close'][0] = int(mist_close)
    state['bow_unloaded'][0] = int(weapon.name == 'bow_unloaded')

    menhir_idx = (menhir_location.y - position.y, menhir_location.x - position.x)
    if abs(menhir_idx[0]) <= 6 and abs(menhir_idx[1]) <= 6:
        state['menhir_loc'][menhir_idx] = 1

    return state


def get_map_derivables():
    map_deriv = {
        'move_to_axe': np.array([0, 0, 0], dtype=float),  # [HALF-STATIC] One-hot encoding of move type (Left, Right, Forward) - to Axe
        'move_to_bow': np.array([0, 0, 0], dtype=float),  # [HALF-STATIC] One-hot encoding of move type (Left, Right, Forward) - to Bow
        'move_to_sword': np.array([0, 0, 0], dtype=float),  # [HALF-STATIC] One-hot encoding of move type (Left, Right, Forward) - to Sword
        'move_to_amulet': np.array([0, 0, 0], dtype=float),  # [HALF-STATIC] One-hot encoding of move type (Left, Right, Forward) - to Amulet
        'move_to_menhir': np.array([0, 0, 0], dtype=float),  # [HALF-STATIC] One-hot encoding of move type (Left, Right, Forward)
        'keypoint_dist': np.array([0, 0, 0, 0, 0], dtype=float),  # [HALF-STATIC] Dists to each weapon type and menhir (0.33 * np.sqrt(x))
        'walkability': np.zeros([13, 13, 1], dtype=float),  # [STATIC] 1 if yes, 0 otherwise
        'is_wall': np.zeros([13, 13, 1], dtype=float),  # [STATIC] 1 if yes, 0 otherwise
        'min_distance': np.zeros([13, 13, 1], dtype=float),  # [HALF-STATIC] 0.33 * np.sqrt(1 + x) of graph distance
        'attackability_fct': np.zeros([13, 13, 5], dtype=float),  # [STATIC] value
        'betweenness_centr': np.zeros([13, 13, 1], dtype=float),  # [STATIC] value
        'non_cluster_coeff': np.zeros([13, 13, 1], dtype=float),  # [STATIC] value
        'borderedness': np.zeros([13, 13, 1], dtype=float),  # [STATIC] value
    }

    return map_deriv

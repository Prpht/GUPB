from gupb.model import characters
import numpy as np


def encode_observation(knowledge: characters.ChampionKnowledge, sight_limit=10):

    x, y = knowledge.position.x, knowledge.position.y

    encoded_observation = np.zeros((sight_limit*2, sight_limit, 3))

    for coords, tile_desc in list(knowledge.visible_tiles.items()):

        tile_x, tile_y = coords.x, coords.y

        x_dist = np.abs(x - tile_x)
        y_dist = y - tile_y + sight_limit

        if x_dist > sight_limit or y_dist < 0 or y_dist > sight_limit*2:
            continue

        ground_type = 1 if tile_desc.type == 'land' else 0
        hero = 1 if tile_desc.character is not None else 0
        effect = 1 if len(tile_desc.effects) > 0 else 0

        encoded_observation[y_dist, x_dist, :] = np.array([ground_type, hero, effect])

    return encoded_observation

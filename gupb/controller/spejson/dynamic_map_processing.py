import numpy as np
from gupb.controller.spejson.pathfinding import find_path
from gupb.model.coordinates import Coords


def analyze_weapons_on_map(weapons_knowledge, clusters):
    stack_axe = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'A']
    stack_bow = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'B']
    stack_sword = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'S']
    stack_amulet = [pos for pos in weapons_knowledge if weapons_knowledge[pos] == 'M']

    def get_dists(stack, base=0):
        dists = 9999 * np.ones(clusters.shape, dtype=np.int32)

        for pos in stack:
            dists[pos] = base

        while stack:
            pos = stack.pop(0)

            for dxdy in np.array([[-1, 0], [1, 0], [0, -1], [0, 1]]):
                new_pos = tuple(pos + dxdy)
                if clusters[new_pos] and dists[pos] + 1 < dists[new_pos]:
                    dists[new_pos] = dists[pos] + 1
                    stack.append(new_pos)

        return dists

    dists_axe = get_dists(stack_axe)
    dists_bow = get_dists(stack_bow, base=-1)  # Preferred weapon
    dists_sword = get_dists(stack_sword)
    dists_amulet = get_dists(stack_amulet)

    closest_weapon = np.argmin(np.stack(
        [9998 * np.ones(clusters.shape, dtype=np.int32),
         dists_axe, dists_bow, dists_sword, dists_amulet,
        ], axis=-1), axis=-1)

    closest_weapon = np.where(
        closest_weapon == 0,
        "-",
        np.where(
            closest_weapon < 3,
            np.where(closest_weapon == 1, "A", "B"),
            np.where(closest_weapon == 3, "S", "M")
        )
    )
    return closest_weapon


def find_closest_weapon(weapons_knowledge, position, weapon_letter, clusters, adj, menhir_location):
    closest_weapon_position = (menhir_location.y, menhir_location.x)
    closest_weapon_distance = 9999

    for pos in [pos for pos in weapons_knowledge if weapons_knowledge[pos] == weapon_letter]:
        dist = len(find_path(adj, clusters[(position.y, position.x)], clusters[pos]))
        if dist < closest_weapon_distance:
            closest_weapon_distance = dist
            closest_weapon_position = pos

    return Coords(x=closest_weapon_position[1], y=closest_weapon_position[0])

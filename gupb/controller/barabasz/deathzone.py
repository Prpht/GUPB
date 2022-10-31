from gupb.model import coordinates
from gupb.model import weapons


def deathzone(weapon: weapons.Weapon, position: coordinates.Coords, facing: coordinates.Coords):
    death_coords = []

    if isinstance(weapon, weapons.Knife):
        death_coords.append(coordinates.add_coords(position, facing))

    elif isinstance(weapon, weapons.Axe):
        death_coords.append(coordinates.add_coords(position, facing))
        if facing[0] == 0:
            for i in [-1, 1]:
                death_coords.append(coordinates.add_coords(position, coordinates.Coords(i, facing[1])))
        else:
            for i in [-1, 1]:
                death_coords.append(coordinates.add_coords(position, coordinates.Coords(facing[0], i)))

    elif isinstance(weapon, weapons.Sword):
        sword_range = 3
        attacked_position = position
        for i in range(sword_range):
            attacked_position = coordinates.add_coords(attacked_position, facing)
            death_coords.append(attacked_position)

    elif isinstance(weapon, weapons.Amulet):
        amulet_range = 2
        for i in range(amulet_range):
            for x in [-i, i]:
                for y in [-i, i]:
                    death_coords.append(coordinates.add_coords(position, coordinates.Coords(x, y)))

    elif isinstance(weapon, weapons.Bow):
        if weapon.ready:
            bow_range = 8
            attacked_position = position
            for i in range(bow_range):
                attacked_position = coordinates.add_coords(attacked_position, facing)
                death_coords.append(attacked_position)

    return death_coords

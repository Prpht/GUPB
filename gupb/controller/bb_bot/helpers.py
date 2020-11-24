import math

from gupb.model import coordinates


def get_tile_type(tiles, coord):
    if (coord in tiles):
        return tiles[coord].type
    return None


def should_attack(knowledge):
    current_pos = knowledge.visible_tiles[knowledge.position]
    in_front = knowledge.visible_tiles[knowledge.position + current_pos.character.facing.value]

    return in_front.character is not None


class HidingSpotFinder:
    def __init__(self, controller):
        self.controller = controller
        self.shelter3tiles = []
        self.shelter2tiles = []

    def findHiddingSpots(self):
        self.shelter3tiles = []
        self.shelter2tiles = []
        tiles = self.controller.scanedArena
        for (key, value) in tiles.items():
            if (value.type == 'land'):
                neighbouringTiles = []

                neighbour = coordinates.add_coords(key, (0, 1))
                if (get_tile_type(tiles, neighbour) == 'wall'):
                    neighbouringTiles.append(neighbour)

                neighbour = coordinates.add_coords(key, (1, 0))
                if (get_tile_type(tiles, neighbour) == 'wall'):
                    neighbouringTiles.append(neighbour)

                neighbour = coordinates.add_coords(key, (0, -1))
                if (get_tile_type(tiles, neighbour) == 'wall'):
                    neighbouringTiles.append(neighbour)

                neighbour = coordinates.add_coords(key, (-1, 0))
                if (get_tile_type(tiles, neighbour) == 'wall'):
                    neighbouringTiles.append(neighbour)

                if (len(neighbouringTiles) == 3):
                    self.shelter3tiles.append(key)
                if (len(neighbouringTiles) == 2 and math.dist(neighbouringTiles[0], neighbouringTiles[1]) != 2):
                    self.shelter2tiles.append(key)

    def getBestSpot(self):
        self.findHiddingSpots()
        if (len(self.shelter3tiles) > 0):
            return max(self.shelter3tiles, key=lambda c: math.dist(c, self.controller.menhirPos))
        if (len(self.shelter2tiles) > 0):
            return max(self.shelter2tiles, key=lambda c: math.dist(c, self.controller.menhirPos))
        return None

import traceback

import numpy as np

from gupb.model import arenas
from gupb.model import characters


class MenhirFinder:
    def __init__(self, arena_description: arenas.ArenaDescription):
        self.arena = arenas.Arena.load(arena_description.name)
        self.size = self.arena.size
        self.is_menhir_possible = np.zeros(self.size)

        self.mist_radius = int(self.size[0] * 2**0.5) + 1

        for cords in self.arena.empty_coords():
            self.is_menhir_possible[cords[0], cords[1]] = 1

        self.menhir_position = None

        print("total tiles: ", self.arena.size[0] * self.arena.size[1])

    def update(self, knowledge: characters.ChampionKnowledge) -> None:
        try:
            print("predicted radius: ", self.mist_radius)

            if self.menhir_position:
                return self.menhir_position
            self.mist_radius = max(self.mist_radius - 1, 0)

            for cords, tile in knowledge.visible_tiles.items():
                if tile.type == "menhir":
                    self.menhir_position = cords
                    return

                self.is_menhir_possible[cords[0], cords[1]] = 0

                if "mist" in [effect.type for effect in tile.effects]:
                    self.exclude_impossible_positions(cords)

                # if self.is_menhir_possible.flatten().sum() == 1:
                #     print("MENHIR FOUND BY EXCLUSION")
                #     return self.is_menhir_possible.flatten().argmax()


        except Exception as e:
            traceback.print_exc()
            print(e)

    def distance(self, a, b):
        return int(((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5)

    def exclude_impossible_positions(self, cords):
        possible_positions = np.argwhere(self.is_menhir_possible == 1)
        for pos in possible_positions:
            x, y = pos
            if self.distance((x, y), cords) > self.mist_radius:
                self.is_menhir_possible[x, y] = 0

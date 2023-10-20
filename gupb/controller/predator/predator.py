import random
import math

from gupb import controller
from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.coordinates import Coords

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

POSSIBLE_MOVES = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]

POSSIBLE_TURNS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
]


class Predator(controller.Controller):
    def __init__(self, first_name: str):
        self.no_of_enemies = None
        self.champion = None
        self.position = None
        self.first_name: str = first_name
        self.map_knowledge = dict()
        self.iter = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Predator):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def update_map_knowledge(self, visible_tiles):
        for coords, description in visible_tiles.items():
            self.map_knowledge[coords] = description
            # if not self.menhir_coords and self.check_menhir(coords):
            #     self.menhir_coords = coords
            # if self.check_mist(coords):
            #     self.mist_coords.add(coords)

    def can_step_forward(self):
        new_position = self.position + self.champion.facing.value
        # print(self.map_knowledge[new_position].type)
        return self.map_knowledge[new_position].type == 'land'

    #     # return True
    #
    def is_enemy_front(self):
        front_coords = self.position + self.champion.facing.value
        return self.map_knowledge[front_coords].character

    def is_enemy_front2(self):
        if self.champion.weapon.description() == 'bow':
            front_coords = self.position
            for i in range(4):
                front_coords = front_coords + self.champion.facing.value
                if self.map_knowledge[front_coords].character:
                    return True
            return False

    #     # return False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.iter += 1
        self.position = knowledge.position
        self.champion = knowledge.visible_tiles[knowledge.position].character
        self.no_of_enemies = knowledge.no_of_champions_alive
        self.update_map_knowledge(knowledge.visible_tiles)


        # todo
        # uciekanie przed mgla
        # chodzenie do broni i przeciwnikow
        # co robi menhir?

        # return random.choice(POSSIBLE_MOVES)

        if self.is_enemy_front():
            return characters.Action.ATTACK
        if self.can_step_forward():
            return characters.Action.STEP_FORWARD

        return random.choice(POSSIBLE_TURNS)
        # return characters.Action.TURN_RIGHT

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f'Predator'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.VIOLET


def dist(coord1, coord2):
    return math.sqrt((coord1[0] - coord2[0]) ** 2 + (coord1[1] - coord2[1]) ** 2)

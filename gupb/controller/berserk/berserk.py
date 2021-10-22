import numpy as np

from gupb.model import arenas
from gupb.model import characters
from gupb.controller.berserk.knowledge_decoder import KnowledgeDecoder
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.finder.a_star import AStarFinder
from collections import deque
from gupb.model.characters import Facing
from gupb.model import coordinates
from gupb.controller.berserk.utilities import distance


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BerserkBot:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.knowledge_decoder = KnowledgeDecoder()
        self._possible_actions = [
            characters.Action.TURN_LEFT,
            characters.Action.TURN_RIGHT,
            characters.Action.STEP_FORWARD,
            characters.Action.ATTACK,
        ]
        self.probabilities = [0.4, 0.4, 0.1, 0.1]
        self.move_counter = 0
        self.path = deque()
        self.picked_up_weapon = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BerserkBot):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.probabilities = [0.4, 0.4, 0.1, 0.1]
        self.move_counter = 0

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.knowledge_decoder.knowledge = knowledge
        if self.can_attack():
            move = characters.Action.ATTACK
        elif self.move_counter <= 2 or not self.path:
            move = self.look_around()
        elif self.picked_up_weapon == 0 and self.knowledge_decoder._info['weapons_in_sight']:
            self.find_weapon()
            move = self.parse_path()
        elif self.path:
            move = self.parse_path()
        elif self.knowledge_decoder._info['enemies_in_sight']:
            self.find_enemy()
            move = self.parse_path()
        else:
            move = self.look_around()
        self.move_counter += 1
        return move

    @property
    def name(self) -> str:
        return f'BerserkBot{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GREY

    def find_path(self, start, goal):
        start = self.knowledge_decoder.map.node(start[0], start[1])
        goal = self.knowledge_decoder.map.node(goal[0], goal[1])

        finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        path, runs = finder.find_path(start, goal, self.knowledge_decoder.map)
        self.path = path

    def parse_path(self):
        facing = self.knowledge_decoder._info['facing']
        position = self.knowledge_decoder.knowledge.position
        position = coordinates.Coords(position[0], position[1])
        target = self.path[0]
        target = coordinates.Coords(target[0], target[1])
        needed_facing = Facing(coordinates.sub_coords(target, position))
        if facing == needed_facing:
            self.path.popleft()
            return characters.Action.STEP_FORWARD
        else:
            return characters.Action.TURN_RIGHT

    def look_around(self):
        return characters.Action.TURN_RIGHT

    def choose_shorter_dist(self, list_of_objects):
        position = self.knowledge_decoder.knowledge.position
        distances = [distance(position, object_pos) for object_pos in list_of_objects]
        return list_of_objects[np.argmin(distances)]

    def find_weapon(self):
        weapon_cords = self.choose_shorter_dist(self.knowledge_decoder._info['weapons_in_sight'])
        position = self.knowledge_decoder.knowledge.position
        self.find_path(position, weapon_cords)
        self.picked_up_weapon = 1

    def find_enemy(self):
        enemy_cords = self.choose_shorter_dist(self.knowledge_decoder._info['enemies_in_sight'])
        position = self.knowledge_decoder.knowledge.position
        self.find_path(position, enemy_cords)

    def can_attack(self):
        if self.knowledge_decoder._info['enemies_in_sight']:
            enemy_cords = self.choose_shorter_dist(self.knowledge_decoder._info['enemies_in_sight'])
            facing = self.knowledge_decoder._info['facing']
            position = self.knowledge_decoder.knowledge.position
            dist = distance(position, enemy_cords)
            position = coordinates.Coords(position[0], position[1])
            target = coordinates.Coords(enemy_cords[0], enemy_cords[1])
            needed_facing = Facing(coordinates.sub_coords(target, position))
            if facing == needed_facing and dist <= 3:
                return True
        else:
            return False
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
from gupb.model.coordinates import Coords

from gupb.model import arenas, characters, coordinates
from gupb.model.characters import Facing
from gupb.model.profiling import profile
from gupb import controller

import random
import numpy as np

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]

EXPLORE_COEF = 0.2

class R2D2Controller(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.map = np.zeros((200, 200))
        self.position = None
        self.facing = None
        self.visible_tiles = {}
        self.menhir_position = None
        self.on_menchir = False
        self.my_destination=Coords(24,27)
        self.visited=[]
        self.known=[]
        self.destination=False
        self.path=None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, R2D2Controller):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def follow_the_path(self):
        dest=self.destination
        matrix = Grid(matrix=self.map)
        start = matrix.node(self.position.x, self.position.y)
        self.destination = matrix.node(self.destination.x, self.destination.y)
        astar_finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
        self.path, _ = astar_finder.find_path(start, self.destination, matrix)
        dist=np.linalg.norm(np.array((self.position.x, self.position.y)) - np.array((dest.x,dest.y)))
        if dist==1 and ((self.facing==Facing.DOWN and dest.y-self.position.y==1)or(self.facing==Facing.UP and dest.y-self.position.y==-1)or(self.facing==Facing.RIGHT and dest.x-self.position.x==1)or(self.facing==Facing.LEFT and dest.x-self.position.x==-1)):
            return characters.Action.STEP_FORWARD
        if self.path:
            orientation = characters.Facing(coordinates.sub_coords(self.path[1], self.position))
            turn_right = [(Facing.RIGHT, Facing.DOWN), (Facing.DOWN, Facing.LEFT), (Facing.LEFT, Facing.UP),
                          (Facing.UP, Facing.RIGHT)]
            turn_left = [(Facing.RIGHT, Facing.UP), (Facing.UP, Facing.LEFT), (Facing.LEFT, Facing.DOWN),
                         (Facing.DOWN, Facing.RIGHT)]
            turn_back = [(Facing.RIGHT, Facing.LEFT), (Facing.UP, Facing.DOWN), (Facing.LEFT, Facing.RIGHT),
                         (Facing.DOWN, Facing.UP)]
            if (self.facing, orientation) in turn_right:
                return characters.Action.TURN_RIGHT
            if (self.facing, orientation) in turn_left:
                return characters.Action.TURN_LEFT
            if (self.facing, orientation) in turn_back:
                return characters.Action.TURN_RIGHT
            else:
                return characters.Action.STEP_FORWARD
        else:
            action = random.choice(POSSIBLE_ACTIONS)
            while action == characters.Action.ATTACK:
                action = random.choice(POSSIBLE_ACTIONS)
            return action


    def update_knowledge(self, knowledge: characters.ChampionKnowledge):
        if self.destination==self.position:
            self.path=False
            self.destination=False
        self.position = knowledge.position
        if knowledge.position not in self.visited:
            self.visited.append((knowledge.position.x,knowledge.position.y))
        self.visible_tiles = knowledge.visible_tiles
        char_description = knowledge.visible_tiles[knowledge.position].character
        self.facing = char_description.facing
        self.map[self.position.x, self.position.y] = 1
        for position, description in self.visible_tiles.items():
            if description.type == "land":
                self.map[position[0], position[1]] = 1
            elif description.type == "menhir":
                self.map[position[0], position[1]] = 1
                self.menhir_position = coordinates.Coords(position[0], position[1])

    def is_enemy_ahead(self, knowledge: characters.ChampionKnowledge) -> bool:
        visible_tile = self.position + self.facing.value
        if knowledge.visible_tiles[visible_tile].character:
            return True
        else:
            return False

    @profile
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.update_knowledge(knowledge)
        if self.on_menchir:
            if self.is_enemy_ahead(knowledge):
                return characters.Action.ATTACK
            else:
                return characters.Action.TURN_RIGHT
        else:
            if self.is_enemy_ahead(knowledge):
                return characters.Action.ATTACK
            if self.menhir_position is not None:
                if (self.position.x - self.menhir_position.x, self.position.y - self.menhir_position.y) == (0, 0):
                    self.on_menchir = True
                    pass
                else:
                    self.destination=self.menhir_position
                    return self.follow_the_path()
            else:
                for i in knowledge.visible_tiles.keys():
                    if (type(i) is tuple) and (i not in self.known) and (knowledge.visible_tiles[i].type not in ('wall', 'sea')):
                        self.known.append(i)
                to_go=list(set(self.known) - set(self.visited) - set(self.position))
                if to_go==[]:
                    return characters.Action.STEP_FORWARD
                ind=self.closest_node((knowledge.position.x, knowledge.position.y),to_go)
                self.destination=Coords(to_go[ind][0], to_go[ind][1])
                return self.follow_the_path()

    def closest_node(self, node, nodes):
        nodes = np.asarray(nodes)
        dist_2 = np.sum((nodes - node) ** 2, axis=1)
        return np.argmin(dist_2)

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.WHITE


POTENTIAL_CONTROLLERS = [
    R2D2Controller("R2D2")
]

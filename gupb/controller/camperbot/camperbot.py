from fontTools.misc.psOperators import ps_string

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
import random
import networkx as nx
from gupb.model.coordinates import Coords
import time

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


class CamperBotController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena_description = None
        self.is_menhir_found = False
        self.menhir_cords = None
        self.visited = []
        self.arena = None
        self.arena_graph = None
        self.path_to_menhir = None

    def load_arena_to_graph(self):
        self.arena = arenas.Arena.load(self.arena_description.name)
        self.arena_graph = nx.Graph()

        for coord, tile in self.arena.terrain.items():
            # Dodajemy każdy wierzchołek, niezależnie od przechodniości
            self.arena_graph.add_node(coord)

            # Sprawdzamy tylko sąsiadów jeśli pole jest przechodnie
            if not tile.terrain_passable():
                continue

            neighbors = [
                Coords(coord.x + 1, coord.y),
                Coords(coord.x - 1, coord.y),
                Coords(coord.x, coord.y + 1),
                Coords(coord.x, coord.y - 1),
            ]

            for neighbor in neighbors:
                neighbor_tile = self.arena.terrain.get(neighbor)
                if neighbor_tile and neighbor_tile.terrain_passable():
                    self.arena_graph.add_edge(coord, neighbor)


    def __eq__(self, other: object) -> bool:
        if isinstance(other, CamperBotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def find_menhir(self, knowledge: characters.ChampionKnowledge):
        for coords, visible_tile in knowledge.visible_tiles.items():
            if visible_tile.type == 'menhir':
                self.is_menhir_found = True
                self.menhir_cords = coords

    def find_path_to_menhir(self, knowledge: characters.ChampionKnowledge):
        current_position = knowledge.position
        menhir_position = self.menhir_cords

        try:
            path = nx.shortest_path(self.arena_graph, source=knowledge.position, target=self.menhir_cords)
            # print(f"Path to menhir found from current position {knowledge.position}: {path}")
            self.path_to_menhir = path[1:]
        except nx.NetworkXNoPath:
            # print(f"Brak ścieżki z {current_position} do {menhir_position}")
            return None
        except nx.NodeNotFound as e:
            # print(f"Nie znaleziono węzła: {e}")
            return None

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        current_position = knowledge.position
        character = knowledge.visible_tiles[knowledge.position].character
        facing = character.facing

        self.visited.append(current_position)


        if not self.is_menhir_found:
            self.find_menhir(knowledge)


        possible_step = current_position + self.step_forward(facing)

        if not self.is_menhir_found:

            next_tile = knowledge.visible_tiles.get(possible_step, None)

            if possible_step not in self.visited:
                if next_tile is None or (next_tile.type not in ['sea', 'wall']):
                    return characters.Action.STEP_FORWARD
                else:
                    return random.choice(POSSIBLE_ACTIONS[:-1])
            elif next_tile and next_tile.type not in ['sea','wall']:
                return random.choice(POSSIBLE_ACTIONS[:-1])
            else:
                return random.choice(POSSIBLE_ACTIONS[:-1])
        else:
            if self.path_to_menhir is None:
                self.find_path_to_menhir(knowledge)

            # condition to stop going towards menhir as we are close
            if len(self.path_to_menhir) > 1:
                next_tile = self.path_to_menhir.pop(0)
                next_step_action = self.step_to_menhir(knowledge, next_tile)
                return next_step_action
            # spinning around when we are close to menhir
            else:
                return random.choice(POSSIBLE_ACTIONS[:-2])

    def step_to_menhir(self, knowledge: characters.ChampionKnowledge, next_position: Coords):
        "Chosing action to step toward menhir"
        current_position = knowledge.position
        character = knowledge.visible_tiles[knowledge.position].character
        facing = character.facing
        coord_difference = current_position - next_position
        if coord_difference.x == -1:
            return self.step_absolute_right(facing)
        elif coord_difference.x == 1:
            return self.step_absolute_left(facing)
        elif coord_difference.y == 1:
            return self.step_absoulute_up(facing)
        elif coord_difference.y == -1:
            return self.step_absoulute_down(facing)

    def step_absolute_right(self, facing):
        if facing == characters.Facing.RIGHT:
            return characters.Action.STEP_FORWARD

        elif facing == characters.Facing.LEFT:
            return characters.Action.STEP_BACKWARD

        elif facing == characters.Facing.UP:
            return characters.Action.STEP_RIGHT

        elif facing == characters.Facing.DOWN:
            return characters.Action.STEP_LEFT


    def step_absolute_left(self, facing):
        if facing == characters.Facing.RIGHT:
            return characters.Action.STEP_BACKWARD

        elif facing == characters.Facing.LEFT:
            return characters.Action.STEP_FORWARD

        elif facing == characters.Facing.UP:
            return characters.Action.STEP_LEFT

        elif facing == characters.Facing.DOWN:
            return characters.Action.STEP_RIGHT


    def step_absoulute_up(self, facing):
        if facing == characters.Facing.RIGHT:
            return characters.Action.STEP_LEFT

        elif facing == characters.Facing.LEFT:
            return characters.Action.STEP_RIGHT

        elif facing == characters.Facing.UP:
            return characters.Action.STEP_FORWARD

        elif facing == characters.Facing.DOWN:
            return characters.Action.STEP_BACKWARD

    def step_absoulute_down(self, facing):
        if facing == characters.Facing.RIGHT:
            return characters.Action.STEP_RIGHT

        elif facing == characters.Facing.LEFT:
            return characters.Action.STEP_LEFT

        elif facing == characters.Facing.UP:
            return characters.Action.STEP_BACKWARD

        elif facing == characters.Facing.DOWN:
            return characters.Action.STEP_FORWARD


    def step_forward(self, facing):
        if facing == characters.Facing.RIGHT:
            return Coords(1,0)
        elif facing == characters.Facing.LEFT:
            return Coords(-1,0)
        elif facing == characters.Facing.UP:
            return Coords(0,-1)
        elif facing == characters.Facing.DOWN:
            return Coords(0,1)

    def step_backward(self, facing):
        if facing == characters.Facing.RIGHT:
            return Coords(-1,0)
        elif facing == characters.Facing.LEFT:
            return Coords(1,0)
        elif facing == characters.Facing.UP:
            return Coords(0,1)
        elif facing == characters.Facing.DOWN:
            return Coords(0,-1)

    def step_right(self, facing):
        if facing == characters.Facing.RIGHT:
            return Coords(0,1)
        elif facing == characters.Facing.LEFT:
            return Coords(0,-1)
        elif facing == characters.Facing.UP:
            return Coords(1,0)
        elif facing == characters.Facing.DOWN:
            return Coords(-1,0)

    def step_left(self, facing):
        if facing == characters.Facing.RIGHT:
            return Coords(0,-1)
        elif facing == characters.Facing.LEFT:
            return Coords(0,1)
        elif facing == characters.Facing.UP:
            return Coords(-1,0)
        elif facing == characters.Facing.DOWN:
            return Coords(1,0)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena_description = arena_description
        self.is_menhir_found = False
        self.menhir_cords = None
        self.visited = []
        self.arena = None
        self.path_to_menhir = None
        self.arena_graph = None
        self.load_arena_to_graph()


    @property
    def name(self) -> str:
        return f'CamperBot{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.CAMPER


POTENTIAL_CONTROLLERS = [
    CamperBotController("V0"),
]

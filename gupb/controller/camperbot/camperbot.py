from gupb import controller
from gupb.model import arenas
from gupb.model import characters, tiles
import random
import networkx as nx
from gupb.model.coordinates import Coords
import logging
import numpy as np

TURNING_ACTIONS = [characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT]
MOVEMENT_ACTIONS = [
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    # characters.Action.STEP_BACKWARD,

]
ATTACK_ACTIONS = [
    characters.Action.ATTACK,
]
logger = logging.getLogger("verbose")

class CamperBotController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena_description = None
        self.is_menhir_found = False
        self.menhir_cords = None
        self.visited = set()
        self.arena = None
        self.arena_graph = None
        self.path_to_menhir = None
        self.forrest_tiles_list = []
        self.path_to_forrest = None
        self.go_to_forrest = True
        self.go_to_menhir = False
        self.path_to_potion = None
        self.seen = set()

    def is_mist_arround(self, knowledge: characters.ChampionKnowledge, mist_arround_trehshold: int = 2) -> bool:
        for coords, visible_tile in knowledge.visible_tiles.items():
            effects = visible_tile.effects
            for elem in effects:
                if elem.type == "mist":
                    current_position = knowledge.position
                    distance_from_mnist = self.manhattan_distance(current_position, Coords(coords[0], coords[1]))
                    if distance_from_mnist < mist_arround_trehshold:
                        return True
        return False

    def manhattan_distance(self, pos1: Coords, pos2: Coords) -> int:
        # print(f"calcualting manhattan distance between {pos1}, {pos2}")
        dist = abs(pos1.x - pos2.x) + abs(pos1.y - pos2.y)
        # print(f"dist: {dist}")
        return dist

    def load_arena_to_graph(self):
        self.arena_graph = nx.Graph()

        for coord, tile in self.arena.terrain.items():
            # Dodajemy każdy wierzchołek, niezależnie od przechodniości
            self.arena_graph.add_node(coord)

            # Sprawdzamy tylko sąsiadów jeśli pole jest przechodnie
            if not tile.terrain_passable():
                continue

            if tile.description().type == "forest":
                self.forrest_tiles_list.append(coord)

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

        self.visited = set()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CamperBotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def find_menhir(self, knowledge: characters.ChampionKnowledge):
        for coords, visible_tile in knowledge.visible_tiles.items():
            if visible_tile.type == "menhir":
                self.is_menhir_found = True
                self.menhir_cords = coords

    def find_path(self, source: Coords, target: Coords):
        try:
            path = nx.shortest_path(self.arena_graph, source=source, target=target)
            return path[1:]
        except nx.NetworkXNoPath:
            return None
        except nx.NodeNotFound as e:
            return None

    def find_path_to_menhir(self, knowledge: characters.ChampionKnowledge):
        current_position = knowledge.position
        menhir_position = self.menhir_cords
        self.path_to_menhir = self.find_path(current_position, menhir_position)

    def find_path_to_forrest(self, knowledge: characters.ChampionKnowledge):
        current_position = knowledge.position
        closest_forrest = sorted(self.forrest_tiles_list, key=lambda x: self.manhattan_distance(current_position, x))[0]
        self.path_to_forrest = self.find_path(current_position, closest_forrest)

    def is_tile_mist(self, tile: tiles.TileDescription) -> bool:
        for elem in tile.effects:
            if elem.type == "mist":
                return True
        return False

    def is_tile_with_potion(self, tile: tiles.TileDescription) -> bool:
        if tile.consumable and tile.consumable.name == "potion":
            return True
        else:
            return False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        current_position = knowledge.position

        character = knowledge.visible_tiles[knowledge.position].character
        facing = character.facing
        self.seen.update(self.visible_cords(current_position, facing))

        self.visited.add(current_position)
        if not self.is_menhir_found:
            self.find_menhir(knowledge)

        possible_step_forward = current_position + self.step_forward(facing)
        possible_step_forward = Coords(possible_step_forward[0], possible_step_forward[1])

        possible_step_backward = current_position + self.step_backward(facing)
        possible_step_backward = Coords(possible_step_backward[0], possible_step_backward[1])

        possible_step_right = current_position + self.step_right(facing)
        possible_step_right = Coords(possible_step_right[0], possible_step_right[1])

        possible_step_left = current_position + self.step_left(facing)
        possible_step_left = Coords(possible_step_left[0], possible_step_left[1])

        tile_forward = knowledge.visible_tiles.get(possible_step_forward, None)
        tile_right = knowledge.visible_tiles.get(possible_step_right, None)
        tile_left = knowledge.visible_tiles.get(possible_step_left, None)
        tile_backward = knowledge.visible_tiles.get(possible_step_backward, None)

        if tile_forward and tile_forward.character and tile_forward.type != "forrest":
            return characters.Action.ATTACK
        elif tile_forward and tile_forward.character and tile_forward.type == "forrest":
            return characters.Action.STEP_BACKWARD
        if tile_right and tile_right.character:
            return characters.Action.TURN_RIGHT
        if tile_left and tile_left.character:
            return characters.Action.TURN_LEFT


        if tile_forward and self.is_tile_with_potion(tile_forward):
            return characters.Action.STEP_FORWARD
        if tile_right and self.is_tile_with_potion(tile_right):
            return characters.Action.STEP_RIGHT
        if tile_left and self.is_tile_with_potion(tile_left):
            return characters.Action.STEP_LEFT

        self.path_to_potion = None
        for crd, tile in knowledge.visible_tiles.items():
            if self.is_tile_with_potion(tile):
                self.path_to_potion = self.find_path(current_position, crd)
                break


        if not self.is_menhir_found:

            if self.is_mist_arround(knowledge, mist_arround_trehshold=4):
                if tile_forward and not self.is_tile_mist(tile_forward):
                    return characters.Action.STEP_FORWARD

                if tile_backward and not self.is_tile_mist(tile_backward):
                    return characters.Action.STEP_BACKWARD

                if tile_right and not self.is_tile_mist(tile_right):
                    return characters.Action.STEP_RIGHT

                if tile_left and not self.is_tile_mist(tile_left):
                    return characters.Action.STEP_LEFT
                # TODO: find a better way to escape form mnist

            if self.path_to_potion is not None and len(self.path_to_potion) > 0:
                next_tile = self.path_to_potion.pop(0)
                next_step_action = self.step_to_target(knowledge, next_tile)
                return next_step_action

            return self.explore(current_position, facing)

        else:
            # Going to forrest
            if self.go_to_forrest:
                # If we are in forrest na mnist arround - go to menhir
                if self.is_mist_arround(knowledge, mist_arround_trehshold=4):
                    self.find_path_to_menhir(knowledge)
                    next_tile = self.path_to_menhir.pop(0)
                    next_step_action = self.step_to_target(knowledge, next_tile)
                    self.go_to_forrest = False
                    self.go_to_menhir = True
                    return next_step_action

                if len(self.forrest_tiles_list) > 0 and self.path_to_forrest is None:
                    self.find_path_to_forrest(knowledge)
                # condition to stop going towards menhir as we are close
                if self.path_to_forrest is not None and len(self.path_to_forrest) > 0:
                    next_tile = self.path_to_forrest.pop(0)
                    next_step_action = self.step_to_target(knowledge, next_tile)
                    return next_step_action
                # searching for potion
                elif self.path_to_potion is not None and len(self.path_to_potion) > 0:
                    next_tile = self.path_to_potion.pop(0)
                    next_step_action = self.step_to_target(knowledge, next_tile)
                    return next_step_action
                # spinning around when we are close to menhir
                else:
                    return characters.Action.TURN_RIGHT

            # Going to menhir
            if self.go_to_menhir:
                if self.path_to_menhir is None:
                    self.find_path_to_menhir(knowledge)

                # Slow up going to menhir, until mist is close enough
                if self.is_mist_arround(knowledge, mist_arround_trehshold=4):
                    # condition to stop going towards menhir as we are close
                    if len(self.path_to_menhir) > 1:
                        next_tile = self.path_to_menhir.pop(0)
                        next_step_action = self.step_to_target(knowledge, next_tile)
                        return next_step_action
                    # spinning around when we are close to menhir
                else:
                    return random.choice(TURNING_ACTIONS)

    def step_to_target(self, knowledge: characters.ChampionKnowledge, next_position: Coords):
        "Chosing action to step toward target"
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
            return Coords(1, 0)
        elif facing == characters.Facing.LEFT:
            return Coords(-1, 0)
        elif facing == characters.Facing.UP:
            return Coords(0, -1)
        elif facing == characters.Facing.DOWN:
            return Coords(0, 1)

    def step_backward(self, facing):
        if facing == characters.Facing.RIGHT:
            return Coords(-1, 0)
        elif facing == characters.Facing.LEFT:
            return Coords(1, 0)
        elif facing == characters.Facing.UP:
            return Coords(0, 1)
        elif facing == characters.Facing.DOWN:
            return Coords(0, -1)

    def step_right(self, facing):
        if facing == characters.Facing.RIGHT:
            return Coords(0, 1)
        elif facing == characters.Facing.LEFT:
            return Coords(0, -1)
        elif facing == characters.Facing.UP:
            return Coords(1, 0)
        elif facing == characters.Facing.DOWN:
            return Coords(-1, 0)

    def step_left(self, facing):
        if facing == characters.Facing.RIGHT:
            return Coords(0, -1)
        elif facing == characters.Facing.LEFT:
            return Coords(0, 1)
        elif facing == characters.Facing.UP:
            return Coords(-1, 0)
        elif facing == characters.Facing.DOWN:
            return Coords(1, 0)

    def visible_cords(self, position: Coords, facing: characters.Facing):
        champion = characters.Champion(position, self.arena)
        champion.facing = facing
        return [coord for coord in self.arena.visible_tiles(champion).keys() if isinstance(coord, Coords)]

    def simulate_move(self, position: Coords, facing: characters.Facing, action: characters.Action):
        if action == characters.Action.STEP_BACKWARD:
            next_position, next_facing = position - facing.value, facing
        elif action == characters.Action.STEP_FORWARD:
            next_position, next_facing = position + facing.value, facing
        elif action == characters.Action.STEP_LEFT:
            next_position, next_facing = position + facing.turn_left().value, facing
        elif action == characters.Action.STEP_RIGHT:
            next_position, next_facing = position + facing.turn_right().value, facing
        elif action == characters.Action.TURN_LEFT:
            next_position, next_facing = position, facing.turn_left()
        elif action == characters.Action.TURN_RIGHT:
            next_position, next_facing = position, facing.turn_right()

        return next_position, next_facing

    def explore(self, position, facing, depth=3, discount=0.5):
        best_action = None
        best_value = -float("inf")

        for action in TURNING_ACTIONS + MOVEMENT_ACTIONS:
            value = self._estimate_future_gain(
                position,
                facing,
                action,
                remaining_depth=depth,
                discount=discount,
                already_seen=set(self.seen)  # copy
            )
            if value > best_value:
                best_value = value
                best_action = action
            elif value == best_value and np.random.uniform() > 0.5:
                best_value = value
                best_action = random.choice(TURNING_ACTIONS)
        return best_action


    def _estimate_future_gain(
        self,
        position,
        facing,
        action,
        remaining_depth,
        discount,
        already_seen
    ):

        next_position, next_facing = self.simulate_move(position, facing, action)


        if not self.arena.terrain.get(next_position, None) or not self.arena.terrain[next_position].passable:
            return 0

        visible_now = set(self.visible_cords(next_position, next_facing))
        new_here = visible_now - already_seen
        gain_here = len(new_here)

        if remaining_depth <= 1:
            return gain_here

        already_seen_next = already_seen.union(new_here)
        best_future = 0.0

        for next_action in TURNING_ACTIONS + MOVEMENT_ACTIONS:
            future_gain = self._estimate_future_gain(
                next_position,
                next_facing,
                next_action,
                remaining_depth=remaining_depth - 1,
                discount=discount,
                already_seen=already_seen_next
            )
            if future_gain > best_future:
                best_future = future_gain

        return gain_here + discount * best_future

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena_description = arena_description
        self.is_menhir_found = False
        self.menhir_cords = None
        self.visited = set()
        self.arena = arenas.Arena.load(arena_description.name)
        self.path_to_menhir = None
        self.arena_graph = None
        self.path_to_forrest = None
        self.forrest_tiles_list = []
        self.go_to_menhir = False
        self.go_to_forrest = True
        self.load_arena_to_graph()

    @property
    def name(self) -> str:
        return f"CamperBot{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.CAMPER


POTENTIAL_CONTROLLERS = [
    CamperBotController("V2"),
]

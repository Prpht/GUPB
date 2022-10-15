import numpy as np
from collections import deque
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import Coords
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid
from pathfinding.finder.a_star import AStarFinder
import pathfinding as pth

def save_method_returns(limit):
    def wrapper(method):
        def save(*args, **kwargs):
            obj_ref = args[0]
            if not hasattr(obj_ref, "saved_returns"):
                obj_ref.saved_returns = []

            result = method(*args, **kwargs)

            obj_ref.saved_returns.append(result)
            if len(obj_ref.saved_returns) > limit:
                obj_ref.saved_returns = obj_ref.saved_returns[1:]

            return result
        return save
    return wrapper


class KillerController(controller.Controller):

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.menhir_coordinates = None
        self.map = np.zeros(shape=(50, 50))
        self.saved_returns = []
        self.dead_ends = []
        self.turn_direction = Action.TURN_RIGHT
        # self.facing_position

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KillerController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def memorize_map(self, knowledge: characters.ChampionKnowledge):
        for coord, tile in knowledge.visible_tiles.items():
            if tile.type == "land":
                self.map[coord[0], coord[1]] = 1

    def find_path_to_menhir(self, knowledge: characters.ChampionKnowledge) -> Action:
        path = self.get_path(knowledge)
        current_facing = self.get_facing(knowledge)
        if path is not None and len(path) > 1:
            if current_facing.value + knowledge.position == path[1]:
                return Action.STEP_FORWARD
            else:
                if current_facing == Facing.UP:
                    if (Facing.RIGHT.value + knowledge.position == path[1]) or (Facing.DOWN.value + knowledge.position == path[1]):
                        return Action.TURN_RIGHT
                    else:
                        return Action.TURN_LEFT
                if current_facing == Facing.LEFT:
                    if (Facing.UP.value + knowledge.position == path[1]) or (Facing.RIGHT.value + knowledge.position == path[1]):
                        return Action.TURN_RIGHT
                    else:
                        return Action.TURN_LEFT
                if current_facing == Facing.DOWN:
                    if (Facing.LEFT.value + knowledge.position == path[1]) or (Facing.UP.value + knowledge.position == path[1]):
                        return Action.TURN_RIGHT
                    else:
                        return Action.TURN_LEFT
                if current_facing == Facing.RIGHT:
                    if (Facing.DOWN.value + knowledge.position == path[1]) or (Facing.LEFT.value + knowledge.position == path[1]):
                        return Action.TURN_RIGHT
                    else:
                        return Action.TURN_LEFT
        elif path is not None:
            return Action.ATTACK
        else:
            return Action.DO_NOTHING

    def get_path(self, knowledge: characters.ChampionKnowledge) -> list:
        queue = deque([[knowledge.position]])
        seen = set([knowledge.position])
        while queue:
            path = queue.popleft()
            x, y = path[-1]
            if self.map[y][x] == 2.:
                return [Coords(p[1], p[0]) for p in path] #to be swapped
            for x2, y2 in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                if 0 <= x2 < 50 and 0 <= y2 < 50 and self.map[y2][x2] != 0 and (x2, y2) not in seen:
                    queue.append(path + [(x2, y2)])
                    seen.add((x2, y2))

    # def get_path(self, knowledge: characters.ChampionKnowledge) -> list:
    #     map = Grid(self.map)
    #     start = map.node(knowledge.position.x, knowledge.position.y)
    #     end = map.node(self.menhir_coordinates[0], self.menhir_coordinates[1])
    #     finder = AStarFinder(diagonal_movement=DiagonalMovement.never)
    #     path, _ = finder.find_path(start, end, map)

    def get_facing(self, knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[knowledge.position].character.facing

    def noticed_menhir(self, knowledge: characters.ChampionKnowledge) -> bool:
        if self.menhir_coordinates is not None:
            return True
        else:
            visible_types = list(map(lambda tile: tile.type, knowledge.visible_tiles.values()))
            coordinates = knowledge.visible_tiles.keys()
            if "menhir" in visible_types:
                elements = dict(zip(visible_types, coordinates))
                self.menhir_coordinates = elements["menhir"]
                self.map[elements["menhir"]] = 2.
                self.memorize_map(knowledge)
                return True
            else:
                return False

    @save_method_returns(limit=2)
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.noticed_menhir(knowledge):
            what_to_do = self.find_path_to_menhir(knowledge)
            if what_to_do is not Action.DO_NOTHING:
                return what_to_do
            else:
                return self.wander(knowledge)
        else:
            return self.wander(knowledge)

    def wander(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        # The wandering algorithm is running in circles until we find a wall or enemy
        x = knowledge.position.x
        y = knowledge.position.y
        for dx, dy in ((1, 0), (0, 1), (-1, 0), (0, -1)):
            try:
                step_forward = Coords(x=x + dx, y=y + dy)
                if knowledge.visible_tiles[step_forward].type == "land":
                    if knowledge.visible_tiles[step_forward].character is not None:
                        return Action.ATTACK
                    else:
                        self.memorize_map(knowledge)
                        return Action.STEP_FORWARD
            except KeyError:
                pass

        self.memorize_map(knowledge)
        if knowledge.position in self.dead_ends:
            if self.turn_direction == Action.TURN_RIGHT:
                self.turn_direction = Action.TURN_LEFT
            else:
                self.turn_direction = Action.TURN_RIGHT
        else:
            if all(action == Action.TURN_RIGHT for action in self.saved_returns):
                self.dead_ends.append(knowledge.position)
            if all(action == Action.TURN_LEFT for action in self.saved_returns):
                self.dead_ends.append(knowledge.position)

        return self.turn_direction

    # def move_to_destination(self, knowledge: characters.ChampionKnowledge, coords: Coords):
    #     x = knowledge.position.x
    #     y = knowledge.position.y
    #     x_t = coords.x
    #     y_t = coords.y


    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED


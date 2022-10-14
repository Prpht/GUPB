import numpy as np

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action
from gupb.model.coordinates import Coords

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

    def is_path_to_menhir(self, coordinates):
        # TODO: implement
        return False

    def find_path_to_menhir(self, coordinates: Coords) -> Action:
        if self.is_path_to_menhir(coordinates):
            # TODO: implement
            pass
        else:
            return Action.DO_NOTHING

    def noticed_menhir(self, knowledge: characters.ChampionKnowledge) -> bool:
        if self.menhir_coordinates is not None:
            return True
        else:
            visible_types = list(map(lambda tile: tile.type, knowledge.visible_tiles.values()))
            coordinates = knowledge.visible_tiles.keys()
            if "menhir" in visible_types:
                elements = dict(zip(visible_types, coordinates))
                self.menhir_coordinates = elements["menhir"]
                self.memorize_map(knowledge)
                return True
            else:
                return False

    @save_method_returns(limit=2)
    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.noticed_menhir(knowledge):
            what_to_do = self.find_path_to_menhir(knowledge.position)
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


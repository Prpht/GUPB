import numpy as np
from enum import Enum
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action, Facing
from gupb.model.coordinates import add_coords
from .utils import KillerInterest, PathConstants, find_paths, path_to_actions


class KillerAction(Enum):
    DISCOVER = 0  # Find new point of interest on map
    FIND_PATH = 1  # Find actions to get to the destination
    FIND_VICTIM = 2  # Find path to enemy
    FIND_MENHIR = 3  # Find path to menhir if one exists
    LEARN_MAP = 4  # Invoke learn_map method
    LOOK_AROUND = 5  # Perform ('turn right', 'learn_map') 4 times


class KillerController(controller.Controller):

    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.game_map = None
        self.menhir_pos = None
        self.planned_actions = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KillerController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def learn_map(self, knowledge: characters.ChampionKnowledge) -> None:

        for coord, tile in knowledge.visible_tiles.items():
            if "mist" in list(map(lambda eff: eff.type, tile.effects)):
                self.game_map[coord[1], coord[0]] = PathConstants.MIST.value
                continue

            if tile.type == "land":
                self.game_map[coord[1], coord[0]] = PathConstants.WALKABLE.value
                if tile.character is not None:
                    if tile.character.controller_name != self.first_name:
                        self.game_map[coord[1], coord[0]] = KillerInterest.KILLING.value

            if self.menhir_pos is None:
                if tile.type == "menhir":
                    self.game_map[coord[1], coord[0]] = KillerInterest.MENHIR.value
                    self.menhir_pos = coord[0], coord[1]

    def update_map(self,
                   knowledge: characters.ChampionKnowledge,
                   current_interest: KillerInterest) -> None:
        # to do: Update only player locations (not the whole map)
        pass

    def find_new_interest(self, curr_position):
        x_max, y_max = self.game_map.shape
        map = self.game_map.copy()
        map[curr_position] = 0
        stack = [curr_position]
        distances = []
        get_distance = lambda z: np.sqrt(z[0]**2 + z[1]**2)
        while stack:
            coords = stack.pop()
            if coords[0] - 1 >= 0 and map[coords[0] - 1, coords[1]] == 1:
                new_coords = coords[0] - 1, coords[1]
                map[new_coords] = 0
                distances.append((new_coords, get_distance(new_coords)))
                stack.append(new_coords)
            if coords[0] + 1 < x_max and map[coords[0] + 1, coords[1]] == 1:
                new_coords = coords[0] + 1, coords[1]
                map[new_coords] = 0
                distances.append((new_coords, get_distance(new_coords)))
                stack.append(new_coords)
            if coords[1] - 1 >= 0 and map[coords[0], coords[1] - 1] == 1:
                new_coords = coords[0], coords[1] - 1
                map[new_coords] = 0
                distances.append((new_coords, get_distance(new_coords)))
                stack.append(new_coords)
            if coords[1] + 1 < y_max and map[coords[0], coords[1] + 1] == 1:
                new_coords = coords[0], coords[1] + 1
                map[new_coords] = 0
                distances.append((new_coords, get_distance(new_coords)))
                stack.append(new_coords)
        if distances:
            self.game_map[sorted(distances, key=lambda x: x[1])[-1][0]] = 2

    @staticmethod
    def get_facing(knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[knowledge.position].character.facing

    @staticmethod
    def get_facing_element(knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[add_coords(knowledge.position,
                                                  KillerController.get_facing(knowledge).value)]

    def find_path(self, knowledge: characters.ChampionKnowledge, interest: KillerInterest = None):
        # Path finding
        pos_x, pos_y = knowledge.position[0], knowledge.position[1]
        paths = find_paths(arr=self.game_map, curr_pos=(pos_y, pos_x))
        if interest is not None:
            found_path = paths.get_best_path(val_from=interest.value,
                                             val_to=interest.value)
        else:
            found_path = paths.get_best_path(val_from=KillerInterest.POINT_ON_MAP.value,
                                             val_to=KillerInterest.MENHIR.value)

        # Getting actions for found path
        facing = self.get_facing(knowledge)
        if facing == Facing.UP:
            curr_direction = -1, 0
        elif facing == Facing.DOWN:
            curr_direction = 1, 0
        elif facing == Facing.LEFT:
            curr_direction = 0, -1
        else:  # facing == Facing.RIGHT
            curr_direction = 0, 1
        actions = path_to_actions(initial_direction=curr_direction, path=found_path)
        self.planned_actions += actions

    def execute_action(self, action: KillerAction, knowledge: characters.ChampionKnowledge):
        if action == KillerAction.LEARN_MAP:
            self.learn_map(knowledge)

        if action == KillerAction.LOOK_AROUND:
            self.planned_actions += 4 * [Action.TURN_RIGHT, KillerAction.LEARN_MAP]

        if action == KillerAction.FIND_VICTIM:
            self.find_path(knowledge, interest=KillerInterest.KILLING)

        if action == KillerAction.FIND_MENHIR:
            self.find_path(knowledge, interest=KillerInterest.MENHIR)

        if action == KillerAction.DISCOVER:
            self.find_new_interest(curr_position=knowledge.position)
            self.find_path(knowledge, interest=KillerInterest.POINT_ON_MAP)

    # def check_for_enemies(self, knowledge: characters.ChampionKnowledge):
    #     #mark enemies
    #     are_enemies = False
    #     for coords, value in knowledge.visible_tiles.items():
    #         if value.character is not None and value.character.controller_name != 'Killer':
    #             self.game_map[coords] = KillerInterest.KILLING.value
    #             are_enemies = True
    #     return are_enemies

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        facing_element = self.get_facing_element(knowledge)
        if facing_element.character is not None:
            return Action.ATTACK

        if self.game_map is None:
            self.game_map = np.zeros(shape=(50, 50))
            self.execute_action(KillerAction.LOOK_AROUND, knowledge)

        self.learn_map(knowledge)

        if self.menhir_pos == knowledge.position:
            return Action.TURN_RIGHT

        if len(self.planned_actions) == 0:
            self.find_path(knowledge)
        while len(self.planned_actions) > 0:
            action = self.planned_actions.pop(0)
            if isinstance(action, KillerAction):
                self.execute_action(action, knowledge)
            else:
                return action
        else:
            return Action.TURN_RIGHT

    def praise(self, score: int) -> None:
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.game_map = None
        self.menhir_pos = None
        self.planned_actions = []

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.RED


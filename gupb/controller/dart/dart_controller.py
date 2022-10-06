import random

from gupb import controller
from gupb.controller.dart.arena_knowledge import ArenaKnowledge
from gupb.model import arenas, coordinates
from gupb.model import characters

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class DartController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena_knowledge = None
        self.path = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, DartController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.path is None:
            self.path = self.arena_knowledge.find_path(knowledge.position, coordinates.Coords(15,2))
        
        next_position = coordinates.Coords(*self.path[0])
        desired_facing = self.arena_knowledge.get_desired_facing(knowledge.position, next_position)
        current_facing = self.arena_knowledge.get_facing(knowledge)
        desired_action = self.arena_knowledge.determine_action(current_facing, desired_facing)
        if desired_action == characters.Action.STEP_FORWARD:
            self.path.pop(0)
        print("decide!!!")
        return desired_action

    def praise(self, score: int) -> None:
        print("praise!!!!")
        pass

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        print("reset!!!")
        self.arena_knowledge = ArenaKnowledge(arena_description)

        pass

    @property
    def name(self) -> str:
        return f'DartController{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW

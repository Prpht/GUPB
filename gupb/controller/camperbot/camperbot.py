from gupb import controller
from gupb.model import arenas
from gupb.model import characters
import random

from gupb.model.coordinates import Coords


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

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CamperBotController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)


    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        current_position = knowledge.position
        character = knowledge.visible_tiles[knowledge.position].character
        facing = character.facing

        self.visited.append(current_position)



        for coords, visible_tile in knowledge.visible_tiles.items():
            if visible_tile.type == 'menhir':
                self.is_menhir_found = True
                self.menhir_cords = coords


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

            return random.choice(POSSIBLE_ACTIONS[:-2])


    def step_forward(self, facing):
        if facing == characters.Facing.RIGHT:
            return Coords(1,0)
        elif facing == characters.Facing.LEFT:
            return Coords(-1,0)
        elif facing == characters.Facing.UP:
            return Coords(0,-1)
        elif facing == characters.Facing.DOWN:
            return Coords(0,1)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena_description = arena_description
        self.is_menhir_found = False
        self.menhir_cords = None
        self.visited = []
        pass

    @property
    def name(self) -> str:
        return f'CamperBot{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.CAMPER


POTENTIAL_CONTROLLERS = [
    CamperBotController("V0"),
]

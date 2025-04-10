from prompt_toolkit.styles import Priority

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
import random

from gupb.model.coordinates import Coords


TURNING_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT
]
MOVEMENT_ACTIONS = [
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.STEP_BACKWARD
]
ATTACK_ACTIONS = [
    characters.Action.ATTACK,
]



class CamperBotController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena_description = None
        self.is_menhir_found = False
        self.menhir_cords = None
        self.visited = set()

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
        self.visited.add(current_position)

        for coords, visible_tile in knowledge.visible_tiles.items():
            if visible_tile.type == 'menhir':
                self.is_menhir_found = True
                self.menhir_cords = coords

        possible_step_forward = current_position + self.step_forward(facing)
        possible_step_forward = Coords(possible_step_forward[0], possible_step_forward[1])

        possible_step_right = current_position + self.step_right(facing)
        possible_step_right = Coords(possible_step_right[0], possible_step_right[1])

        possible_step_left = current_position + self.step_left(facing)
        possible_step_left = Coords(possible_step_left[0], possible_step_left[1])

        priority_actions = []
        secondary_actions = TURNING_ACTIONS.copy()

        if not self.is_menhir_found:

            tile_forward = knowledge.visible_tiles.get(possible_step_forward, None)
            tile_right = knowledge.visible_tiles.get(possible_step_right, None)
            tile_left = knowledge.visible_tiles.get(possible_step_left, None)

            if tile_forward and tile_forward.character:
                return characters.Action.ATTACK
            if tile_right and tile_right.character:
                return characters.Action.TURN_RIGHT
            if tile_left and tile_left.character:
                return characters.Action.TURN_LEFT

            if tile_forward and tile_forward.type not in ['sea', 'wall']:
                if possible_step_forward not in self.visited:
                    priority_actions.append(characters.Action.STEP_FORWARD)
                else:
                    secondary_actions.append(characters.Action.STEP_FORWARD)

            if tile_right and tile_right.type not in ['sea', 'wall']:
                if possible_step_right not in self.visited:
                    priority_actions.append(characters.Action.STEP_RIGHT)
                else:
                    secondary_actions.append(characters.Action.STEP_RIGHT)

            if tile_left and tile_left.type not in ['sea', 'wall']:
                if possible_step_left not in self.visited:
                    priority_actions.append(characters.Action.STEP_LEFT)
                else:
                    secondary_actions.append(characters.Action.STEP_LEFT)

            if priority_actions:
                return random.choice(priority_actions)
            elif len(secondary_actions) > 2:
                return random.choice(secondary_actions)
            else:
                return characters.Action.STEP_BACKWARD

        else:
            return random.choice(TURNING_ACTIONS)

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
        self.visited = set()
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

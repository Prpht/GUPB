import random
import numpy as np

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.characters import Action
from gupb.model.characters import Facing

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Spejson(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.facing = None
        self.move_number = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Spejson):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.move_number += 1
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles

        available_actions = POSSIBLE_ACTIONS.copy()

        if self.facing is None:
            # Infer direction if not known yet. TODO: May or may not work if spawned facing a wall
            n = len(visible_tiles)
            sum_x, sum_y = 0, 0

            for pos in visible_tiles:
                sum_x += pos[0]
                sum_y += pos[1]

            angle = np.angle(sum_x / n - position[0] + (sum_y / n - position[1]) * 1j)
            inferred_dir = int(np.floor(2 * (1.25 + angle / 3.14) % 4))
            self.facing = [Facing.LEFT, Facing.UP, Facing.RIGHT, Facing.DOWN][inferred_dir]

        # Rule out stupid moves
        next_block = position + self.facing.value
        if next_block in visible_tiles:
            if visible_tiles[next_block].type in ['sea', 'wall']:
                available_actions = [x for x in available_actions if x not in [Action.STEP_FORWARD, Action.ATTACK]]
            if visible_tiles[next_block].character is None:
                available_actions = [x for x in available_actions if x not in [Action.ATTACK]]
            if visible_tiles[next_block].character is not None:
                available_actions = [Action.ATTACK]

        # Make move
        move = random.choice(available_actions)

        if move == Action.TURN_LEFT:
            self.facing = self.facing.turn_left()
        elif move == Action.TURN_RIGHT:
            self.facing = self.facing.turn_right()

        return move

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
    Spejson("Spejson"),
]

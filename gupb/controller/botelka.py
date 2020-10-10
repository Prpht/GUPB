import operator
from typing import Dict, List

from gupb.model.arenas import ArenaDescription
from gupb.model.characters import Facing, Action, ChampionKnowledge

from gupb.model.tiles import TileDescription


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class BotElkaController:
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.directions_info: Dict[Facing, int] = {
            Facing.UP: 0, Facing.LEFT: 0, Facing.RIGHT: 0, Facing.DOWN: 0
        }
        self.moves_queue: List[Action] = []
        self.counter: int = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, BotElkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: ArenaDescription) -> None:
        pass

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        if self.moves_queue:
            return self.moves_queue.pop(0)

        # Determine current Facing of the bot
        current_facing = self.get_current_facing(knowledge)

        # Count how many save tiles Bot can see in given direction
        self.directions_info[current_facing] = len([
            visible_tile
            for visible_tile in knowledge.visible_tiles.values()
            if _is_safe_land(visible_tile)
        ])

        self.control_movement(current_facing)

        return self.moves_queue.pop(0)

    def get_current_facing(self, knowledge: ChampionKnowledge) -> Facing:
        facing = next(
            (visible_tile.character.facing
             for visible_tile in knowledge.visible_tiles.values()
             if visible_tile.character and visible_tile.character.controller_name == self.name), None
        )

        assert facing, "Bot facing always present"

        return facing

    def control_movement(self, current_facing: Facing) -> None:
        self.counter += 1

        if self.counter != 4:
            # Bot needs to spin around, to see whats is around it
            self.moves_queue.append(Action.TURN_RIGHT)
            return

        self.counter = 0
        # Calculate the best direction to run away
        desired_direction = max(self.directions_info.items(), key=operator.itemgetter(1))[0]
        self.moves_queue += self.rotate_character(current_facing, desired_direction)
        self.moves_queue.append(Action.STEP_FORWARD)

    def rotate_character(self, starting_facing: Facing, desired_facing: Facing) -> List[Action]:
        """
        Rotate character until starting position becomes desired position.
        """
        result = []

        right_side_transitions = {
            Facing.UP: Facing.RIGHT,
            Facing.RIGHT: Facing.DOWN,
            Facing.DOWN: Facing.LEFT,
            Facing.LEFT: Facing.UP,
        }

        while starting_facing != desired_facing:
            result.append(Action.TURN_RIGHT)
            starting_facing = right_side_transitions[starting_facing]

        return result

    @property
    def name(self) -> str:
        return f"BotElka{self.first_name}"


def _is_safe_land(visible_tile: TileDescription) -> bool:
    dangerous_effects = [
        effect for effect in visible_tile.effects if effect.type == "mist"
    ]
    if dangerous_effects:
        return False

    if visible_tile.type != "land":
        return False

    return True


POTENTIAL_CONTROLLERS = [
    BotElkaController("")
]

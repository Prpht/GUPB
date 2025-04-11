import random

from gupb import controller
from gupb.model import arenas, characters, coordinates


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class GarekController(controller.Controller):
    """
    G.A.R.E.K. - Game Agent Reinforcement Exploration Kernel
    """

    def __init__(self, first_name: str):
        self.first_name: str = first_name

    def __eq__(self, other: object) -> bool:
        if isinstance(other, GarekController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        current_pos = knowledge.position
        visible_tiles = knowledge.visible_tiles

        # Get current tile and facing
        current_tile = visible_tiles.get(current_pos)
        if not current_tile or not current_tile.character:
            return random.choice(POSSIBLE_ACTIONS)

        current_facing = current_tile.character.facing
        current_has_mist = any(effect.type == 'mist' for effect in current_tile.effects)

        # Directions for possible steps
        step_actions = [
            (characters.Action.STEP_FORWARD, current_facing.value),
            (characters.Action.STEP_BACKWARD, current_facing.opposite().value),
            (characters.Action.STEP_LEFT, current_facing.turn_left().value),
            (characters.Action.STEP_RIGHT, current_facing.turn_right().value),
        ]

        safe_actions = []
        for action, direction in step_actions:
            new_x = current_pos.x + direction.x
            new_y = current_pos.y + direction.y
            new_pos = coordinates.Coords(new_x, new_y)
            tile = visible_tiles.get(new_pos)
            if tile:
                # Check if tile is safe: passable, no character, no mist
                passable = tile.type in ['land', 'forest', 'menhir']
                no_character = tile.character is None
                no_mist = all(effect.type != 'mist' for effect in tile.effects)
                if passable and no_character and no_mist:
                    safe_actions.append(action)

        # Prioritize escaping mist if present
        if current_has_mist:
            if safe_actions:
                return safe_actions[0]  # Prefer first safe action
            else:
                return random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])
        else:
            if safe_actions:
                # Introduce randomness to avoid loops
                random.shuffle(safe_actions)
                return safe_actions[0]
            else:
                # No safe moves, random turn
                return random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        pass

    @property
    def name(self) -> str:
        return f'G.A.R.E.K. {self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.GAREK


POTENTIAL_CONTROLLERS = [
    GarekController("The Great"),
    GarekController("Exterminator"),
    GarekController("The Conqueror"),
]

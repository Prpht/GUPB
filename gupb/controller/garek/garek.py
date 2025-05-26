import random
import numpy as np

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

MIST_HORIZON_RADIUS = 10  # How far to scan for mist


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

        current_tile = visible_tiles.get(current_pos)
        if not current_tile or not current_tile.character:
            return random.choice(POSSIBLE_ACTIONS)
        current_facing = current_tile.character.facing

        # Scan for mist in a radius
        mist_coords = []
        for dx in range(-MIST_HORIZON_RADIUS, MIST_HORIZON_RADIUS + 1):
            for dy in range(-MIST_HORIZON_RADIUS, MIST_HORIZON_RADIUS + 1):
                check_pos = coordinates.Coords(current_pos.x + dx, current_pos.y + dy)
                tile = visible_tiles.get(check_pos)
                if tile and any(effect.type == 'mist' for effect in tile.effects):
                    mist_coords.append(np.array([check_pos.x, check_pos.y]))

        # Calculate mist avoidance vector
        flee_vector = np.array([0.0, 0.0])
        if mist_coords:
            mist_center = np.mean(mist_coords, axis=0)
            my_pos = np.array([current_pos.x, current_pos.y])
            flee_vector = my_pos - mist_center
            norm = np.linalg.norm(flee_vector)
            if norm > 0:
                flee_vector = flee_vector / norm

        # Directions for possible steps
        step_actions = [
            (characters.Action.STEP_FORWARD, current_facing.value),
            (characters.Action.STEP_BACKWARD, current_facing.opposite().value),
            (characters.Action.STEP_LEFT, current_facing.turn_left().value),
            (characters.Action.STEP_RIGHT, current_facing.turn_right().value),
        ]

        best_action = None
        best_score = -float('inf')
        safe_actions = []
        for action, direction in step_actions:
            new_x = current_pos.x + direction.x
            new_y = current_pos.y + direction.y
            new_pos = coordinates.Coords(new_x, new_y)
            tile = visible_tiles.get(new_pos)
            if tile:
                passable = tile.type in ['land', 'forest', 'menhir']
                no_character = tile.character is None
                no_mist = all(effect.type != 'mist' for effect in tile.effects)
                if passable and no_character and no_mist:
                    safe_actions.append(action)
                    # If mist is present, prefer moves that go away from mist
                    if mist_coords:
                        move_vec = np.array([new_x, new_y]) - np.array([current_pos.x, current_pos.y])
                        score = np.dot(move_vec, flee_vector)
                        # Prefer forest tiles for extra safety
                        if tile.type == 'forest':
                            score += 0.2
                        if score > best_score:
                            best_score = score
                            best_action = action
        if mist_coords and best_action is not None:
            return best_action
        if safe_actions:
            return self._pick_safe_action(safe_actions)
        else:
            return random.choice(POSSIBLE_ACTIONS)

    def _pick_safe_action(self, safe_actions: list[characters.Action]) -> characters.Action:
        if random.random() > 0.8:
            return safe_actions[0]  # 80% chance to pick the first safe action
        else:
            return random.choice(safe_actions) # 20% chance to pick a random safe action

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
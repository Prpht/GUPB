import math
import random
from queue import SimpleQueue
from typing import Dict, List, Optional

from gupb.model import arenas, coordinates, tiles
from gupb.model import characters
from gupb.model.characters import Action
from gupb.model.coordinates import add_coords
from . import utils
from .knowledge import Knowledge
from .. import Controller

__all__ = ["Krowa1233Controller"]

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Krowa1233Controller(Controller):
    def __init__(self, first_name: str):
        self.action_queue: SimpleQueue[Action] = SimpleQueue()
        self.first_name: str = first_name
        self.knowledge: Optional[Knowledge] = None
        self.last_action: Optional[Action] = None
        self.last_position: Optional[coordinates.Coords] = None
        self.path = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Krowa1233Controller):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.knowledge = Knowledge(arena_description)
        self.last_action = None
        self.last_position = None

    def decide(self, knowledge: characters.ChampionKnowledge) -> Action:
        self.knowledge.update(knowledge)

        if self._mist_is_coming(knowledge.position, knowledge.visible_tiles):
            action = self._escape_from_mist(knowledge.position, knowledge.visible_tiles)
        elif self._check_if_hit(knowledge.visible_tiles):
            action = Action.ATTACK
        else:
            action = self._find_enemy()
        if action == self.last_action and knowledge.position == self.last_position:
            action = random.choice(POSSIBLE_ACTIONS[:-1])
        self.last_action = action
        self.last_position = knowledge.position
        return action

    def _check_if_hit(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        return len(self.knowledge.champions_to_attack()) > 0

    @property
    def name(self) -> str:
        return f'Krowa1233Controller{self.first_name}'

    def _mist_is_coming(
        self,
        champion_position: coordinates.Coords,
        visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]
    ) -> bool:
        to_check = [
            coordinates.Coords(
                x=champion_position.x + x_d,
                y=champion_position.y + y_d
            ) for x_d in range(-2, 3, 1) for y_d in range(-2, 3, 1)
        ]
        return self._mist_present(positions=to_check, visible_tiles=visible_tiles)

    def _mist_present(
        self,
        positions: List[coordinates.Coords],
        visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]
    ) -> bool:
        return any(
            any(e.type == "mist" for e in visible_tiles[position].effects)
            for position in positions
            if position in visible_tiles
        )

    def _escape_from_mist(
        self,
        champion_position: coordinates.Coords,
        visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]
    ) -> Action:
        forward_positions = [add_coords(champion_position, self.knowledge.facing.value)]
        forward_positions.append(add_coords(forward_positions[-1], self.knowledge.facing.value))
        forward_position_is_safe = not self._mist_present(forward_positions, visible_tiles)
        if forward_position_is_safe:
            return Action.STEP_FORWARD
        return random.choice(POSSIBLE_ACTIONS[:2])

    def _find_enemy(self) -> Action:
        enemies = utils.get_champion_positions(self.knowledge.visible_terrain())
        closest_enemy = self._find_closest_enemy(
            champion_position=self.knowledge.position, enemies_positions=enemies
        )
        if closest_enemy is None:
            return random.choice(POSSIBLE_ACTIONS[:-1])
        dx, dy = int((closest_enemy[0] - self.knowledge.position[0]) > 0), int((closest_enemy[1] - self.knowledge.position[1]) > 0)
        if dx == self.knowledge.facing.value.x or dy == self.knowledge.facing.value.y:
            return Action.STEP_FORWARD
        return random.choice(POSSIBLE_ACTIONS[:2])

    def _find_closest_enemy(
        self,
        champion_position: coordinates.Coords,
        enemies_positions: List[coordinates.Coords]
    ) -> Optional[coordinates.Coords]:
        if len(enemies_positions) == 0:
            return None
        distances = [
            (i, math.sqrt((e[0] - champion_position.x) ** 2 + (e[1] - champion_position.y) ** 2))
            for i, e in enumerate(enemies_positions)
        ]
        distances.sort(key=lambda d: d[1])
        return enemies_positions[distances[0][0]]

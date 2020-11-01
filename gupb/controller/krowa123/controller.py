import collections
import random
from typing import Dict, List, Optional, Type

from gupb.controller import Controller
from gupb.model import arenas, tiles
from gupb.model.characters import Action, ChampionKnowledge, Tabard
from gupb.model.coordinates import Coords
from gupb.model.weapons import Bow, Weapon
from . import utils
from .knowledge import Knowledge

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
        self.action_queue = collections.deque()
        self.first_name: str = first_name
        self.knowledge: Optional[Knowledge] = None
        self.last_action: Optional[Action] = None
        self.last_position: Optional[Coords] = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, Krowa1233Controller):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.knowledge = Knowledge(arena_description)
        self.action_queue = collections.deque()
        self.last_action = None
        self.last_position = None

    def path_to_weapon(self, weapon_name: str):
        return sorted([self.knowledge.find_path(self.knowledge.position, axe, False)
                       for axe in self.knowledge.loot([weapon_name])], key=lambda p: len(p))[0]

    def path_to_menhir(self):
        return self.knowledge.find_path(self.knowledge.position, self.knowledge.menhir_position)

    def find_dijkstra_to_menhir(
        self,
        weapons_to_take: List[Type[Weapon]],
        dist: int = 0,
        strict: bool = True
    ) -> List[Coords]:
        return self.knowledge.find_dijkstra_path(
            weapons_to_take=weapons_to_take,
            dist=dist,
            strict=strict
        )

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self.knowledge.update(knowledge)
        if len(self.action_queue) == 0 and self.last_action is None:
            path = self.knowledge.find_sneaky_path()
            if path is None:
                path = self.find_dijkstra_to_menhir(
                    weapons_to_take=[Bow]
                )
            self._plan_actions(path)
        elif len(self.action_queue) == 0:
            if self.knowledge.mist_radius > 30:
                self._plan_random_enemies_search()
            else:
                path = self.find_dijkstra_to_menhir(
                    weapons_to_take=[], dist=max(1, int(self.knowledge.mist_radius / 2))
                )
                self._plan_actions(path)
        if self._check_if_hit(knowledge.visible_tiles):
            action = Action.ATTACK
        else:
            action = self.action_queue.popleft() if len(self.action_queue) > 0 else Action.TURN_RIGHT
        self.last_action = action
        self.last_position = knowledge.position
        return action

    def _plan_actions(self, path: List[Coords]) -> None:
        self.action_queue = collections.deque()
        for action in utils.path_to_actions(self.knowledge.position, self.knowledge.facing, path):
            self.action_queue.append(action)

    def _plan_random_enemies_search(self) -> None:
        self.action_queue = collections.deque()
        for _ in range(4):
            self.action_queue.append(Action.TURN_RIGHT)
        for _ in range(random.randint(0, 3)):
            self.action_queue.append(Action.TURN_RIGHT)
        self.action_queue.append(Action.STEP_FORWARD)

    def _check_if_hit(self, visible_tiles: Dict[Coords, tiles.TileDescription]) -> bool:
        return len(self.knowledge.champions_to_attack()) > 0

    @property
    def name(self) -> str:
        return f'Krowa1233Controller{self.first_name}'

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.VIOLET

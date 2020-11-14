import collections
import random
from enum import Enum
from typing import Dict, List, Optional, Type

from gupb.controller import Controller
from gupb.model import arenas, tiles
from gupb.model.characters import Action, ChampionKnowledge, Tabard
from gupb.model.coordinates import Coords
from gupb.model.weapons import Bow, Weapon, Sword, Axe, Amulet, Knife
from . import utils
from .knowledge import Knowledge
import traceback
from timeit import default_timer as timer
import time


__all__ = ["Krowa1233Controller"]

POSSIBLE_ACTIONS = [
    Action.TURN_LEFT,
    Action.TURN_RIGHT,
    Action.STEP_FORWARD,
    Action.ATTACK,
]


class Goals(Enum):
    WEAPON = "Weapon"
    SAFE_SPOT = "SafeSpot"
    CAMP = "Camp"
    MENHIR = "Menhir"
    HUNT = "Hunt"


class GoalState(Enum):
    NOT_STARTED = "NotStarted"
    IN_PROGRESS = "InProgress"
    FINISHED = "Finished"
    FAILED = "Failed"
    IMPOSSIBLE = "Impossible"

    @staticmethod
    def end(finished: bool):
        return GoalState.FINISHED if finished else GoalState.FAILED


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class Krowa1233Controller(Controller):
    def __init__(self, first_name: str):
        self.action_queue = collections.deque()
        self.first_name: str = first_name
        self.knowledge: Optional[Knowledge] = None
        self.last_action: Optional[Action] = None
        self.last_position: Optional[Coords] = None
        self.last_weapon: Optional[Type[Weapon]] = Knife
        self.path = []
        self.goals = collections.defaultdict(lambda: [GoalState.NOT_STARTED, None])

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
        self.last_weapon: Optional[Type[Weapon]] = Knife
        self.goals = collections.defaultdict(lambda: [GoalState.NOT_STARTED, None])

    def path_to_weapon(self, weapon_name: str):
        return sorted([self.knowledge.find_path(self.knowledge.position, axe, False)
                       for axe in self.knowledge.loot([weapon_name])], key=lambda p: len(p))[0]

    def path_to_menhir(self):
        return self.knowledge.find_path(self.knowledge.position, self.knowledge.menhir_position)

    def find_dijkstra_to_menhir(
        self,
        weapons_to_take: List[Type[Weapon]],
        dist: int = 1,
        strict: bool = True
    ) -> List[Coords]:
        return self.knowledge.find_dijkstra_path(
            weapons_to_take=weapons_to_take,
            target=self.knowledge.menhir_position,
            dist=dist,
            strict=strict
        )

    def find_dijkstra(
        self,
        weapons_to_take: List[Type[Weapon]],
        target: Coords,
        dist: int = 0,
        strict: bool = True
    ) -> List[Coords]:
        return self.knowledge.find_dijkstra_path(
            weapons_to_take=weapons_to_take,
            target=target,
            dist=dist,
            strict=strict
        )

    def get_weapon(self):
        weapon_distances = self.knowledge.weapon_distances()

        def valid(w):
            return w if (w and w[1][0] + w[1][1] <= self.knowledge.mist_radius * 3) else None

        bow = next(map(lambda d: (Bow, d), weapon_distances[Bow]), None)
        sword = next(map(lambda d: (Sword, d), weapon_distances[Sword]), None)
        axe = next(map(lambda d: (Axe, d), weapon_distances[Axe]), None)
        amulet = next(map(lambda d: (Amulet, d), weapon_distances[Amulet]), None)
        weapon = valid(bow) or valid(sword) or valid(axe) or valid(amulet)

        if weapon:
            path = self.knowledge.find_path(self.knowledge.position, weapon[1][2], False)
            if path:
                self.goals[Goals.WEAPON] = [GoalState.IN_PROGRESS, weapon[1][2], weapon[0]]
                self._plan_actions(path)
                return
        self.goals[Goals.WEAPON] = [GoalState.IMPOSSIBLE]

    def go_to_sneaky_point(self):
        def valid(sp):
            return sp if (sp[1][0] + sp[1][1] < self.knowledge.mist_radius) else None

        sneaky_points = sorted(filter(valid, self.knowledge.sneaky_point_distances().items()), key=lambda x: x[1][0])

        for sneaky_point in sneaky_points:
            if not self.knowledge.check_loot(sneaky_point[0]) or self.knowledge.check_loot(sneaky_point[0], self.knowledge.weapon_type):
                if sneaky_point[1][0] == self.knowledge.position and sneaky_point[1][1] < (self.knowledge.mist_radius - 5):
                    return
                else:
                    path = self.find_dijkstra([], sneaky_point[0])
                    if path:
                        self.goals[Goals.SAFE_SPOT] = [GoalState.IN_PROGRESS, sneaky_point[0]]
                        self._plan_actions(path)
                        return

        # print("SAFE SPOT IMPOSSILBE")
        self.goals[Goals.SAFE_SPOT] = [GoalState.IMPOSSIBLE]

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        try:
            self.knowledge.update(knowledge)
            if self.goals[Goals.WEAPON][0] == GoalState.FINISHED:
                if self.goals[Goals.WEAPON][2] != self.knowledge.weapon_type and self.knowledge.weapon_type != self.last_weapon:
                    path = [self.last_position, self.knowledge.position]
                    self.action_queue.extendleft(utils.path_to_actions(self.knowledge.position, self.knowledge.facing, path))
            if self.goals[Goals.WEAPON][0] == GoalState.IN_PROGRESS:
                if self.goals[Goals.WEAPON][1] == self.knowledge.position:
                    self.goals[Goals.WEAPON][0] = GoalState.end(self.goals[Goals.WEAPON][2] == self.knowledge.weapon_type)
                elif not self.knowledge.check_loot(*self.goals[Goals.WEAPON][1:]):
                    self.goals[Goals.WEAPON][0] = GoalState.FAILED
                    self.get_weapon()
            if self.goals[Goals.WEAPON][0] == GoalState.NOT_STARTED:
                self.get_weapon()

            if len(self.action_queue) == 0:
                if self.goals[Goals.SAFE_SPOT][0] == GoalState.IN_PROGRESS:
                    if self.goals[Goals.SAFE_SPOT][1] == self.knowledge.position:
                        self.goals[Goals.SAFE_SPOT][0] = GoalState.FINISHED
                elif self.goals[Goals.SAFE_SPOT][0] != GoalState.IMPOSSIBLE:
                    self.go_to_sneaky_point()
                if self.goals[Goals.SAFE_SPOT][0] == GoalState.IMPOSSIBLE:
                    if self.knowledge.mist_radius > 10:
                        path = self.find_dijkstra_to_menhir(
                            weapons_to_take=[], dist=max(1, int(self.knowledge.mist_radius / 2))
                        )
                        self._plan_actions(path)
                    else:
                        path = self.find_dijkstra_to_menhir(
                            weapons_to_take=[], dist=min(4, int(self.knowledge.mist_radius - 1))
                        )
                        self._plan_actions(path)
            if self._check_if_hit(knowledge.visible_tiles):
                action = Action.ATTACK
            elif self._check_if_under_attack():
                action = Action.DO_NOTHING
            elif len(self.action_queue) > 0:
                self.goals[Goals.CAMP] = [GoalState.FINISHED, None]
                action = self.action_queue.popleft()
            else:
                last_turn = self.goals[Goals.CAMP][1]
                turn_left = self.knowledge.tile_on_left().terrain_transparent()
                turn_right = self.knowledge.tile_on_right().terrain_transparent()

                if last_turn == Action.TURN_LEFT:
                    action = Action.TURN_LEFT if turn_left else Action.TURN_RIGHT
                else:
                    action = Action.TURN_RIGHT if turn_right else Action.TURN_LEFT
                self.goals[Goals.CAMP] = [GoalState.IN_PROGRESS, action]

            self.last_action = action
            self.last_position = knowledge.position
            self.last_weapon = self.knowledge.weapon_type
            return action
        except Exception as e:
            traceback.print_exc()
            return Action.DO_NOTHING


    def _plan_actions(self, path: List[Coords]) -> None:
        self.action_queue = collections.deque()
        self.path = path
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

    def _check_if_under_attack(self) -> bool:
        return False

    @property
    def name(self) -> str:
        return f'Krowa1233Controller{self.first_name}'

    @property
    def preferred_tabard(self) -> Tabard:
        return Tabard.VIOLET

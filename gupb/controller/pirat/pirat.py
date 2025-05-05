import random
from typing import List, Dict, Tuple

from gupb.model import coordinates
from gupb.model import tiles
from gupb.controller.pirat.menhir_finder2 import MenhirFinder2

from gupb.controller.pirat.pathfinding import PathFinder
from gupb.controller.pirat.weapon_act import WeaponDecider


from gupb import controller
from gupb.model import arenas
from gupb.model.arenas import ArenaDescription, Arena
from gupb.model import characters
import random
from gupb.controller.pirat.mist_detector import MistDetector

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.ATTACK,
    characters.Action.DO_NOTHING,
]


# noinspection PyUnusedLocal
# noinspection PyMethodMayBeStatic
class PiratController(controller.Controller):
    def __init__(self, first_name: str, threeshold = 0, reset = None, dynamic_reg = False, region_size = 5, rand_turn = 0, percent_of_route = 1, in_all_turn = False):
        self.first_name: str = first_name
        self.menhir_finder = None
        self.arena: Arena = None
        self.actual_path: List[coordinates.Coords] = []
        self.region_size = region_size
        self.dynamic_reg = dynamic_reg
        self.hero = None
        self.threeshold = threeshold
        self.i = 0
        self.res = reset
        self.rand_turn = rand_turn
        self.mist_detector = None
        self.percent_of_route = percent_of_route
        self.prob_in_turn = in_all_turn


    def __eq__(self, other: object) -> bool:
        if isinstance(other, PiratController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def update_info(self, knowledge: characters.ChampionKnowledge) -> None:
        hero: characters.ChampionDescription = knowledge.visible_tiles[
            knowledge.position
        ].character
        self.hero = hero

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.update_info(knowledge)
        try:
            if self.i == 0:
                weapon_decider = WeaponDecider(self.arena)
                path = weapon_decider.check_if_need_to_go(knowledge.position, self.path_finder)
                self.actual_path = path
                

            self.i += 1
            mist_escape_path = self.mist_detector.update(knowledge)

        except Exception as e:
            import traceback
            traceback.print_exc()
            mist_escape_path = None
            if self.menhir_finder.menhir is None:
                self.menhir_finder.look_for_menhir(knowledge.visible_tiles)
                if self.res != None and self.i % self.res == 0:
                    self.actual_path = []

        try:
           

            # Priority: menhir

            character = self._check_if_facing_opponent(knowledge)
            if character is not None:
                return characters.Action.ATTACK

            if self.menhir_finder.menhir is not None:
                if knowledge.position == self.menhir_finder.menhir:
                    return random.choice([characters.Action.ATTACK, characters.Action.ATTACK, characters.Action.TURN_LEFT])
                if mist_escape_path:
                    self.actual_path = mist_escape_path
                    return self._move_along_path(knowledge)
                else:
                    return self._move_towards_menhir(knowledge)

            # Priority: escaping mists

            if mist_escape_path:
                self.actual_path = mist_escape_path
                return self._move_along_path(knowledge)


            if self.menhir_finder.menhir is None:
                self.menhir_finder.look_for_menhir(knowledge.visible_tiles)
                if self.res != None and self.i % self.res == 0:
                    self.actual_path = []

                if len(self.actual_path) < self.threeshold:
                    self.actual_path = []

                if self.actual_path:
                    if random.random() < self.rand_turn:
                        return characters.Action.TURN_LEFT
                    move = self._move_along_path(knowledge)
                    return move
                    
                else:
                    reg = self.menhir_finder.get_max_probability_region()
                    end = self.get_first_standable_tile(reg)
                    start = knowledge.position

                    new_path = self.path_finder.find_the_shortest_path(start, end)
                    self.actual_path = new_path
            
        except Exception as e:
            print(f"Error updating mist detector: {e}")



        return random.choice(POSSIBLE_ACTIONS)
    
    def _check_if_facing_opponent(self, knowledge: characters.ChampionKnowledge):
        return knowledge.visible_tiles[(self.hero.facing.value + knowledge.position)].character
    

    def _move_along_path(
        self, knowledge: characters.ChampionKnowledge
    ) -> characters.Action:
        next_coord = self.actual_path[0]
        delta_x = next_coord.x - knowledge.position.x
        delta_y = next_coord.y - knowledge.position.y
        delta = coordinates.Coords(delta_x, delta_y)

        if delta == (0, 0):
            self.actual_path.pop(0)
            if not self.actual_path:
                return characters.Action.DO_NOTHING
            next_coord = self.actual_path[0]
            delta_x = next_coord.x - knowledge.position.x
            delta_y = next_coord.y - knowledge.position.y
            delta = coordinates.Coords(delta_x, delta_y)

        if delta == self.hero.facing.value:
            if not self.actual_path:
                self.current_target = None
            return characters.Action.STEP_FORWARD
        elif delta == self.hero.facing.turn_left().value:
            return characters.Action.TURN_LEFT
        elif delta == self.hero.facing.turn_right().value:
            return characters.Action.TURN_RIGHT
        else:
            return characters.Action.TURN_LEFT

    def _move_towards_menhir(
        self, knowledge: characters.ChampionKnowledge
    ) -> characters.Action:

        if not self.actual_path:
            start = knowledge.position
            end = self.menhir_finder.menhir
            new_path = self.path_finder.find_the_shortest_path(start, end)
            self.actual_path = new_path
            
        return self._move_along_path(knowledge)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena = arenas.Arena.load(arena_description.name)
        self.menhir_finder = MenhirFinder2(arena=self.arena)
        self.path_finder = PathFinder(arena=self.arena)
        self.actual_path = []
        self.mist_detector = MistDetector(self.arena)
        if self.dynamic_reg:
            self.region_size = self.arena.size[0] // 5
        self.i = 0
        pass

        


    def get_first_standable_tile(self, region: Tuple[int, int]) -> coordinates.Coords:
        x_start = region[0] * self.region_size
        y_start = region[1] * self.region_size
        x_end = x_start + self.region_size
        y_end = y_start + self.region_size

        for x in range(x_start, x_end):
            for y in range(y_start, y_end):
                pos = coordinates.Coords(x, y)
                if self.arena.terrain[pos].terrain_passable():
                    return pos
        return None

    @property
    def name(self) -> str:
        return f"PiratController{self.first_name}"

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PIRAT


POTENTIAL_CONTROLLERS = [
    PiratController("Pirat"),
]

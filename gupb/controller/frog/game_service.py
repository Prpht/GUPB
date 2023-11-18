from .world_service import WorldService
from gupb.model import arenas
from gupb.model.coordinates import Coords
from gupb.model.characters import Facing, Action
from .decision_utils import get_furthest_coord, get_menhir, get_nearby_potions, get_nearby_characters, is_in_path

from enum import Enum


class CurrentState(Enum):
    CHILLING = 0
    MOVING = 1
    EXPLORING = 2
    LOOTING = 3
    ATTACKING = 4
    CAMPING = 5
    STUCK = 6


class State:
    def __init__(self, arena_name=None):
        self.position: Coords = Coords(0, 0)
        self.arena_name: str = arena_name
        self.facing: Facing = Facing.random()
        self.interests = {}
        self.game_age = 0



def are_last_five_items_same(lst):
    # Check if the list has at least 5 items
    if len(lst) < 10:
        return False

    # Get the last item in the list
    last_item = lst[-1]

    # Check if the last 5 items are the same as the last item
    return all(item == last_item for item in lst[-10:])


class GameService:
    def __init__(self, arena: arenas.ArenaDescription):
        self.state = State(arena_name=arena.name)

        self.world = WorldService(self.state)

        self.actions_queue = []
        self.current_state = CurrentState.CHILLING

        self.last_positions = []
        self.centers = []

    def get_action(self, knowledge):
        position = knowledge.position
        my_character = knowledge.visible_tiles[position].character
        visible_tiles = knowledge.visible_tiles
        self.state.position = position
        self.state.facing = my_character.facing

        self.last_positions.append(position)

        if are_last_five_items_same(self.last_positions):
            self.current_state = CurrentState.STUCK

        if self.state.game_age == 0:
            self.current_state = CurrentState.EXPLORING

            if len(self.centers) == 0 and self.current_state == CurrentState.EXPLORING:
                self.centers = self.world.find_centered_points()
        if self.current_state == CurrentState.EXPLORING and len(self.actions_queue) == 0:

            self.actions_queue = self.world.find_path(self.centers.pop(0))
        elif self.state.game_age > 4:
            if len(self.actions_queue) == 0:
                self.current_state = CurrentState.CHILLING

        self.remember(visible_tiles)
        self.decide_actions(position, my_character, visible_tiles)

        self.state.game_age += 1

        return self.actions_queue.pop(0)

    # todo: nuke this code
    def decide_actions(self, position, my_character, visible_tiles):
        self.state.position = position
        self.state.facing = my_character.facing

        menhir = self.state.interests.get('menhir')
        if menhir and self.state.game_age > 100 and (self.current_state != CurrentState.CAMPING or self.current_state != CurrentState.STUCK):
            self.actions_queue = self.world.find_path(menhir)
            self.current_state = CurrentState.CAMPING
            return

        if self.current_state == CurrentState.CAMPING:
            if self.current_state == CurrentState.STUCK:
                self.actions_queue = [Action.TURN_LEFT]

            chars = get_nearby_characters(position, visible_tiles, distance_threshold=10)
            if chars:
                char = chars[0]

                if is_in_path(self.state.position, self.state.facing, char[0]):
                    return self.actions_queue.insert(0, Action.ATTACK)


        if self.current_state == CurrentState.MOVING or self.current_state == CurrentState.EXPLORING or self.current_state == CurrentState.CAMPING:
            chars = get_nearby_characters(position, visible_tiles, distance_threshold=1)

            if chars:
                char = chars[0]

                if is_in_path(self.state.position, self.state.facing, char[0]):
                    return self.actions_queue.insert(0, Action.ATTACK)

        if self.current_state == CurrentState.STUCK:
            self.current_state = CurrentState.CHILLING
            self.actions_queue.clear()
            self.last_positions.clear()
            return

        if self.current_state == CurrentState.CHILLING:
            potions = get_nearby_potions(position, visible_tiles, distance_threshold=20)

            if len(potions) > 0:
                self.actions_queue = self.world.find_path(get_furthest_coord(potions[0][0], visible_tiles))
                self.current_state = CurrentState.LOOTING
                return

        if self.current_state == CurrentState.CHILLING:
            furthest_coord = get_furthest_coord(position, visible_tiles)
            if furthest_coord:
                self.actions_queue = self.world.find_path(furthest_coord)
                self.current_state = CurrentState.MOVING
            else:
                self.actions_queue.append(Action.TURN_RIGHT)

    def remember(self, visible_tiles):
        menhir = get_menhir(visible_tiles)
        if menhir:
            self.state.interests['menhir'] = menhir

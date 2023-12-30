from gupb.controller.r2d2.knowledge import R2D2Knowledge
from gupb.controller.r2d2.navigation import get_move_towards_target
from gupb.controller.r2d2.r2d2_helpers import get_all_enemies, walking_distance, get_cut_positions, get_possible_attack_positions
from gupb.controller.r2d2.r2d2_state_machine import R2D2StateMachine
from gupb.controller.r2d2.strategies import Strategy
from gupb.model.characters import Action, ChampionDescription, Facing
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, LineWeapon, Sword, Axe, Bow, Amulet
from itertools import chain 

class ChaseWeaker(Strategy):
    MAX_ROUNDS_WITHOUT_SEEING = 1

    def __init__(self, target: tuple[Coords, ChampionDescription]):
        self.target_coord = target[0]
        self.target_champion = target[1]

        self.rounds_in_chasing = 0
        self.round_without_seeing = 0
        self.last_diff = (0, 0)

    def is_applicable(self, knowledge: R2D2Knowledge) -> bool:
        if self.round_without_seeing > self.MAX_ROUNDS_WITHOUT_SEEING:
            return False
    
    def update_state(self, knowledge: R2D2Knowledge):
        # update target position 
        enemies = get_all_enemies(knowledge)
        target = next(filter(lambda x: x[1].controller_name == self.target_champion.controller_name, enemies), None)
        if target:
            self.last_diff = self.target_coord - target[0]
            self.target_coord = target[0]
            self.target_champion = target[1]
            self.round_without_seeing = 0
        else:
            self.round_without_seeing += 1
            self.target_coord += self.last_diff


    def decide(self, knowledge: R2D2Knowledge, state_machine: R2D2StateMachine) -> Action:
        self.rounds_in_chasing += 1

        # get the tiles, where the target can be in range of out weapon
        my_coords = knowledge.champion_knowledge.position
        my_description = knowledge.champion_knowledge.visible_tiles[my_coords].character
        cut_positions = get_possible_attack_positions(self.target_coord, knowledge)
        coord2facing = {coords: facing for coords, facing in cut_positions}
        cut_coordinates = [coords for coords, facing in cut_positions]
        closest_position, dist = find_closest_position(my_coords, cut_coordinates, knowledge)
        if dist == 0:
            return get_closest_turn(my_description.facing, coord2facing[closest_position])
        cut_coordinates = [coords for coords in cut_coordinates if walking_distance(my_coords, coords, knowledge.world_state.matrix_walkable_no_enymy) == dist]
        return get_move_towards_target(my_coords, closest_position, knowledge, allow_moonwalk=True)[0]
    
def get_closest_turn(current_facing: Facing, target_facing: Facing) -> Action:
    """
    Get the closest turn to the target facing.
    """
    if current_facing == target_facing:
        return Action.DO_NOTHING
    elif current_facing == target_facing.opposite():
        return Action.TURN_LEFT
    elif current_facing == target_facing.turn_left():
        return Action.TURN_RIGHT
    elif current_facing == target_facing.turn_right():
        return Action.TURN_LEFT
    else:
        raise Exception("Invalid facing")

    
def find_closest_position(start: Coords, ends: list[Coords], knowledge: R2D2Knowledge) -> tuple[Coords, int]:
    closest_position = min(ends, key=lambda coords: walking_distance(start, coords, knowledge.world_state.matrix_walkable))
        # find all positions with the same distance 
    dist = walking_distance(start, closest_position, knowledge.world_state.matrix_walkable)
    return closest_position, dist 

    
from typing import Tuple

import numpy as np
from pathfinding.finder.bi_a_star import BiAStarFinder
from pathfinding.core.diagonal_movement import DiagonalMovement
from pathfinding.core.grid import Grid

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords

from .r2d2_state_machine import R2D2StateMachineV2 as R2D2StateMachine
from .r2d2_helpers import *
from .utils import *


class RecklessRoamingDancingDruid(controller.Controller):

    def _init_matrix(self, arena: Arena):
        self.arena_shape = arena.size[1], arena.size[0]
        for coords, tile in arena.terrain.items():
            self.matrix[coords[1], coords[0]] = tiles_mapping[tile.description().type]

        # Save the initial state of the arena for decay mechanism
        self.initial_arena = self.matrix.copy()
    
    def _fill_matrix(self, champion_knowledge: ChampionKnowledge):
        
        # Update Visible tiles
        for coords, tile_description in champion_knowledge.visible_tiles.items():

            if tile_description.type == "menhir":
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.type]
                self.menhir_position = coords
            
            if tile_description.loot:
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.loot.name]
            
            if tile_description.consumable:
                self.matrix[coords[1], coords[0]] = tiles_mapping[tile_description.consumable.name]
            
            if tile_description.character:
                self.matrix[coords[1], coords[0]] = tiles_mapping["enymy"]
            
            if tile_description.effects:
                if "mist" in tile_description.effects:
                    self.matrix[coords[1], coords[0]] = tiles_mapping["mist"]
    
    def _decay_step(self, champion_knowledge: ChampionKnowledge):
        
        # Decay the whole mask
        self.decay_mask = np.maximum(self.decay_mask - 1, 0)

        # Reset decayed tiles
        self.matrix = np.where(self.decay_mask == 0, self.initial_arena, self.matrix)
        # - but keep the menhir in place once discovered
        if self.menhir_position:
            self.matrix[self.menhir_position[1], self.menhir_position[0]] = tiles_mapping["menhir"]

        # Reset decay of visible tiles
        for coords, tile_description in champion_knowledge.visible_tiles.items():
            if tile_description.character:
                # - if the tile is occupied by an enemy, reset the decay to 0, we need live information
                self.decay_mask[coords[1], coords[0]] = 0
            else:
                # - otherwise, reset the decay to the initial value
                self.decay_mask[coords[1], coords[0]] = self.decay
    
    def _update_state(self, champion_knowledge: ChampionKnowledge):

        # Update counter
        self.counter += 1

        # Update Champion position
        self.matrix[champion_knowledge.position.y, champion_knowledge.position.x] = tiles_mapping["champion"]
        self.champion_position = champion_knowledge.position
        self.current_weapon = champion_knowledge.visible_tiles[self.champion_position].character.weapon.name

        # Create a walkable matrix for pathfinding
        matrix_walkable = self.matrix[:self.arena_shape[0], :self.arena_shape[1]]
        matrix_walkable = np.logical_and(matrix_walkable != 2, matrix_walkable != 3)
        matrix_walkable = np.logical_and(matrix_walkable, matrix_walkable != 12)
        self.matrix_walkable = matrix_walkable.astype(int)

    def __init__(self, first_name: str, decay: int = 5, menhir_eps=3):
        self.first_name: str = first_name

        # Controls the memory of the agent. Decay of n, means that the agent will assume that
        # the item is still there for n steps, even when it's not visible. Note that the decay
        # of 1 means no memory at all, the higher the decay, the longer the memory.
        # TODO Could we use a different decay for dynamic characters and a different one for static items?
        self.decay = decay
        self.decay_mask = np.zeros(LARGEST_ARENA_SHAPE, np.int8)

        # Define a state machine to manage the agent's behaviour
        self.state_machine = R2D2StateMachine()

        self.arena_id = None
        self.arena_shape = None
        self.initial_arena = None
        self.menhir_position = None
        self.champion_position = None
        self.menhir_eps = menhir_eps
        self.defending_attack = False # TODO This is a hack, use the state machine instead
        self.finder = BiAStarFinder(diagonal_movement=DiagonalMovement.never)

        # The state of the agend
        self.counter = 0
        self.destination = None

        # This is the representation of the map state that will be returned as the observation
        self.matrix = np.zeros(LARGEST_ARENA_SHAPE, dtype=np.int8)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecklessRoamingDancingDruid):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)
    
    def _move_to(
            self, target_coords: Coords, knowledge: characters.ChampionKnowledge
        ) -> Tuple[characters.Action, bool]:
        "Returns the next action to move to the target_coords and a flag indicating if the target was reached"
        
        # If already in 
        if self.champion_position == target_coords:
            return characters.Action.TURN_RIGHT, True   # Always better turn than do nothing
        
        # Find a path to the target
        # - Translate the matrix into an appropriate format for the pathfinding algorithm
        grid = Grid(matrix=self.matrix_walkable)
        start = grid.node(*self.champion_position)
        end = grid.node(*target_coords)

        # - Find the path
        path, _ = self.finder.find_path(start, end, grid)
        next_tile_coords = Coords(path[1].x, path[1].y)

        # - Move to the next tile
        delta = next_tile_coords - self.champion_position
        facing = knowledge.visible_tiles[self.champion_position].character.facing

        if facing.value == characters.Facing.UP.value:
            if delta == characters.Facing.UP.value:
                return characters.Action.STEP_FORWARD, False
            if delta == characters.Facing.LEFT.value:
                return characters.Action.TURN_LEFT, False
            return characters.Action.TURN_RIGHT, False
        
        if facing.value == characters.Facing.RIGHT.value:
            if delta == characters.Facing.RIGHT.value:
                return characters.Action.STEP_FORWARD, False
            if delta == characters.Facing.UP.value:
                return characters.Action.TURN_LEFT, False
            return characters.Action.TURN_RIGHT, False
        
        if facing.value == characters.Facing.DOWN.value:
            if delta == characters.Facing.DOWN.value:
                return characters.Action.STEP_FORWARD, False
            if delta == characters.Facing.RIGHT.value:
                return characters.Action.TURN_LEFT, False
            return characters.Action.TURN_RIGHT, False
        
        if facing.value == characters.Facing.LEFT.value:
            if delta == characters.Facing.LEFT.value:
                return characters.Action.STEP_FORWARD, False
            if delta == characters.Facing.DOWN.value:
                return characters.Action.TURN_LEFT, False
            return characters.Action.TURN_RIGHT, False
    
    def _attack_is_effective(self, knowledge: characters.ChampionKnowledge) -> bool:
        """
        Check if the attack is effective. The attack is effective if the enemy is in the range of the weapon.
        """
        
        # Determine facing
        facing = knowledge.visible_tiles[self.champion_position].character.facing

        if self.current_weapon == "knife":
            # - if the enemy is in the range of the knife, attack
            range = [self.champion_position + facing.value]
            pot = [self.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if self.current_weapon == "sword":
            range = [self.champion_position + i * facing.value for i in [1, 2, 3]]
            pot = [self.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if self.current_weapon == "bow":
            range = [self.champion_position + i * facing.value for i in [1, 2, 3, 4, 5]]
            pot = [self.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if self.current_weapon == "axe":
            range = [
                self.champion_position + facing.value,
                self.champion_position + facing.value + facing.turn_left().value,
                self.champion_position + facing.value + facing.turn_right().value,
            ]
            pot = [self.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if self.current_weapon == "amulet":
            position = self.champion_position
            range = [
                Coords(*position + (1, 1)),
                Coords(*position + (-1, 1)),
                Coords(*position + (1, -1)),
                Coords(*position + (-1, -1)),
                Coords(*position + (2, 2)),
                Coords(*position + (-2, 2)),
                Coords(*position + (2, -2)),
                Coords(*position + (-2, -2)),
            ]
            pot = [self.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        return False
    
    def _act_stage_1(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """
        In this stage, the agent is supposed to find a weapon. The agent randomly chooses a destination, until
        a weapon is seen. Then the agent moves to the weapon and collects it. It finalizes this stage.
        """
        
        # Act according to the state in stage I - Find Weapon
        if self.state_machine.current_state.value.name == "ChooseDestinationStI":
            # - choose a destination and transition to the approach destination state
            self.destination = choose_destination(self.matrix)
            self.state_machine.st1_destination_chosen()
        
        if self.state_machine.current_state.value.name == "ApproachDestinationStI":
            # - scan the visible tiles for the weapon, if any, save the weapon destination
            # and transition to the 'approach weapon' state
            possible_weapon = scan_for_weapons(self.matrix)
            if possible_weapon:
                weapon_coords, weapon_type = possible_weapon
                self.weapon_destination = weapon_coords
                self.weapon_destination_type = weapon_type
                self.state_machine.st1_weapon_localized()

            # - if no weapon is not visible, move to the destination
            else:
                next_action, reached = self._move_to(self.destination, knowledge)
                if reached:
                    self.destination = None
                    self.state_machine.st1_destination_reached()
                return next_action
            
        if self.state_machine.current_state.value.name == "ApproachWeaponStI":
            # - if the weapon is reached, transition to the stage II
            if self.champion_position == self.weapon_destination:
                self.current_weapon = self.weapon_destination_type
                self.state_machine.st1_weapon_collected()

            # - if the weapon is still on board, move to the weapon
            elif self.matrix[self.weapon_destination[1], self.weapon_destination[0]] == tiles_mapping[self.weapon_destination_type]:
                next_action, _ = self._move_to(self.weapon_destination, knowledge)
                return next_action
            
            # - if the weapon is not visible, return to the 'choose destination' state
            else:
                self.weapon_destination_type = None
                self.state_machine.st1_weapon_lost()

        return characters.Action.TURN_RIGHT # Better than nothing

    def _act_stage_2(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """
        In second stage, the agent is supposed to find the menhir. When the menhir is seen, the agent moves to it.
        This stage ends when the agent reaches the menhir and stages III is started.
        """

        # Act according to the state in stage II - Find Menhir
        if self.state_machine.current_state.value.name == "ChooseDestinationStII":
            # - choose a destination and transition to the approach destination state
            self.destination = choose_destination(self.matrix)
            self.state_machine.st2_destination_chosen()
        
        if self.state_machine.current_state.value.name == "ApproachDestinationStII":
            # - If menhir is already found, transition to the 'approach menhir' state
            if self.menhir_position:
                self.state_machine.st2_menhir_localized()
            
            # - If menhir is not found, move to the destination
            else:
                next_action, reached = self._move_to(self.destination, knowledge)
                if reached:
                    self.destination = None
                    self.state_machine.st2_destination_reached()
                return next_action
        
        if self.state_machine.current_state.value.name == "ApproachMenhirStII":
            # # - If menhir is reached, transition to the stage III
            if manhataan_distance(self.champion_position, self.menhir_position) <= self.menhir_eps:
                self.state_machine.st2_menhir_reached()
            
            # - If menhir is not reached, move to the menhir
            else:
                next_action, _ = self._move_to(self.menhir_position, knowledge)
                return next_action
        
        return characters.Action.TURN_RIGHT # Better than nothing

    def _act_stage_3(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """
        This is the final stage, when the agent is supposed to defend the menhir. At the moment, the agent
        just moves around the menhir.
        """

        # Act according to the state in stage III - Defend Menhir
        if self.state_machine.current_state.value.name == "ChooseDestinationStIII":
            # - choose a destination and transition to the approach destination state
            self.destination = choose_destination_around_menhir(self.matrix, self.menhir_position, self.menhir_eps)
            self.state_machine.st3_destination_chosen()
        
        if self.state_machine.current_state.value.name == "ApproachDestinationStIII":
            # - move to the destination
            next_action, reached = self._move_to(self.destination, knowledge)
            if reached:
                self.destination = None
                self.state_machine.st3_destination_reached()
            return next_action
        
        return characters.Action.TURN_RIGHT # Better than nothing

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        
        # Apply decay and update the decay mask
        self._decay_step(knowledge)
        
        # Update the matrix with the current observation
        self._fill_matrix(knowledge)

        # Update the state of the agent
        self._update_state(knowledge)
        
        # Chose next action acording to the stage
        next_action = characters.Action.TURN_RIGHT # Better than nothing
        if self.state_machine.current_state.value.stage == 1:
            next_action = self._act_stage_1(knowledge)
        elif self.state_machine.current_state.value.stage == 2:
            next_action = self._act_stage_2(knowledge)
        elif self.state_machine.current_state.value.stage == 3:
            next_action = self._act_stage_3(knowledge)

        # However, if the attack is effective, attack
        if self._attack_is_effective(knowledge):
            return characters.Action.ATTACK
        
        return next_action

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena_id = arena_description.name
        self._init_matrix(Arena.load(self.arena_id))

    @property
    def name(self) -> str:
        return f'RecklessRoamingDancingDruid_{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.R2D2

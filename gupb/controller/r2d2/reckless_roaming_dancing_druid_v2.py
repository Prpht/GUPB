from gupb import controller
from gupb.controller.r2d2.knowledge import WorldState
from gupb.controller.r2d2.navigation import get_move_towards_target
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords

from .r2d2_state_machine import R2D2StateMachineV2 as R2D2StateMachine
from .r2d2_helpers import *
from .utils import *


class RecklessRoamingDancingDruid(controller.Controller):
    
    def __init__(self, first_name: str, decay: int = 5, menhir_eps=3):
        self.first_name: str = first_name

        # Controls the memory of the agent. Decay of n, means that the agent will assume that
        # the item is still there for n steps, even when it's not visible. Note that the decay
        # of 1 means no memory at all, the higher the decay, the longer the memory.
        # TODO Could we use a different decay for dynamic characters and a different one for static items?  

        self.decay: int = decay
        self.world_state: WorldState = None # initialize in reset

        # Define a state machine to manage the agent's behaviour
        self.state_machine = R2D2StateMachine()

        self.arena_id = None
        self.initial_arena = None
        self.champion_position = None
        self.menhir_eps = menhir_eps
        self.defending_attack = False # TODO This is a hack, use the state machine instead

        # The state of the agend
        self.counter = 0
        self.destination = None

    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecklessRoamingDancingDruid):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)
    
    def _attack_is_effective(self, knowledge: characters.ChampionKnowledge, world_state: WorldState) -> bool:
        """
        Check if the attack is effective. The attack is effective if the enemy is in the range of the weapon.
        """
        
        # Determine facing
        facing = knowledge.visible_tiles[self.champion_position].character.facing

        if self.current_weapon == "knife":
            # - if the enemy is in the range of the knife, attack
            range = [self.champion_position + facing.value]
            pot = [world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if self.current_weapon == "sword":
            range = [self.champion_position + i * facing.value for i in [1, 2, 3]]
            pot = [world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if self.current_weapon == "bow":
            range = [self.champion_position + i * facing.value for i in [1, 2, 3, 4, 5]]
            pot = [world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if self.current_weapon == "axe":
            range = [
                self.champion_position + facing.value,
                self.champion_position + facing.value + facing.turn_left().value,
                self.champion_position + facing.value + facing.turn_right().value,
            ]
            pot = [world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
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
            pot = [world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        return False
    
    def _act_stage_1(self, knowledge: characters.ChampionKnowledge, world_state: WorldState) -> characters.Action:
        """
        In this stage, the agent is supposed to find a weapon. The agent randomly chooses a destination, until
        a weapon is seen. Then the agent moves to the weapon and collects it. It finalizes this stage.
        """
        
        # Act according to the state in stage I - Find Weapon
        if self.state_machine.current_state.value.name == "ChooseDestinationStI":
            # - choose a destination and transition to the approach destination state
            self.destination = choose_destination(world_state.matrix)
            self.state_machine.st1_destination_chosen()
        
        if self.state_machine.current_state.value.name == "ApproachDestinationStI":
            # - scan the visible tiles for the weapon, if any, save the weapon destination
            # and transition to the 'approach weapon' state
            possible_weapon = scan_for_weapons(world_state.matrix)
            if possible_weapon:
                weapon_coords, weapon_type = possible_weapon
                self.weapon_destination = weapon_coords
                self.weapon_destination_type = weapon_type
                self.state_machine.st1_weapon_localized()

            # - if no weapon is not visible, move to the destination
            else:
                print("action3")
                next_action, reached = get_move_towards_target(self.champion_position, self.destination, knowledge, world_state)
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
            elif world_state.matrix[self.weapon_destination[1], self.weapon_destination[0]] == tiles_mapping[self.weapon_destination_type]:
                next_action, _ = get_move_towards_target(self.champion_position, self.weapon_destination, knowledge, world_state)
                return next_action
            
            # - if the weapon is not visible, return to the 'choose destination' state
            else:
                self.weapon_destination_type = None
                self.state_machine.st1_weapon_lost()

        return characters.Action.TURN_RIGHT # Better than nothing

    def _act_stage_2(self, knowledge: characters.ChampionKnowledge, world_state: WorldState) -> characters.Action:
        """
        In second stage, the agent is supposed to find the menhir. When the menhir is seen, the agent moves to it.
        This stage ends when the agent reaches the menhir and stages III is started.
        """

        # Act according to the state in stage II - Find Menhir
        if self.state_machine.current_state.value.name == "ChooseDestinationStII":
            # - choose a destination and transition to the approach destination state
            self.destination = choose_destination(world_state.matrix)
            self.state_machine.st2_destination_chosen()
        
        if self.state_machine.current_state.value.name == "ApproachDestinationStII":
            # - If menhir is already found, transition to the 'approach menhir' state
            if world_state.menhir_position:
                self.state_machine.st2_menhir_localized()
            
            # - If menhir is not found, move to the destination
            else:
                next_action, reached = get_move_towards_target(self.champion_position, self.destination, knowledge, world_state)
                if reached:
                    self.destination = None
                    self.state_machine.st2_destination_reached()
                return next_action
        
        if self.state_machine.current_state.value.name == "ApproachMenhirStII":
            # # - If menhir is reached, transition to the stage III
            if manhataan_distance(self.champion_position, world_state.menhir_position) <= self.menhir_eps:
                self.state_machine.st2_menhir_reached()
            
            # - If menhir is not reached, move to the menhir
            else:
                next_action, _ = get_move_towards_target(self.champion_position, menhir_position, knowledge, world_state)
                return next_action
        
        return characters.Action.TURN_RIGHT # Better than nothing

    def _act_stage_3(self, knowledge: characters.ChampionKnowledge, world_state: WorldState) -> characters.Action:
        """
        This is the final stage, when the agent is supposed to defend the menhir. At the moment, the agent
        just moves around the menhir.
        """

        # Act according to the state in stage III - Defend Menhir
        if self.state_machine.current_state.value.name == "ChooseDestinationStIII":
            # - choose a destination and transition to the approach destination state
            if world_state.menhir_position is None:
                raise ValueError("Menhir position is None")
            self.destination = choose_destination_around_menhir(world_state.matrix, world_state.menhir_position, self.menhir_eps)
            self.state_machine.st3_destination_chosen()
        
        if self.state_machine.current_state.value.name == "ApproachDestinationStIII":
            # - move to the destination
            next_action, reached = get_move_towards_target(self.champion_position, self.destination, knowledge, world_state)
            if reached:
                self.destination = None
                self.state_machine.st3_destination_reached()
            return next_action
        
        return characters.Action.TURN_RIGHT # Better than nothing

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.counter += 1
        self.champion_position = knowledge.position
        self.current_weapon = knowledge.visible_tiles[self.champion_position].character.weapon.name
        self.world_state.update(knowledge)
        
        # Chose next action acording to the stage
        next_action = characters.Action.TURN_RIGHT # Better than nothing
        if self.state_machine.current_state.value.stage == 1:
            next_action = self._act_stage_1(knowledge, self.world_state)
        elif self.state_machine.current_state.value.stage == 2:
            next_action = self._act_stage_2(knowledge, self.world_state)
        elif self.state_machine.current_state.value.stage == 3:
            next_action = self._act_stage_3(knowledge, self.world_state)

        print("action1", next_action)
        # However, if the attack is effective, attack
        if self._attack_is_effective(knowledge, self.world_state):
            return characters.Action.ATTACK
        print("action2", next_action)
        
        return next_action

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena_id = arena_description.name
        self.world_state = WorldState(Arena.load(self.arena_id), self.decay)

    @property
    def name(self) -> str:
        return f'RecklessRoamingDancingDruid_{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.R2D2

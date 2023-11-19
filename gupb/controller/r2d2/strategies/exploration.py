import numpy as np

from typing import Any
from gupb.controller.r2d2.knowledge import R2D2Knowledge
from gupb.controller.r2d2.navigation import get_move_towards_target
from gupb.controller.r2d2.r2d2_helpers import *
from gupb.controller.r2d2.r2d2_state_machine import R2D2StateMachine
from gupb.controller.r2d2.strategies import Strategy
from gupb.controller.r2d2.utils import *
from gupb.model.characters import Action


class ExplorationStrategy(Strategy):
    def __init__(self):
        self.destination = None

    def decide(self, knowledge: R2D2Knowledge) -> Action:

        champion_position = knowledge.champion_knowledge.position
        
        # First, choose a destination, preferably unexplored
        if self.destination is None:
            self.destination = choose_destination(knowledge.world_state.matrix, knowledge.world_state.explored)
        
        # Update the destination if you see any items (weapons or potions)
        tempting_destination = scan_for_items(knowledge)
        if tempting_destination:
            self.destination = tempting_destination

        # Avoid other champions TODO?
        # self.destination = self._avoid_champions(knowledge, self.destination)

        # Move towards the destination
        next_action, reached = get_move_towards_target(champion_position, self.destination, knowledge)

        # If the destination is reached, reset the destination
        if reached:
            self.destination = None

        return next_action


class MenhirStrategy(Strategy):
    def __init__(self, menhir_eps):
        self.menhir_eps = menhir_eps
        self.destination = None

    def decide(self, knowledge: R2D2Knowledge) -> Action:

        champion_position = knowledge.champion_knowledge.position
        menhir_position = knowledge.world_state.menhir_position
        
        # If further than menhir_eps from the menhir, the destination is menhir
        if walking_distance(champion_position, menhir_position, knowledge.world_state.matrix_walkable) > self.menhir_eps:
            self.destination = menhir_position
        
        # If no destination choosen, random walk around the menhir
        if self.destination is None:
            self.destination = choose_destination_around_menhir(knowledge, menhir_position, self.menhir_eps)

        # Update the destination if you see any items (weapons or potions), but with a distance constraint
        # TODO add distance constraint
        tempting_destination = scan_for_items(knowledge, self.menhir_eps)
        if tempting_destination:
            self.destination = tempting_destination

        # Move towards the destination
        next_action, reached = get_move_towards_target(champion_position, self.destination, knowledge)

        # If the destination is reached, reset the destination
        if reached:
            self.destination = None
        
        return next_action

class WeaponFinder(Strategy):
    def __init__(self):
        self.destination = None
        self.weapon_destination = None
        self.weapon_destination_type = None

    def decide(self, knowledge: R2D2Knowledge, state_machine: R2D2StateMachine) -> Action:
        """
        In this stage, the agent is supposed to find a weapon. The agent randomly chooses a destination, until
        a weapon is seen. Then the agent moves to the weapon and collects it. It finalizes this stage.
        """
        champion_position = knowledge.champion_knowledge.position
        
        # Act according to the state in stage I - Find Weapon
        if state_machine.current_state.value.name == "ChooseDestinationStI":
            # - choose a destination and transition to the approach destination state
            self.destination = choose_destination(knowledge.world_state.matrix)
            state_machine.st1_destination_chosen()
        
        if state_machine.current_state.value.name == "ApproachDestinationStI":
            # - scan the visible tiles for the weapon, if any, save the weapon destination
            # and transition to the 'approach weapon' state
            possible_weapon = scan_for_weapons(knowledge.world_state.matrix)
            if possible_weapon:
                weapon_coords, weapon_type = possible_weapon
                self.weapon_destination = weapon_coords
                self.weapon_destination_type = weapon_type
                state_machine.st1_weapon_localized()

            # - if no weapon is not visible, move to the destination
            else:
                next_action, reached = get_move_towards_target(champion_position, self.destination, knowledge)
                if reached:
                    self.destination = None
                    state_machine.st1_destination_reached()
                return next_action
            
        if state_machine.current_state.value.name == "ApproachWeaponStI":
            # - if the weapon is reached, transition to the stage II
            if champion_position == self.weapon_destination:
                state_machine.st1_weapon_collected()

            # - if the weapon is still on board, move to the weapon
            elif knowledge.world_state.matrix[self.weapon_destination[1], self.weapon_destination[0]] == tiles_mapping[self.weapon_destination_type]:
                next_action, _ = get_move_towards_target(champion_position, self.weapon_destination, knowledge)
                return next_action
            
            # - if the weapon is not visible, return to the 'choose destination' state
            else:
                self.weapon_destination_type = None
                state_machine.st1_weapon_lost()

        return characters.Action.TURN_RIGHT # Better than nothing
    

class MenhirFinder(Strategy):
    def __init__(self, menhir_eps=3):
        self.destination = None
        self.menhir_eps = menhir_eps

    def decide(self, knowledge: R2D2Knowledge, state_machine: R2D2StateMachine) -> Action:
        """
        In second stage, the agent is supposed to find the menhir. When the menhir is seen, the agent moves to it.
        This stage ends when the agent reaches the menhir and stages III is started.
        """
        champion_position = knowledge.champion_knowledge.position

        # Act according to the state in stage II - Find Menhir
        if state_machine.current_state.value.name == "ChooseDestinationStII":
            # - choose a destination and transition to the approach destination state
            self.destination = choose_destination(knowledge.world_state.matrix)
            state_machine.st2_destination_chosen()
        
        if state_machine.current_state.value.name == "ApproachDestinationStII":
            # - If menhir is already found, transition to the 'approach menhir' state
            if knowledge.world_state.menhir_position:
                state_machine.st2_menhir_localized()
            
            # - If menhir is not found, move to the destination
            else:
                next_action, reached = get_move_towards_target(champion_position, self.destination, knowledge)
                if reached:
                    self.destination = None
                    state_machine.st2_destination_reached()
                return next_action
        
        if state_machine.current_state.value.name == "ApproachMenhirStII":
            # # - If menhir is reached, transition to the stage III
            if manhataan_distance(champion_position, knowledge.world_state.menhir_position) <= self.menhir_eps:
                state_machine.st2_menhir_reached()
            
            # - If menhir is not reached, move to the menhir
            else:
                next_action, _ = get_move_towards_target(champion_position, knowledge.world_state.menhir_position, knowledge)
                return next_action
        
        return characters.Action.TURN_RIGHT # Better than nothing
    

class MenhirObserver(Strategy):
    def __init__(self, menhir_eps=3):
        self.destination = None
        self.menhir_eps = menhir_eps

    def decide(self, knowledge: R2D2Knowledge, state_machine: R2D2StateMachine) -> Action:
        """
        This is the final stage, when the agent is supposed to defend the menhir. At the moment, the agent
        just moves around the menhir.
        """
        champion_position = knowledge.champion_knowledge.position

        # Act according to the state in stage III - Defend Menhir
        if state_machine.current_state.value.name == "ChooseDestinationStIII":
            # - choose a destination and transition to the approach destination state
            if knowledge.world_state.menhir_position is None:
                raise ValueError("Menhir position is None")
            self.destination = choose_destination_around_menhir(knowledge, knowledge.world_state.menhir_position, self.menhir_eps)
            state_machine.st3_destination_chosen()
        
        if state_machine.current_state.value.name == "ApproachDestinationStIII":
            # - move to the destination
            next_action, reached = get_move_towards_target(champion_position, self.destination, knowledge)
            if reached:
                self.destination = None
                state_machine.st3_destination_reached()
            return next_action
        
        return characters.Action.TURN_RIGHT # Better than nothing
    
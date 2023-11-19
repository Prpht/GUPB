from gupb import controller
from gupb.controller.r2d2.knowledge import R2D2Knowledge, WorldState, decide_whether_attack, get_all_enemies, get_cut_positions, get_threating_enemies_map
from gupb.controller.r2d2.navigation import get_move_towards_target
from gupb.controller.r2d2.strategies.exploration import MenhirFinder, MenhirObserver, WeaponFinder
from gupb.controller.r2d2.strategies.potion import PotionPicker, get_nearby_potions
from gupb.controller.r2d2.strategies.runaway import Runaway
from gupb.controller.r2d2.strategies.exploration import *
from gupb.model import arenas
from gupb.model import characters
from gupb.model.arenas import Arena
from gupb.model.characters import ChampionKnowledge
from gupb.model.coordinates import Coords

from .r2d2_state_machine import R2D2StateMachine
from .r2d2_helpers import *
from .utils import *


class RecklessRoamingDancingDruid(controller.Controller):
    
    def __init__(self, first_name: str, decay: int = 1, menhir_eps=3):
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
        self.defending_attack = False # TODO This is a hack, use the state machine instead

        # The state of the agend
        self.counter = 0

        self.exploration_strategy = ExplorationStrategy()
        self.menhir_strategy = MenhirStrategy(menhir_eps)


    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecklessRoamingDancingDruid):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)
    
    def _attack_is_effective(self, knowledge: R2D2Knowledge) -> bool:
        """
        Check if the attack is effective. The attack is effective if the enemy is in the range of the weapon.
        """
        
        # Determine facing
        facing = knowledge.chempion_knowledge.visible_tiles[self.champion_position].character.facing

        if knowledge.current_weapon == "knife":
            # - if the enemy is in the range of the knife, attack
            range = [self.champion_position + facing.value]
            pot = [knowledge.world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if knowledge.current_weapon == "sword":
            range = [self.champion_position + i * facing.value for i in [1, 2, 3]]
            pot = [knowledge.world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if knowledge.current_weapon == "bow":
            range = [self.champion_position + i * facing.value for i in [1, 2, 3, 4, 5]]
            pot = [knowledge.world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if knowledge.current_weapon == "axe":
            range = [
                self.champion_position + facing.value,
                self.champion_position + facing.value + facing.turn_left().value,
                self.champion_position + facing.value + facing.turn_right().value,
            ]
            pot = [knowledge.world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        if knowledge.current_weapon == "amulet":
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
            pot = [knowledge.world_state.matrix[r[1], r[0]] == tiles_mapping["enymy"] for r in range]
            return any(pot)

        return False

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.counter += 1
        try:
            self.champion_position = knowledge.position
            self.world_state.update(knowledge)

            r2_knowledge = R2D2Knowledge(
                knowledge,
                self.world_state,
                self.arena,
                knowledge.visible_tiles[self.champion_position].character.weapon.name
            )

            # priorities 
            if decide_whether_attack(r2_knowledge):
                return characters.Action.ATTACK
            if self._is_threat_nearby(r2_knowledge):
                return Runaway().decide(r2_knowledge, self.state_machine)
            if len(get_nearby_potions(r2_knowledge)) > 0:
                return PotionPicker().decide(r2_knowledge, self.state_machine)
            
            # exploration
            if (
                self.world_state.menhir_position and (
                    items_ranking[r2_knowledge.current_weapon] < items_ranking["knife"] or
                    r2_knowledge.world_state.mist_present or
                    r2_knowledge.world_state.step_counter > MAX_STEPS_EXPLORING
                )
            ):
                next_action = self.menhir_strategy.decide(r2_knowledge)
            else:
                next_action = self.exploration_strategy.decide(r2_knowledge)

            # If walked into a worse weapon, drop it
            dropped_weapon = knowledge.visible_tiles[self.champion_position].loot
            if dropped_weapon:
                if items_ranking[dropped_weapon.name] < items_ranking[r2_knowledge.current_weapon]:
                    return characters.Action.STEP_BACKWARD
        except Exception as e:
            # import traceback
            # print(e)
            # traceback.print_exc()
            return characters.Action.TURN_RIGHT


        return next_action
    
    def _is_threat_nearby(self, knowledge: R2D2Knowledge) -> bool:
        """
        Check if there is a threat nearby.
        """
        
        threating_coords = get_threating_enemies_map(knowledge)
        my_coord = knowledge.champion_knowledge.position
        # return true if there is a threat in the range of 4 walking distance
        return any([walking_distance(my_coord, coords, knowledge.world_state.matrix_walkable) <= 4 for coords, enemy in threating_coords])
        

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena_id = arena_description.name
        self.arena = Arena.load(self.arena_id)
        self.world_state = WorldState(self.arena, self.decay)

    @property
    def name(self) -> str:
        return f'RecklessRoamingDancingDruid_{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.R2D2

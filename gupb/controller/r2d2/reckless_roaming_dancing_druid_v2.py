from gupb import controller
from gupb.controller.r2d2.knowledge import R2D2Knowledge, WorldState
from gupb.controller.r2d2.navigation import get_move_towards_target, _try_to_find_path
from gupb.controller.r2d2.strategies.attack import ChaseWeaker
from gupb.controller.r2d2.strategies.exploration import MenhirFinder, MenhirObserver, WeaponFinder
from gupb.controller.r2d2.strategies.potion import PotionPicker, get_nearby_potions
from gupb.controller.r2d2.strategies.runaway import Runaway
from gupb.controller.r2d2.strategies.mist import *
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
        self.chase_strategy = None 


    def __eq__(self, other: object) -> bool:
        if isinstance(other, RecklessRoamingDancingDruid):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)
    
    def _print(self, *args):
        # print(*args)
        pass 

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
            # - if there is a potion nearby, pick it up
            potions = get_nearby_potions(r2_knowledge)
            if len(potions) > 0:
                action = PotionPicker().decide(r2_knowledge, self.state_machine)
                self._print("pick potion", action)
                return action
            self._print("potions count", len(potions))
            

            # priorities
            # - if the enemy is in the range of the weapon, attack
            if decide_whether_attack(r2_knowledge):
                if self.chase_strategy:
                    self.chase_strategy.update_state(r2_knowledge)
                else:
                    target_enemy = get_weaker_enemy_in_range(r2_knowledge, max_distance=0)
                    if target_enemy:
                        self._print("chasing the enemy after attack")
                        self.chase_strategy = ChaseWeaker(target_enemy)
                self._print("attack")
                return characters.Action.ATTACK
            # - if the mist is coming, go to the menhir
            if r2_knowledge.world_state.mist_present:
                action = MistAvoider().decide(r2_knowledge)
                self._print("mist is coming", action)
                return action
            # - if there is a threat nearby, runaway
            if self._is_threat_nearby(r2_knowledge):
                action = Runaway().decide(r2_knowledge, self.state_machine)
                self._print("runaway", action)
                return action
            
            # chase strategy 
            if self.chase_strategy and self.chase_strategy.is_applicable(r2_knowledge):
                self.chase_strategy.update_state(r2_knowledge)
                action = self.chase_strategy.decide(r2_knowledge, self.state_machine)
                self._print("chasing enemy", action, target_enemy[0], r2_knowledge.champion_knowledge.position, r2_knowledge.champion_knowledge.visible_tiles[r2_knowledge.champion_knowledge.position].character.facing)
                return action
            else:
                self.chase_strategy = None
                target_enemy = get_weaker_enemy_in_range(r2_knowledge, max_distance=4)
                if target_enemy:
                    self.chase_strategy = ChaseWeaker(target_enemy)
                    action = self.chase_strategy.decide(r2_knowledge, self.state_machine)
                    self._print("chasing enemy", action, target_enemy[0], r2_knowledge.champion_knowledge.position, r2_knowledge.champion_knowledge.visible_tiles[r2_knowledge.champion_knowledge.position].character.facing)
                    return action

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
            return characters.Action.ATTACK


        return next_action
    
    def _is_threat_nearby(self, knowledge: R2D2Knowledge) -> bool:
        """
        Check if there is a threat nearby.
        """
        threating_coords = get_threating_enemies_map(knowledge)
        threating_enemies_cut_positions = set()
        for coord, descr in threating_coords:
            cuts = get_cut_positions(coord, descr, knowledge)
            threating_enemies_cut_positions.update(cuts)
        is_in_cut_range = knowledge.champion_knowledge.position in threating_enemies_cut_positions
        my_coord = knowledge.champion_knowledge.position
        # return true if there is a threat in the range of 4 walking distance
        return is_in_cut_range or any([walking_distance(my_coord, coords, knowledge.world_state.matrix_walkable) <= 2 for coords, enemy in threating_coords])
        

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

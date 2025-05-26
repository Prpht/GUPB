import random
from typing import Optional, Tuple, List, Union, Set

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model.characters import Facing, Action

from gupb.controller.pirat.utils import (
    ensure_coords, manhattan_distance, is_tile_safe
)
from gupb.controller.pirat.bot_knowledge import (
    find_menhir_in_visible, update_mist_memory_and_threat_levels,
    find_nearest_enemy, find_nearest_potion
)

class PiratController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena_name: Optional[str] = None
        self.menhir_position: Optional[coordinates.Coords] = None
        self.current_facing: Optional[Facing] = None
        self.last_action: Optional[Action] = None
        self.action_queue: List[Action] = []
        self.last_seen_mist_coords: Set[coordinates.Coords] = set() 
        self.mist_warning_active: bool = False

    def _find_menhir_in_visible(self, knowledge: characters.ChampionKnowledge) -> None:
        menhir_pos = find_menhir_in_visible(knowledge) 
        if menhir_pos:
            self.menhir_position = menhir_pos

    def _update_mist_memory_and_threat_levels(self, knowledge: characters.ChampionKnowledge, my_pos: coordinates.Coords) -> Tuple[bool, bool]:
        is_critical, is_warning, new_mist_coords = update_mist_memory_and_threat_levels(
            knowledge, my_pos
        )
        self.last_seen_mist_coords = new_mist_coords
        self.mist_warning_active = is_warning or is_critical
        return is_critical, is_warning

    def _get_action_to_target(self, current_facing: Facing, current_pos: coordinates.Coords, target_pos_raw: Union[coordinates.Coords, Tuple[int,int]], knowledge: characters.ChampionKnowledge, allow_unsafe_target_step: bool = False) -> Optional[Action]:
        target_pos = ensure_coords(target_pos_raw) 
        if current_pos == target_pos:
            if target_pos == self.menhir_position:
                 menhir_tile_desc = knowledge.visible_tiles.get(self.menhir_position)
                 if menhir_tile_desc and menhir_tile_desc.effects and any(eff.type == 'mist' for eff in menhir_tile_desc.effects):
                     return None 
            return Action.DO_NOTHING
        
        delta = target_pos - current_pos
        preferred_step_vector = None
        if abs(delta.x) > abs(delta.y):
            preferred_step_vector = coordinates.Coords(1 if delta.x > 0 else -1, 0)
        elif abs(delta.y) > abs(delta.x):
            preferred_step_vector = coordinates.Coords(0, 1 if delta.y > 0 else -1)
        elif delta.x != 0:
            preferred_step_vector = coordinates.Coords(1 if delta.x > 0 else -1, 0)
        elif delta.y != 0:
            preferred_step_vector = coordinates.Coords(0, 1 if delta.y > 0 else -1)

        if not preferred_step_vector:
            return Action.TURN_LEFT

        action: Optional[Action] = None
        if current_facing.value == preferred_step_vector:
            action = Action.STEP_FORWARD
            next_pos_candidate = current_pos + current_facing.value
            next_tile_desc_candidate = knowledge.visible_tiles.get(next_pos_candidate)
            if not allow_unsafe_target_step and (not next_tile_desc_candidate or not is_tile_safe(next_tile_desc_candidate, consider_mist=True)):
                return None 
        elif current_facing.turn_left().value == preferred_step_vector:
            action = Action.TURN_LEFT
        elif current_facing.turn_right().value == preferred_step_vector:
            action = Action.TURN_RIGHT
        else: 
            action = Action.TURN_LEFT 
        return action

    def _get_escape_mist_action(self, knowledge: characters.ChampionKnowledge, my_pos: coordinates.Coords, my_facing: Facing, is_critical_mist: bool) -> Action:
        if self.menhir_position:
            menhir_tile_desc = knowledge.visible_tiles.get(self.menhir_position)
            is_menhir_misty_on_tile = bool(menhir_tile_desc and menhir_tile_desc.effects and any(eff.type == 'mist' for eff in menhir_tile_desc.effects))

            if my_pos == self.menhir_position and is_menhir_misty_on_tile:
                pass 
            elif not is_menhir_misty_on_tile or \
                 (is_menhir_misty_on_tile and not is_critical_mist and manhattan_distance(my_pos, self.menhir_position) > 1):
                allow_unsafe_step_to_menhir = is_menhir_misty_on_tile and not is_critical_mist
                action_to_menhir = self._get_action_to_target(my_facing, my_pos, self.menhir_position, knowledge, allow_unsafe_target_step=allow_unsafe_step_to_menhir)
                
                if action_to_menhir == Action.STEP_FORWARD:
                    return Action.STEP_FORWARD
                elif action_to_menhir and action_to_menhir != Action.DO_NOTHING :
                    return action_to_menhir
                elif action_to_menhir == Action.DO_NOTHING and not is_menhir_misty_on_tile:
                    return Action.DO_NOTHING

        action_order = [
            (Action.STEP_FORWARD, my_facing.value, 0),
            (Action.TURN_LEFT, my_facing.turn_left().value, 1),
            (Action.TURN_RIGHT, my_facing.turn_right().value, 1),
            (Action.TURN_LEFT, my_facing.turn_left().turn_left().value, 2) 
        ]
        
        for initial_action_for_orientation, step_vector, turns_needed in action_order:
            next_potential_pos = my_pos + step_vector
            tile_at_next_pos = knowledge.visible_tiles.get(next_potential_pos)
            if tile_at_next_pos and is_tile_safe(tile_at_next_pos, consider_mist=True):
                if not (tile_at_next_pos.effects and any(eff.type == 'mist' for eff in tile_at_next_pos.effects)):
                    if turns_needed == 0:
                        return Action.STEP_FORWARD
                    else:
                        self.action_queue.append(Action.STEP_FORWARD)
                        return initial_action_for_orientation
        return Action.TURN_LEFT

    def _get_escape_enemy_action(self, knowledge: characters.ChampionKnowledge, my_pos: coordinates.Coords, my_facing: Facing, enemy_pos_raw: Union[coordinates.Coords, Tuple[int,int]]) -> Action:
        enemy_pos = ensure_coords(enemy_pos_raw)
        action_order = [
            (Action.STEP_FORWARD, my_facing.value, 0),
            (Action.TURN_LEFT, my_facing.turn_left().value, 1),
            (Action.TURN_RIGHT, my_facing.turn_right().value, 1),
            (Action.TURN_LEFT, my_facing.turn_left().turn_left().value, 2)
        ]
        best_flee_option: Optional[Tuple[Action, int, int]] = None
        current_dist_to_enemy = manhattan_distance(my_pos, enemy_pos)

        for initial_action_for_orientation, step_vector, turns_needed in action_order:
            next_potential_pos = my_pos + step_vector
            tile_at_next_pos = knowledge.visible_tiles.get(next_potential_pos)
            if tile_at_next_pos and is_tile_safe(tile_at_next_pos, consider_mist=True):
                 if not (tile_at_next_pos.effects and any(eff.type == 'mist' for eff in tile_at_next_pos.effects)):
                    new_dist = manhattan_distance(next_potential_pos, enemy_pos)
                    if new_dist > current_dist_to_enemy:
                        action_to_take_candidate = Action.STEP_FORWARD if turns_needed == 0 else initial_action_for_orientation
                        if best_flee_option is None or \
                           new_dist > best_flee_option[1] or \
                           (new_dist == best_flee_option[1] and turns_needed < best_flee_option[2]):
                            best_flee_option = (action_to_take_candidate, new_dist, turns_needed)
        
        if best_flee_option:
            action_to_take = best_flee_option[0]
            if action_to_take != Action.STEP_FORWARD and best_flee_option[2] > 0 :
                self.action_queue.append(Action.STEP_FORWARD)
            return action_to_take

        enemy_is_adj = manhattan_distance(my_pos, enemy_pos) == 1
        if enemy_is_adj:
            vec_to_enemy = enemy_pos - my_pos 
            if my_facing.value == vec_to_enemy:
                return Action.ATTACK
        return Action.TURN_LEFT

    def decide(self, knowledge: characters.ChampionKnowledge) -> Action:
        if self.action_queue:
            action_to_take = self.action_queue.pop(0)
            if self.current_facing:
                if action_to_take == Action.TURN_LEFT: self.current_facing = self.current_facing.turn_left()
                elif action_to_take == Action.TURN_RIGHT: self.current_facing = self.current_facing.turn_right()
            self.last_action = action_to_take
            return action_to_take

        kp_x = knowledge.position.x if hasattr(knowledge.position, 'x') else knowledge.position[0]
        kp_y = knowledge.position.y if hasattr(knowledge.position, 'y') else knowledge.position[1]
        my_pos = coordinates.Coords(kp_x, kp_y)

        my_tile_desc = knowledge.visible_tiles.get(my_pos)
        if not my_tile_desc or not my_tile_desc.character: return Action.DO_NOTHING

        my_facing = my_tile_desc.character.facing
        my_name = my_tile_desc.character.controller_name
        self.current_facing = my_facing
        
        self._find_menhir_in_visible(knowledge)
        
        is_critical_mist, is_warning_mist = self._update_mist_memory_and_threat_levels(knowledge, my_pos)
        action_to_take = random.choice([Action.TURN_LEFT, Action.TURN_RIGHT])

        if is_critical_mist:
            action_to_take = self._get_escape_mist_action(knowledge, my_pos, my_facing, True)
        else:
            closest_enemy_pos = find_nearest_enemy(knowledge, my_pos, my_name)
            if closest_enemy_pos:
                action_to_take = self._get_escape_enemy_action(knowledge, my_pos, my_facing, closest_enemy_pos)
            elif is_warning_mist or (not closest_enemy_pos):
                potion_pos = find_nearest_potion(knowledge, my_pos)
                
                if is_warning_mist and self.menhir_position:
                    menhir_action = self._get_action_to_target(my_facing, my_pos, self.menhir_position, knowledge, allow_unsafe_target_step=True)
                    if menhir_action == Action.STEP_FORWARD: action_to_take = Action.STEP_FORWARD
                    elif menhir_action and menhir_action != Action.DO_NOTHING:
                        action_to_take = menhir_action
                        if manhattan_distance(my_pos, self.menhir_position) == 1 or \
                           (manhattan_distance(my_pos, self.menhir_position) <=2 and menhir_action != Action.STEP_FORWARD):
                             self.action_queue.append(Action.STEP_FORWARD)
                    elif menhir_action == Action.DO_NOTHING:
                        action_to_take = random.choice([Action.TURN_LEFT, Action.TURN_RIGHT, Action.DO_NOTHING])
                    elif menhir_action is None and is_warning_mist:
                        action_to_take = self._get_escape_mist_action(knowledge, my_pos, my_facing, False) 
                
                elif potion_pos: 
                    action_to_potion = self._get_action_to_target(my_facing, my_pos, potion_pos, knowledge)
                    if action_to_potion == Action.STEP_FORWARD:
                        action_to_take = Action.STEP_FORWARD
                    elif action_to_potion and action_to_potion != Action.DO_NOTHING :
                        action_to_take = action_to_potion
                        if manhattan_distance(my_pos, potion_pos) == 1 or \
                           (manhattan_distance(my_pos, potion_pos) <=2 and action_to_potion != Action.STEP_FORWARD):
                           self.action_queue.append(Action.STEP_FORWARD)
                
                elif self.menhir_position and not is_warning_mist:
                    menhir_action = self._get_action_to_target(my_facing, my_pos, self.menhir_position, knowledge)
                    if menhir_action == Action.STEP_FORWARD: action_to_take = Action.STEP_FORWARD
                    elif menhir_action and menhir_action != Action.DO_NOTHING:
                        action_to_take = menhir_action
                        if manhattan_distance(my_pos, self.menhir_position) == 1 or \
                           (manhattan_distance(my_pos, self.menhir_position) <=2 and menhir_action != Action.STEP_FORWARD):
                             self.action_queue.append(Action.STEP_FORWARD)
                    elif menhir_action == Action.DO_NOTHING:
                        action_to_take = random.choice([Action.TURN_LEFT, Action.TURN_RIGHT, Action.DO_NOTHING])

        if self.current_facing:
            if action_to_take == Action.TURN_LEFT: self.current_facing = self.current_facing.turn_left()
            elif action_to_take == Action.TURN_RIGHT: self.current_facing = self.current_facing.turn_right()
        
        self.last_action = action_to_take
        return action_to_take

    def praise(self, score: int) -> None:
        pass 

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena_name = arena_description.name
        self.menhir_position = None
        self.current_facing = None
        self.last_action = None
        self.action_queue = []
        self.last_seen_mist_coords = set()
        self.mist_warning_active = False
        fixed_menhirs_tuples = {
            'isolated_shrine': (9, 9),
            'lone_sanctum': (9, 9),
        }
        if arena_description.name in fixed_menhirs_tuples:
            raw_coords = fixed_menhirs_tuples[arena_description.name]
            self.menhir_position = coordinates.Coords(raw_coords[0], raw_coords[1])

    @property
    def name(self) -> str: return f"Pirat{self.first_name}"
    @property
    def preferred_tabard(self) -> characters.Tabard: return characters.Tabard.PIRAT

POTENTIAL_CONTROLLERS = [PiratController("Pirat")]

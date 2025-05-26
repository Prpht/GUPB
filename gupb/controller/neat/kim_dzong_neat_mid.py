import random
from typing import Optional, List, Set, Tuple, Dict, cast, Deque
import collections # Dla deque do historii akcji

from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import effects
from gupb.model import tiles
from gupb.model import weapons
from gupb.model import consumables 
from gupb.model.characters import Facing, ChampionKnowledge, Action, ChampionDescription
from gupb.model.coordinates import Coords, add_coords, sub_coords

from gupb.controller import Controller

# Implementacja brakującej funkcji manhattan_distance
def manhattan_distance(coord1: Coords, coord2: Coords) -> int:
    return abs(coord1[0] - coord2[0]) + abs(coord1[1] - coord2[1])

# Definicje typów broni dla ułatwienia
WEAPON_REACH_STATIC: Dict[str, int] = {
    "knife": 1, "sword": 3, "axe": 1, "amulet": 2,
    "bow_unloaded": 0, "bow_loaded": 5, "scroll": 0,
}

def get_weapon_reach(weapon_name: str) -> int:
    # Bezpośrednie użycie słownika, ponieważ weapons.WEAPONS może nie istnieć
    return WEAPON_REACH_STATIC.get(weapon_name, 0)

# Nazwy map
MAPS_WITH_TREES = ["ordinary_chaos"] # Przykładowe nazwy
MAPS_WITHOUT_TREES = ["lone_sanctum", "fisher_island", "isolated_shrine", "dungeon", "island", "archipelago", "mini", "wasteland"] 

HARMFUL_EFFECT_TYPES = {
    "mist",
    "fire",
}

class KimDzongNeatMidController(Controller):
    def __init__(self, first_name: str = "Kim Dzong Neat v_2"):
        self.first_name: str = first_name
        
        self.current_state: str = "INITIAL_ASSESSMENT"
        self.map_strategy: str = "UNKNOWN" 
        self.target_coord: Optional[Coords] = None 
        self.path: List[Coords] = []
        
        self.spin_actions_in_bush: List[Action] = [Action.TURN_RIGHT, Action.TURN_RIGHT, Action.DO_NOTHING, Action.TURN_LEFT, Action.DO_NOTHING]
        self.spin_idx: int = 0
        
        self.last_known_mist_coords: Set[Coords] = set()
        self.known_map_tiles: Dict[Coords, tiles.TileDescription] = {}
        self.map_dimensions: Optional[Tuple[Coords, Coords]] = None
        self.center_coord: Optional[Coords] = None
        self.known_menhir_coord: Optional[Coords] = None

        self.turn_counter: int = 0
        self.flee_attempts_in_a_row: int = 0
        self.actions_history: Deque[bool] = collections.deque(maxlen=4) 
        self.last_scroll_use_turn: int = -10 
        self.bot_moved_or_turned_this_turn : bool = False 
        self.arena_name_printed_this_game: bool = False

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KimDzongNeatMidController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.current_state = "INITIAL_ASSESSMENT"
        self.map_strategy = "UNKNOWN"
        self.target_coord = None
        self.path = []
        self.spin_idx = 0
        self.last_known_mist_coords = set()
        self.known_map_tiles = {}
        self.map_dimensions = None
        self.center_coord = None
        self.known_menhir_coord = None
        self.turn_counter = 0
        self.flee_attempts_in_a_row = 0
        self.actions_history.clear()
        self.last_scroll_use_turn = -10
        self.bot_moved_or_turned_this_turn = False
        
        current_arena_name = "default_arena"
        if hasattr(arena_description, 'name'):
             current_arena_name = arena_description.name
        
        if not self.arena_name_printed_this_game:
            #print(f"Bot {self.name} gra na mapie: {current_arena_name}") 
            self.arena_name_printed_this_game = True

        if current_arena_name in MAPS_WITH_TREES:
            self.map_strategy = "TREES"
            self.current_state = "SEARCHING_FOR_TREE"
        elif current_arena_name in MAPS_WITHOUT_TREES:
            self.map_strategy = "NO_TREES_CENTER"
            self.current_state = "GOING_TO_CENTER_OR_MENHIR"
        else: 
            self.map_strategy = "UNKNOWN_CENTER_THEN_TREES"
            self.current_state = "GOING_TO_CENTER_OR_MENHIR"

        if hasattr(arena_description, 'terrain') and isinstance(arena_description.terrain, dict):
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')
            has_terrain_data = False
            for coord, tile_desc in arena_description.terrain.items():
                # coord jest już typu Coords, nie trzeba konwertować
                self.known_map_tiles[coord] = cast(tiles.TileDescription, tile_desc)
                min_x, min_y = min(min_x, coord[0]), min(min_y, coord[1])
                max_x, max_y = max(max_x, coord[0]), max(max_y, coord[1])
                if tile_desc.type == "menhir":
                    self.known_menhir_coord = coord
                has_terrain_data = True
            
            if has_terrain_data:
                self.map_dimensions = (Coords(int(min_x), int(min_y)), Coords(int(max_x), int(max_y)))
                self.center_coord = Coords((int(min_x) + int(max_x)) // 2, (int(min_y) + int(max_y)) // 2)
        
        if self.current_state == "GOING_TO_CENTER_OR_MENHIR":
            if self.known_menhir_coord:
                self.target_coord = self.known_menhir_coord
            elif self.center_coord:
                 self.target_coord = self.center_coord
            else:
                 self.current_state = "IDLE_AT_TARGET"

    def _update_knowledge(self, knowledge: ChampionKnowledge):
        self.turn_counter += 1
        for coord, tile_description in knowledge.visible_tiles.items():
            self.known_map_tiles[coord] = tile_description
            if tile_description.type == "menhir":
                self.known_menhir_coord = coord
            if self.map_strategy == "UNKNOWN_CENTER_THEN_TREES" and tile_description.type == "forest":
                #print(f"Bot {self.name} znalazł drzewo na nieznanej mapie. Zmiana strategii na TREES.")
                self.map_strategy = "TREES"
                self.current_state = "SEARCHING_FOR_TREE"
                self.target_coord = None 
                self.path = []

        newly_seen_mist = set()
        for coord, tile_description in knowledge.visible_tiles.items():
            if tile_description.effects:
                for effect in tile_description.effects:
                    if effect.type == "mist":  # Użyj tekstu zamiast effects.EffectDescription.MIST
                        newly_seen_mist.add(coord)
        
        if newly_seen_mist:
            self.last_known_mist_coords.update(newly_seen_mist)

    def _get_player_danger_zones(self, knowledge: ChampionKnowledge) -> Set[Coords]:
        danger_zones = set()
        # Użyj visible_tiles zamiast visible_champions (które może nie istnieć)
        for coord, tile_desc in knowledge.visible_tiles.items():
            if tile_desc.character is not None and coord != knowledge.position:
                player_pos = coord
                player_facing = tile_desc.character.facing
                for dx in [-1, 0, 1]:
                    for dy in [-1, 0, 1]:
                        if dx == 0 and dy == 0: continue
                        danger_zones.add(Coords(player_pos[0] + dx, player_pos[1] + dy))
                forward_vector = player_facing.value
                danger_zones.add(add_coords(player_pos, forward_vector))
                danger_zones.add(add_coords(player_pos, Coords(forward_vector[0] * 2, forward_vector[1] * 2)))
        return danger_zones

    def _get_occupied_by_players_coords(self, knowledge: ChampionKnowledge) -> Set[Coords]:
        occupied = set()
        for coord, tile_desc in knowledge.visible_tiles.items():
            if tile_desc.character is not None and coord != knowledge.position:
                occupied.add(coord)
        return occupied

    def _is_tile_safe(self, target_coord: Coords, knowledge: ChampionKnowledge,
                      player_danger_zones: Set[Coords],
                      occupied_by_players: Set[Coords],
                      mist_coords: Set[Coords],
                      allow_player_zones_if_fleeing: bool = False,
                      allow_stepping_on_player_if_fleeing: bool = False) -> bool:
        tile_desc = self.known_map_tiles.get(target_coord)
        if not tile_desc or tile_desc.type in ["wall", "sea"]: return False

        if tile_desc.effects: 
            for effect in tile_desc.effects:
                if effect.type in HARMFUL_EFFECT_TYPES: return False
        
        if target_coord in mist_coords: return False

        if target_coord in occupied_by_players:
            if not (allow_stepping_on_player_if_fleeing and self.current_state == "FLEEING_MIST"):
                return False

        if target_coord in player_danger_zones:
            if not (allow_player_zones_if_fleeing and self.current_state == "FLEEING_MIST"):
                return False
        return True

    def _bfs_path(self, start: Coords, end: Coords, knowledge: ChampionKnowledge,
                  player_danger_zones: Set[Coords],
                  occupied_by_players: Set[Coords],
                  mist_coords_to_avoid: Set[Coords],
                  allow_player_zones: bool = False,
                  allow_stepping_on_player: bool = False) -> List[Coords]:
        queue: List[Tuple[Coords, List[Coords]]] = [(start, [])]
        visited: Set[Coords] = {start}
        
        while queue:
            current_pos, path_taken = queue.pop(0)
            if current_pos == end: return path_taken

            for dx, dy in [(0, -1), (1, 0), (0, 1), (-1, 0)]:
                next_pos = Coords(current_pos[0] + dx, current_pos[1] + dy)
                if next_pos not in visited and \
                   self._is_tile_safe(next_pos, knowledge, player_danger_zones, occupied_by_players, mist_coords_to_avoid,
                                      allow_player_zones_if_fleeing=allow_player_zones,
                                      allow_stepping_on_player_if_fleeing=allow_stepping_on_player):
                    visited.add(next_pos)
                    queue.append((next_pos, path_taken + [next_pos]))
        return []

    def _get_move_action_to_target(self, current_pos: Coords, current_facing: Facing, target_pos: Coords) -> Action:
        if current_pos == target_pos: return Action.DO_NOTHING
        
        diff_x = target_pos[0] - current_pos[0]
        diff_y = target_pos[1] - current_pos[1]

        required_facing: Optional[Facing] = None
        if diff_x == 1 and diff_y == 0: required_facing = Facing.RIGHT
        elif diff_x == -1 and diff_y == 0: required_facing = Facing.LEFT
        elif diff_x == 0 and diff_y == 1: required_facing = Facing.DOWN
        elif diff_x == 0 and diff_y == -1: required_facing = Facing.UP
        
        if required_facing:
            if current_facing == required_facing:
                return Action.STEP_FORWARD
            else:
                if current_facing.turn_right() == required_facing: return Action.TURN_RIGHT
                elif current_facing.turn_left() == required_facing: return Action.TURN_LEFT
                else: return Action.TURN_RIGHT
        return Action.DO_NOTHING

    def _find_empty_bushes(self, knowledge: ChampionKnowledge, occupied_by_players: Set[Coords]) -> List[Coords]:
        empty_bushes = []
        for coord, tile_description in self.known_map_tiles.items():
            if tile_description.type == "forest" and coord not in occupied_by_players:
                empty_bushes.append(coord)
        empty_bushes.sort(key=lambda c: manhattan_distance(knowledge.position, c))
        return empty_bushes

    def _get_flee_destination(self, my_pos: Coords, knowledge: ChampionKnowledge,
                               player_danger_zones: Set[Coords], occupied_by_players: Set[Coords]) -> Optional[Coords]:
        if not self.last_known_mist_coords: return None

        avg_mist_x = sum(c[0] for c in self.last_known_mist_coords) / len(self.last_known_mist_coords)
        avg_mist_y = sum(c[1] for c in self.last_known_mist_coords) / len(self.last_known_mist_coords)

        possible_destinations = []
        for radius in range(1, 6):
            for dx_try in range(-radius, radius + 1):
                for dy_try in range(-radius, radius + 1):
                    if abs(dx_try) + abs(dy_try) != radius: continue
                    
                    potential_dest = Coords(my_pos[0] + dx_try, my_pos[1] + dy_try)
                    if potential_dest not in self.known_map_tiles: continue
                    
                    if self._is_tile_safe(potential_dest, knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords, True, True) and potential_dest not in self.last_known_mist_coords:
                        dist_to_avg_mist = (potential_dest[0] - avg_mist_x)**2 + (potential_dest[1] - avg_mist_y)**2
                        score = dist_to_avg_mist  
                        possible_destinations.append({'coord': potential_dest, 'score': score, 'distance_from_self': radius})
        
        if not possible_destinations: return None
        
        possible_destinations.sort(key=lambda x: (-x['score'], x['distance_from_self']))
        return possible_destinations[0]['coord']

    def _can_attack_target_with_facing(self, my_pos: Coords, my_facing: Facing, weapon_name: str, target_pos: Coords, knowledge: ChampionKnowledge) -> bool:
        reach = get_weapon_reach(weapon_name)
        if reach == 0 and weapon_name != "scroll": return False

        if weapon_name in ["sword", "knife", "amulet", "bow_loaded"]:
            for i in range(1, reach + 1):
                current_check_tile = add_coords(my_pos, Coords(my_facing.value[0] * i, my_facing.value[1] * i))
                if current_check_tile == target_pos:
                    for j in range(1, i):
                        intermediate_tile = add_coords(my_pos, Coords(my_facing.value[0] * j, my_facing.value[1] * j))
                        tile_desc = self.known_map_tiles.get(intermediate_tile)
                        if tile_desc:
                            if tile_desc.type in ["wall", "sea"]: return False
                            if tile_desc.character and intermediate_tile != target_pos : return False 
                        elif intermediate_tile != target_pos:
                             return False
                    return True
                
                tile_desc_on_line = self.known_map_tiles.get(current_check_tile)
                if tile_desc_on_line:
                    if tile_desc_on_line.type in ["wall", "sea"]: break
                    if tile_desc_on_line.character and current_check_tile != target_pos: break

            return False
        elif weapon_name == "axe":
            pattern_relative_to_pos: List[Coords] = []
            if my_facing == Facing.UP: pattern_relative_to_pos = [Coords(0,-1), Coords(-1,-1), Coords(1,-1)]
            elif my_facing == Facing.RIGHT: pattern_relative_to_pos = [Coords(1,0), Coords(1,-1), Coords(1,1)]
            elif my_facing == Facing.DOWN: pattern_relative_to_pos = [Coords(0,1), Coords(-1,1), Coords(1,1)]
            else:
                pattern_relative_to_pos = [Coords(-1,0), Coords(-1,-1), Coords(-1,1)]
            
            for relative_coord in pattern_relative_to_pos:
                if add_coords(my_pos, relative_coord) == target_pos:
                    return True
            return False
        return False

    def _handle_combat(self, knowledge: ChampionKnowledge) -> Optional[Action]:
        my_pos = knowledge.position
        
        # Bot zawsze widzi siebie w visible_tiles
        my_tile = knowledge.visible_tiles[my_pos]
        my_weapon_name = my_tile.character.weapon.name
        my_facing = my_tile.character.facing
    
        if not any(self.actions_history) and len(self.actions_history) == self.actions_history.maxlen:
            return None
    
        if my_weapon_name == "scroll":
            # Poprawka: użyj wszystkich wymaganych pól TileDescription
            default_tile = tiles.TileDescription(
                type="land",
                loot=None,
                character=None,
                consumable=None,
                effects=[]
            )
            if self.known_map_tiles.get(my_pos, default_tile).type == "menhir":
                self.last_scroll_use_turn = self.turn_counter
                return Action.ATTACK
            
            for coord, tile_desc in knowledge.visible_tiles.items():
                if tile_desc.character is not None and coord != my_pos:
                    if manhattan_distance(my_pos, coord) <= 2:
                        if coord not in self.last_known_mist_coords and \
                           (not self.known_map_tiles.get(coord) or self.known_map_tiles.get(coord).type != "forest"):
                            self.last_scroll_use_turn = self.turn_counter
                            return Action.ATTACK 
            
            if self.turn_counter - self.last_scroll_use_turn >= 7:
                self.last_scroll_use_turn = self.turn_counter
                return Action.ATTACK
            return None
    
        for coord, tile_desc in knowledge.visible_tiles.items():
            if tile_desc.character is not None and coord != my_pos:
                target_tile_desc = self.known_map_tiles.get(coord)
                if target_tile_desc and target_tile_desc.type == "forest": continue
                if coord in self.last_known_mist_coords: continue
    
                if self._can_attack_target_with_facing(my_pos, my_facing, my_weapon_name, coord, knowledge):
                    return Action.ATTACK
        return None

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        try:
            self._update_knowledge(knowledge)
            my_pos = knowledge.position

            # Bot zawsze widzi siebie
            my_tile = knowledge.visible_tiles[my_pos]
            my_facing = my_tile.character.facing

            newly_seen_mist_this_turn = set()
            for coord, tile_desc in knowledge.visible_tiles.items():
                if tile_desc.effects:
                    for effect in tile_desc.effects:
                        if effect.type == "mist":  # Użyj tekstu zamiast effects.EffectDescription.MIST
                            newly_seen_mist_this_turn.add(coord)

            player_danger_zones = self._get_player_danger_zones(knowledge)
            occupied_by_players = self._get_occupied_by_players_coords(knowledge)
            self.bot_moved_or_turned_this_turn = False

            if (my_pos in self.last_known_mist_coords or newly_seen_mist_this_turn) and \
               self.current_state != "FLEEING_MIST":
                #print(f"Bot {self.name} wykrył mgłę. Zmiana stanu na FLEEING_MIST.")
                self.current_state = "FLEEING_MIST"
                self.path = []
                self.target_coord = None
                self.flee_attempts_in_a_row = 0

            combat_action = self._handle_combat(knowledge)
            if combat_action:
                self.actions_history.append(False) 
                return combat_action

            next_action: Action = Action.DO_NOTHING

            if self.current_state == "INITIAL_ASSESSMENT":
                 if self.map_strategy == "TREES": self.current_state = "SEARCHING_FOR_TREE"
                 elif self.map_strategy in ["NO_TREES_CENTER", "UNKNOWN_CENTER_THEN_TREES"]:
                     self.current_state = "GOING_TO_CENTER_OR_MENHIR"
                     if self.known_menhir_coord: self.target_coord = self.known_menhir_coord
                     elif self.center_coord: self.target_coord = self.center_coord
                     else: self.current_state = "IDLE_AT_TARGET"
                 else:
                     self.current_state = "IDLE_AT_TARGET"

            if self.current_state == "GOING_TO_CENTER_OR_MENHIR":
                if self.target_coord and my_pos == self.target_coord:
                    self.current_state = "IDLE_AT_TARGET"
                    self.path = []
                elif not self.path and self.target_coord:
                    self.path = self._bfs_path(my_pos, self.target_coord, knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords)

                if self.path:
                    next_step_coord = self.path[0]
                    action_to_target = self._get_move_action_to_target(my_pos, my_facing, next_step_coord)
                    if action_to_target == Action.STEP_FORWARD:
                        if self._is_tile_safe(next_step_coord, knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords):
                            self.path.pop(0)
                            next_action = Action.STEP_FORWARD
                        else: self.path = []; self.target_coord = None
                    else: next_action = action_to_target
                elif self.target_coord:
                    next_action = Action.TURN_RIGHT
                else:
                    self.current_state = "IDLE_AT_TARGET"

            elif self.current_state == "SEARCHING_FOR_TREE":
                if self.target_coord and my_pos == self.target_coord:
                    self.current_state = "IN_TREE_IDLE"; self.path = []; self.spin_idx = 0
                    next_action = self.spin_actions_in_bush[self.spin_idx]
                else:
                    if not self.path or (self.path and not self._is_tile_safe(self.path[0], knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords)):
                        empty_bushes = self._find_empty_bushes(knowledge, occupied_by_players)
                        if empty_bushes:
                            self.target_coord = empty_bushes[0]
                            self.path = self._bfs_path(my_pos, self.target_coord, knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords)
                        else:
                            self.target_coord = None; self.path = []
                            if self.map_strategy == "TREES" and self.turn_counter > 30:
                                self.current_state = "GOING_TO_CENTER_OR_MENHIR"; self.map_strategy = "NO_TREES_CENTER"
                                self.target_coord = self.center_coord if self.center_coord else my_pos

                    if self.path:
                        next_step_coord = self.path[0]
                        action_to_target = self._get_move_action_to_target(my_pos, my_facing, next_step_coord)
                        if action_to_target == Action.STEP_FORWARD:
                            if self._is_tile_safe(next_step_coord, knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords):
                                self.path.pop(0); next_action = Action.STEP_FORWARD
                            else: self.path = []; self.target_coord = None
                        else: next_action = action_to_target
                    elif self.target_coord :
                        next_action = Action.TURN_RIGHT
                    else:
                        next_action = Action.TURN_RIGHT

            elif self.current_state == "IN_TREE_IDLE":
                current_tile_desc = self.known_map_tiles.get(my_pos)
                if not current_tile_desc or current_tile_desc.type != "forest":
                    self.current_state = "SEARCHING_FOR_TREE"; self.target_coord = None
                    next_action = Action.TURN_RIGHT
                else:
                    self.spin_idx = (self.spin_idx + 1) % len(self.spin_actions_in_bush)
                    next_action = self.spin_actions_in_bush[self.spin_idx]

            elif self.current_state == "IDLE_AT_TARGET":
                self.spin_idx = (self.spin_idx + 1) % len(self.spin_actions_in_bush)
                next_action = self.spin_actions_in_bush[self.spin_idx]
                if not self.known_menhir_coord and self.target_coord != self.known_menhir_coord:
                     for coord_tile, desc_tile in knowledge.visible_tiles.items():
                         if desc_tile.type == "menhir":
                             self.known_menhir_coord = coord_tile
                             self.current_state = "GOING_TO_CENTER_OR_MENHIR"
                             self.target_coord = coord_tile
                             self.path = []
                             break

            if self.current_state == "FLEEING_MIST":
                self.flee_attempts_in_a_row += 1
                action_taken_fleeing = False
                if self.path and self._is_tile_safe(self.path[0], knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords, True, True):
                    next_step_coord = self.path[0]
                    action_to_target = self._get_move_action_to_target(my_pos, my_facing, next_step_coord)
                    if action_to_target == Action.STEP_FORWARD:
                        self.path.pop(0); self.flee_attempts_in_a_row = 0
                    next_action = action_to_target
                    action_taken_fleeing = True
                else:
                    self.path = []
                    flee_destination = self._get_flee_destination(my_pos, knowledge, player_danger_zones, occupied_by_players)
                    if flee_destination:
                        self.path = self._bfs_path(my_pos, flee_destination, knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords, True, True)
                        if self.path:
                            next_step_coord = self.path[0]
                            action_to_target = self._get_move_action_to_target(my_pos, my_facing, next_step_coord)
                            if action_to_target == Action.STEP_FORWARD:
                                self.path.pop(0); self.flee_attempts_in_a_row = 0
                            next_action = action_to_target
                            action_taken_fleeing = True

                if not action_taken_fleeing:
                    best_panic_move: Optional[Action] = None
                    potential_panic_directions = [my_facing.value, my_facing.turn_right().value, my_facing.turn_left().value]

                    for direction in potential_panic_directions:
                        panic_target_coord = add_coords(my_pos, direction)
                        if self._is_tile_safe(panic_target_coord, knowledge, player_danger_zones, occupied_by_players, self.last_known_mist_coords, True, True) and panic_target_coord not in self.last_known_mist_coords:
                            if direction == my_facing.value:
                                best_panic_move = Action.STEP_FORWARD
                                break
                            elif direction == my_facing.turn_right().value:
                                best_panic_move = Action.TURN_RIGHT
                                break
                            elif direction == my_facing.turn_left().value:
                                best_panic_move = Action.TURN_LEFT
                                break
                            
                    if best_panic_move:
                        next_action = best_panic_move
                        self.flee_attempts_in_a_row = 0
                    else:
                        next_action = Action.TURN_RIGHT if self.flee_attempts_in_a_row % 2 == 0 else Action.TURN_LEFT

                if not self.last_known_mist_coords and not newly_seen_mist_this_turn:
                    #print(f"Bot {self.name} nie widzi już mgły. Powrót do poprzedniej strategii.")
                    if self.map_strategy == "TREES": self.current_state = "SEARCHING_FOR_TREE"
                    else: self.current_state = "GOING_TO_CENTER_OR_MENHIR"
                    self.target_coord = None
                    self.path = []

            self.bot_moved_or_turned_this_turn = next_action in [Action.STEP_FORWARD, Action.TURN_LEFT, Action.TURN_RIGHT]
            self.actions_history.append(self.bot_moved_or_turned_this_turn)

            return next_action
        except Exception:
            return Action.TURN_RIGHT

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIMDZONGNEAT
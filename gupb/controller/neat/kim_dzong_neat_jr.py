import random
from typing import Dict

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import tiles

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
    characters.Action.STEP_BACKWARD,
    characters.Action.DO_NOTHING,
    characters.Action.ATTACK,
]

CIRCLE_PATTERN = [
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
]


class KimDzongNeatJuniorController(controller.Controller):
    def __init__(self, first_name: str = "Kim Dzong Neat v_1"):
        self.first_name: str = first_name
        self.pattern_index = 0
        self.fleeing_from_mist = False
        self.last_position = None
        self.stuck_counter = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KimDzongNeatJuniorController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        if self.last_position == knowledge.position:
            self.stuck_counter += 1
            if self.stuck_counter > 2:  
                self.stuck_counter = 0
                return random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])
        else:
            self.stuck_counter = 0
            self.last_position = knowledge.position
        
        mist_detected = self.detect_mist(knowledge.visible_tiles)
        
        if mist_detected:
            self.fleeing_from_mist = True
            action = self.flee_from_mist(knowledge)
            return action
        else:
            self.fleeing_from_mist = False
            action = CIRCLE_PATTERN[self.pattern_index]
            self.pattern_index = (self.pattern_index + 1) % len(CIRCLE_PATTERN)
            
            if action == characters.Action.STEP_FORWARD and not self.can_move_forward(knowledge):
                return characters.Action.TURN_RIGHT
                
            return action

    def detect_mist(self, visible_tiles: Dict[coordinates.Coords, tiles.TileDescription]) -> bool:
        """Sprawdza czy na widocznych polach znajduje się mgła."""
        for tile_desc in visible_tiles.values():
            if hasattr(tile_desc, 'effects') and tile_desc.effects:
                for effect in tile_desc.effects:
                    if effect.type == "mist":
                        return True
        return False

    def can_move_forward(self, knowledge: characters.ChampionKnowledge) -> bool:
        """Sprawdza czy można iść do przodu."""
        position = knowledge.position
        forward_pos = position + knowledge.facing.value
        visible_tiles = knowledge.visible_tiles
        
        if forward_pos in visible_tiles and self.is_safe_tile(visible_tiles[forward_pos], check_mist=False):
            return True
        return False

    def flee_from_mist(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        """Strategia ucieczki od mgły."""
        safe_directions = self.find_safe_directions(knowledge)
        
        if safe_directions:
            return random.choice(safe_directions)
        else:
            return random.choice([characters.Action.TURN_LEFT, characters.Action.TURN_RIGHT])

    def find_safe_directions(self, knowledge: characters.ChampionKnowledge) -> list:
        """Znajduje kierunki, w których nie ma mgły."""
        position = knowledge.position
        visible_tiles = knowledge.visible_tiles
        
        safe_directions = []
        
        forward_pos = position + knowledge.facing.value
        if forward_pos in visible_tiles and self.is_safe_tile(visible_tiles[forward_pos]):
            safe_directions.append(characters.Action.STEP_FORWARD)
        
        left_facing = knowledge.facing.turn_left()
        left_pos = position + left_facing.value
        if left_pos in visible_tiles and self.is_safe_tile(visible_tiles[left_pos]):
            safe_directions.append(characters.Action.STEP_LEFT)
        
        right_facing = knowledge.facing.turn_right()
        right_pos = position + right_facing.value
        if right_pos in visible_tiles and self.is_safe_tile(visible_tiles[right_pos]):
            safe_directions.append(characters.Action.STEP_RIGHT)
        
        back_facing = knowledge.facing.opposite()
        back_pos = position + back_facing.value
        if back_pos in visible_tiles and self.is_safe_tile(visible_tiles[back_pos]):
            safe_directions.append(characters.Action.STEP_BACKWARD)
        
        return safe_directions

    def is_safe_tile(self, tile_desc: tiles.TileDescription, check_mist: bool = True) -> bool:
        """Sprawdza czy dane pole jest bezpieczne (można na nie wejść i nie ma mgły)."""
      
        if tile_desc.type in ["wall", "sea"]:
            return False
        
        if tile_desc.character is not None:
            return False
        
        if check_mist:
            for effect in tile_desc.effects:
                if effect.type == "mist":
                    return False
        
        return True

    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.pattern_index = 0
        self.fleeing_from_mist = False
        self.last_position = None
        self.stuck_counter = 0

    @property
    def name(self) -> str:
        return self.first_name

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.KIMDZONGNEAT

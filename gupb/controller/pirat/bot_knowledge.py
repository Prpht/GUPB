from typing import Optional, Tuple, Union, Set
from gupb.model import characters, coordinates

from gupb.controller.pirat.pirat_constants import CRITICAL_MIST_RADIUS, WARNING_MIST_RADIUS, POTION_SCAN_RADIUS, ENEMY_THREAT_RADIUS
from gupb.controller.pirat.utils import ensure_coords, manhattan_distance, is_tile_safe


def find_menhir_in_visible(knowledge: characters.ChampionKnowledge) -> Optional[coordinates.Coords]:
    for pos_key, tile_desc in knowledge.visible_tiles.items():
        if tile_desc.type == 'menhir':
            return ensure_coords(pos_key)
    return None

def update_mist_memory_and_threat_levels(
    knowledge: characters.ChampionKnowledge, 
    my_pos: coordinates.Coords,
) -> Tuple[bool, bool, Set[coordinates.Coords]]:
    newly_seen_mist_coords: Set[coordinates.Coords] = set()
    is_critical_mist = False
    is_warning_mist = False

    for i in range(-WARNING_MIST_RADIUS, WARNING_MIST_RADIUS + 1):
        for j in range(-WARNING_MIST_RADIUS, WARNING_MIST_RADIUS + 1):
            distance = abs(i) + abs(j)
            if distance == 0 or distance > WARNING_MIST_RADIUS:
                continue
            
            check_pos_raw = my_pos + coordinates.Coords(i, j)
            check_pos = ensure_coords(check_pos_raw)
            tile_desc = knowledge.visible_tiles.get(check_pos)

            if tile_desc and tile_desc.effects and any(eff.type == 'mist' for eff in tile_desc.effects):
                newly_seen_mist_coords.add(check_pos)
                if distance <= CRITICAL_MIST_RADIUS:
                    is_critical_mist = True
                elif distance <= WARNING_MIST_RADIUS:
                    is_warning_mist = True
    
    return is_critical_mist, is_warning_mist, newly_seen_mist_coords

def find_nearest_enemy(knowledge: characters.ChampionKnowledge, my_pos: coordinates.Coords, my_controller_name: str) -> Optional[coordinates.Coords]:
    min_dist = float('inf')
    closest_enemy_pos_candidate: Optional[Union[coordinates.Coords, Tuple[int,int]]] = None
    
    for pos_key, tile_desc in knowledge.visible_tiles.items():
        if tile_desc.character and tile_desc.character.controller_name != my_controller_name:
            dist_to_enemy = manhattan_distance(my_pos, pos_key)
            if dist_to_enemy < min_dist:
                min_dist = dist_to_enemy
                closest_enemy_pos_candidate = pos_key

    if closest_enemy_pos_candidate and min_dist <= ENEMY_THREAT_RADIUS:
        return ensure_coords(closest_enemy_pos_candidate)
    return None

def find_nearest_potion(knowledge: characters.ChampionKnowledge, my_pos: coordinates.Coords) -> Optional[coordinates.Coords]:
    min_dist = float('inf')
    closest_potion_pos: Optional[coordinates.Coords] = None
    for i in range(-POTION_SCAN_RADIUS, POTION_SCAN_RADIUS + 1):
        for j in range(-POTION_SCAN_RADIUS, POTION_SCAN_RADIUS + 1):
            scan_dist = abs(i) + abs(j)
            if scan_dist == 0 or scan_dist > POTION_SCAN_RADIUS :
                continue
            check_pos_raw = my_pos + coordinates.Coords(i,j)
            check_pos = ensure_coords(check_pos_raw)
            tile_desc = knowledge.visible_tiles.get(check_pos)
            if tile_desc and tile_desc.consumable and tile_desc.consumable.name == 'potion':
                if is_tile_safe(tile_desc, consider_mist=True, allow_potion=True):
                     if not (tile_desc.effects and any(eff.type == 'mist' for eff in tile_desc.effects)):
                        dist_to_potion = manhattan_distance(my_pos, check_pos)
                        if dist_to_potion < min_dist:
                            min_dist = dist_to_potion
                            closest_potion_pos = check_pos
    return closest_potion_pos

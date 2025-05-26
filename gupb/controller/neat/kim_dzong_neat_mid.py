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
WEAPON_REACH: Dict[str, int] = {
    "knife": 1,
    "sword": 3,
    "axe": 1, # Axe ma obszar stożkowy, ale 'reach' może być rozumiany jako główny zasięg
    "amulet": 2, # Amulet ma zasięg w linii prostej
    "bow_unloaded": 0, # Nie strzela
    "bow_loaded": 5, # Zasięg łuku (przykładowo)
    "scroll": 0, # Scroll nie jest bronią do bezpośredniego ataku, ale używa się go przez Action.ATTACK
}
# Obszary działania broni (potrzebne do dokładniejszego celowania, zwłaszcza dla axe)
# Klucz: nazwa broni, Wartość: lista kafelków względnych do pozycji i kierunku gracza
WEAPON_PATTERNS: Dict[str, List[Coords]] = {
    "knife": [Coords(0, -1)],  # Prosto przed siebie na 1 pole (zakładając Y rośnie w dół, -1 to w górę)
    "sword": [Coords(0, -1), Coords(0, -2), Coords(0, -3)],
    "axe": [Coords(0, -1), Coords(-1, -1), Coords(1, -1)], # Stożek 3 pól przed
    "amulet": [Coords(0, -1), Coords(0, -2)], # Linia 2 pola
    "bow_loaded": [Coords(0, -1), Coords(0, -2), Coords(0, -3), Coords(0, -4), Coords(0, -5)],
    # Scroll nie ma wzoru ataku w ten sposób, jego efekt zależy od logiki użycia
}


def get_weapon_reach(weapon_name: str) -> int:
    # Bezpośrednie mapowanie na klasy broni
    weapon_classes = {
        "knife": weapons.Knife,
        "sword": weapons.Sword, 
        "bow_loaded": weapons.Bow,
        "bow_unloaded": weapons.Bow,
        "axe": weapons.Axe,
        "amulet": weapons.Amulet,
        "scroll": weapons.Scroll
    }
    
    weapon_class = weapon_classes.get(weapon_name)
    if weapon_class and hasattr(weapon_class, 'reach'):
        return weapon_class.reach()
    
    # Fallback do stałych wartości
    return WEAPON_REACH.get(weapon_name, 0)


def get_weapon_pattern(weapon_name: str, facing: Facing) -> List[Coords]:
    # Ta funkcja nie jest używana w kodzie, więc można ją uprościć
    base_pattern = WEAPON_PATTERNS.get(weapon_name, [])
    
    # Uproszczona rotacja - zwróć wzór dla kierunku UP
    if get_weapon_reach(weapon_name) > 0:
        reach = get_weapon_reach(weapon_name)
        if weapon_name in ["sword", "knife", "amulet", "bow_loaded"]:
            return [Coords(facing.value[0] * i, facing.value[1] * i) for i in range(1, reach + 1)]
        elif weapon_name == "axe":
            # Wzór topora - 3 pola w kształcie stożca
            if facing == Facing.UP:
                return [Coords(0,-1), Coords(-1,-1), Coords(1,-1)]
            elif facing == Facing.RIGHT:
                return [Coords(1,0), Coords(1,-1), Coords(1,1)]
            elif facing == Facing.DOWN:
                return [Coords(0,1), Coords(-1,1), Coords(1,1)]
            else:  # LEFT
                return [Coords(-1,0), Coords(-1,-1), Coords(-1,1)]
    
    return []


# Nazwy map (do ręcznego wypełnienia na podstawie printów)
MAPS_WITH_TREES = ["ordinary_chaos"] # Przykładowe nazwy
MAPS_WITHOUT_TREES = ["lone_sanctum", "fisher_island", "isolated_shrine", "dungeon", "island", "archipelago", "mini", "wasteland"] 


HARMFUL_EFFECT_TYPES = {
    "mist",
    "fire",
}


class KimDzongNeatMidController(Controller):
    def __init__(self, first_name: str = "Kim Dzong Neat v_2"): # Zwiększona wersja
        self.first_name: str = first_name
        
        # Stany i cele
        self.current_state: str = "INITIAL_ASSESSMENT" # Nowy stan początkowy
        self.map_strategy: str = "UNKNOWN" # UNKNOWN, TREES, NO_TREES_CENTER, UNKNOWN_CENTER_THEN_TREES
        self.target_coord: Optional[Coords] = None # Ogólny cel (drzewo, centrum, menhir)
        self.path: List[Coords] = []
        
        # Drzewa
        self.spin_actions_in_bush: List[Action] = [Action.TURN_RIGHT, Action.TURN_RIGHT, Action.DO_NOTHING, Action.TURN_LEFT, Action.DO_NOTHING]
        self.spin_idx: int = 0
        
        # Wiedza o mapie i mgle
        self.last_known_mist_coords: Set[Coords] = set()
        self.known_map_tiles: Dict[Coords, tiles.TileDescription] = {}
        self.map_dimensions: Optional[Tuple[Coords, Coords]] = None # (min_coords, max_coords)
        self.center_coord: Optional[Coords] = None
        self.known_menhir_coord: Optional[Coords] = None

        # Liczniki i historia
        self.turn_counter: int = 0
        self.flee_attempts_in_a_row: int = 0
        self.actions_history: Deque[bool] = collections.deque(maxlen=4) # True jeśli ruch/obrót, False jeśli DO_NOTHING/ATTACK
        self.last_scroll_use_turn: int = -10 # Aby móc użyć scrolla na początku
        self.bot_moved_or_turned_this_turn : bool = False # Flaga dla historii akcji

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
        self.arena_name_printed_this_game = False

        if hasattr(arena_description, 'name') and not self.arena_name_printed_this_game:
            #print(f"Bot {self.name} gra na mapie: {arena_description.name}") # Print nazwy mapy
            self.arena_name_printed_this_game = True # Zapobiega wielokrotnemu printowaniu (choć reset jest raz na grę)

            if arena_description.name in MAPS_WITH_TREES:
                self.map_strategy = "TREES"
                self.current_state = "SEARCHING_FOR_TREE"
            elif arena_description.name in MAPS_WITHOUT_TREES:
                self.map_strategy = "NO_TREES_CENTER"
                self.current_state = "GOING_TO_CENTER_OR_MENHIR"
            else: # Mapa nieznana
                self.map_strategy = "UNKNOWN_CENTER_THEN_TREES"
                self.current_state = "GOING_TO_CENTER_OR_MENHIR" # Domyślnie idź do centrum, szukaj drzew

        # Pre-populate known_map with arena terrain
        if hasattr(arena_description, 'terrain') and isinstance(arena_description.terrain, dict):
            min_x, min_y = float('inf'), float('inf')
            max_x, max_y = float('-inf'), float('-inf')
            for coord, tile_desc in arena_description.terrain.items():
                self.known_map_tiles[coord] = cast(tiles.TileDescription, tile_desc)
                min_x, min_y = min(min_x, coord[0]), min(min_y, coord[1])
                max_x, max_y = max(max_x, coord[0]), max(max_y, coord[1])
                if tile_desc.type == "menhir":
                    self.known_menhir_coord = coord

            if min_x != float('inf'): # Jeśli mapa nie jest pusta
                self.map_dimensions = (Coords(int(min_x), int(min_y)), Coords(int(max_x), int(max_y)))
                self.center_coord = Coords((int(min_x) + int(max_x)) // 2, (int(min_y) + int(max_y)) // 2)
        
        if self.current_state == "GOING_TO_CENTER_OR_MENHIR":
            if self.known_menhir_coord:
                self.target_coord = self.known_menhir_coord
            elif self.center_coord:
                 self.target_coord = self.center_coord
            # Jeśli nie ma ani menhiru ani centrum (dziwna mapa?), bot będzie musiał eksplorować


    def _update_knowledge(self, knowledge: ChampionKnowledge):
        self.turn_counter += 1
        # Aktualizacja mapy na podstawie widocznych kafelków
        for coord, tile_description in knowledge.visible_tiles.items():
            self.known_map_tiles[coord] = tile_description
            if tile_description.type == "menhir": # Zapamiętaj menhir jeśli go zobaczysz
                self.known_menhir_coord = coord
            if self.map_strategy == "UNKNOWN_CENTER_THEN_TREES" and tile_description.type == "forest":
                # Zobaczyliśmy drzewo na nieznanej mapie, przełączamy strategię
                #print(f"Bot {self.name} znalazł drzewo na nieznanej mapie. Zmiana strategii na TREES.")
                self.map_strategy = "TREES"
                self.current_state = "SEARCHING_FOR_TREE"
                self.target_coord = None # Zresetuj cel, aby poszukać drzewa
                self.path = []

        # Aktualizacja pozycji mgły
        newly_seen_mist = set()
        for coord, tile_description in knowledge.visible_tiles.items():
            if tile_description.effects:
                for effect in tile_description.effects:
                    if effect.type == "mist":
                        newly_seen_mist.add(coord)
        
        # Usuń stare koordynaty mgły, których już nie widać i nie sąsiadują z nowo widzianą mgłą
        # To jest uproszczenie, pełne śledzenie rozprzestrzeniania się mgły jest trudne
        current_and_adjacent_to_new_mist = set(newly_seen_mist)
        for m_coord in newly_seen_mist:
            for dx in [-1,0,1]:
                for dy in [-1,0,1]:
                    current_and_adjacent_to_new_mist.add(Coords(m_coord[0]+dx, m_coord[1]+dy))
        
        self.last_known_mist_coords = {c for c in self.last_known_mist_coords if c in current_and_adjacent_to_new_mist}
        self.last_known_mist_coords.update(newly_seen_mist)


    def _get_player_danger_zones(self, knowledge: ChampionKnowledge) -> Set[Coords]:
        danger_zones = set()
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

        if tile_desc.effects: # Sprawdzanie szkodliwych efektów (mgła, ogień itp.)
            for effect in tile_desc.effects:
                if effect.type in HARMFUL_EFFECT_TYPES: return False
        
        # Sprawdzenie mgły na podstawie self.last_known_mist_coords, bo tile_desc.effects może nie być aktualne dla niewidocznych pól
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
                  mist_coords: Set[Coords],
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
                   self._is_tile_safe(next_pos, knowledge, player_danger_zones, occupied_by_players, mist_coords,
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

    def _get_flee_destination(self, my_pos: Coords, mist_coords: Set[Coords], knowledge: ChampionKnowledge,
                               player_danger_zones: Set[Coords], occupied_by_players: Set[Coords]) -> Optional[Coords]:
        if not mist_coords: return None

        avg_mist_x = sum(c[0] for c in mist_coords) / len(mist_coords)
        avg_mist_y = sum(c[1] for c in mist_coords) / len(mist_coords)

        possible_destinations = []
        for dx_try in range(-3, 4):
            for dy_try in range(-3, 4):
                if dx_try == 0 and dy_try == 0: continue
                
                potential_dest = Coords(my_pos[0] + dx_try, my_pos[1] + dy_try)
                if potential_dest not in self.known_map_tiles: continue
                
                if self._is_tile_safe(potential_dest, knowledge, player_danger_zones, occupied_by_players, mist_coords, True, True):
                    dist_to_avg_mist = (potential_dest[0] - avg_mist_x)**2 + (potential_dest[1] - avg_mist_y)**2
                    dist_to_self = abs(dx_try) + abs(dy_try)
                    score = dist_to_avg_mist - dist_to_self 
                    possible_destinations.append({'coord': potential_dest, 'score': score})
    
        if not possible_destinations: return None
        
        possible_destinations.sort(key=lambda x: x['score'], reverse=True)
        return possible_destinations[0]['coord']


    def _can_attack_target(self, knowledge: ChampionKnowledge, target_champion_pos: Coords) -> bool:
        my_pos = knowledge.position
        my_facing = knowledge.facing
        weapon_name = knowledge.weapon.name
        
        # Sprawdzenie, czy cel jest w zasięgu i wzorze ataku
        # To jest uproszczenie. Idealnie, weapons.WEAPONS[weapon_name].cut_positions() powinno być użyte.
        # Poniżej prosta logika bazująca na liniowym zasięgu.
        
        reach = get_weapon_reach(weapon_name)
        if reach == 0 and weapon_name != "scroll": # Scroll ma zasięg 0, ale atakuje inaczej
             return False

        # Czy cel jest na linii strzału/uderzenia?
        # Dla broni liniowych (miecz, nóż, amulet, łuk)
        if weapon_name in ["sword", "knife", "amulet", "bow_loaded"]:
            for i in range(1, reach + 1):
                target_tile_in_line = add_coords(my_pos, Coords(my_facing.value[0] * i, my_facing.value[1] * i))
                if target_tile_in_line == target_champion_pos:
                    # Sprawdź, czy nie ma przeszkód po drodze (inny gracz, ściana)
                    for j in range(1, i):
                        intermediate_tile = add_coords(my_pos, Coords(my_facing.value[0] * j, my_facing.value[1] * j))
                        if intermediate_tile in self._get_occupied_by_players_coords(knowledge): return False
                        tile_desc = self.known_map_tiles.get(intermediate_tile)
                        if tile_desc and tile_desc.type in ["wall", "sea"]: return False
                    return True # Cel na linii i bez przeszkód
            return False # Cel nie na linii
        elif weapon_name == "axe": # Topór ma inny wzór
            # Wzór dla topora: (0,-1), (-1,-1), (1,-1) względem kierunku UP
            # Musimy transponować ten wzór na aktualny kierunek gracza
            # Uproszczenie: topór trafia na 3 pola przed graczem
            if my_facing == Facing.UP: check_coords = [Coords(0,-1), Coords(-1,-1), Coords(1,-1)]
            elif my_facing == Facing.RIGHT: check_coords = [Coords(1,0), Coords(1,-1), Coords(1,1)]
            elif my_facing == Facing.DOWN: check_coords = [Coords(0,1), Coords(-1,1), Coords(1,1)]
            else: # Facing.LEFT
                check_coords = [Coords(-1,0), Coords(-1,-1), Coords(-1,1)]
            
            for ch_c in check_coords:
                if add_coords(my_pos, ch_c) == target_champion_pos:
                    return True
            return False
        
        return False # Domyślnie dla nieobsługiwanych broni


    def _handle_combat(self, knowledge: ChampionKnowledge, current_mist_coords: Set[Coords]) -> Optional[Action]:
        my_pos = knowledge.position

        # Warunek 4: Bot ruszył się lub obrócił co najmniej raz w ciągu 4 ostatnich tur
        if not any(self.actions_history):
            if len(self.actions_history) == self.actions_history.maxlen and not any(self.actions_history):
                 return None

        # Bot zawsze widzi siebie, więc nie musimy sprawdzać None
        my_tile = knowledge.visible_tiles[my_pos]  # Zawsze dostępne
        my_weapon_name = my_tile.character.weapon.name
        my_facing = my_tile.character.facing

        # Scroll logic
        if my_weapon_name == "scroll":
            # Priorytet 2: Na menhirze
            if self.known_map_tiles.get(my_pos, tiles.TileDescription(type="land",loot=None,character=None, effects=[])).type == "menhir":
                self.last_scroll_use_turn = self.turn_counter
                return Action.ATTACK 

            # Priorytet 3: Na graczu
            for coord, tile_desc in knowledge.visible_tiles.items():
                if tile_desc.character is not None and coord != my_pos:
                    if manhattan_distance(my_pos, coord) <= 2:
                        target_tile_desc = self.known_map_tiles.get(coord)
                        if target_tile_desc and target_tile_desc.type == "forest": 
                            continue
                        if coord in current_mist_coords: 
                            continue
                        
                        self.last_scroll_use_turn = self.turn_counter
                        return Action.ATTACK 

            # Priorytet 4: Co 7 tur
            if self.turn_counter - self.last_scroll_use_turn >= 7:
                self.last_scroll_use_turn = self.turn_counter
                return Action.ATTACK
            return None

        # Standardowy atak bronią
        for coord, tile_desc in knowledge.visible_tiles.items():
            if tile_desc.character is not None and coord != my_pos:
                # Warunek 2: Przeciwnik nie w drzewie
                target_tile_desc = self.known_map_tiles.get(coord)
                if target_tile_desc and target_tile_desc.type == "forest":
                    continue
                
                # Warunek 3: Przeciwnik nie w mgle
                if coord in current_mist_coords:
                    continue

                # Warunek 1: Przeciwnik w zasięgu
                if self._can_attack_target_with_facing(my_pos, my_facing, my_weapon_name, coord):
                    return Action.ATTACK
    
        return None

    def _can_attack_target_with_facing(self, my_pos: Coords, my_facing: Facing, weapon_name: str, target_pos: Coords) -> bool:
        reach = get_weapon_reach(weapon_name)
        if reach == 0 and weapon_name != "scroll":
             return False

        if weapon_name in ["sword", "knife", "amulet", "bow_loaded"]:
            for i in range(1, reach + 1):
                target_tile_in_line = add_coords(my_pos, Coords(my_facing.value[0] * i, my_facing.value[1] * i))
                if target_tile_in_line == target_pos:
                    for j in range(1, i):
                        intermediate_tile = add_coords(my_pos, Coords(my_facing.value[0] * j, my_facing.value[1] * j))
                        intermediate_tile_desc = self.known_map_tiles.get(intermediate_tile)
                        if intermediate_tile_desc:
                            if intermediate_tile_desc.character is not None:
                                return False
                            if intermediate_tile_desc.type in ["wall", "sea"]:
                                return False
                    return True
            return False
        elif weapon_name == "axe":
            if my_facing == Facing.UP: 
                check_coords = [Coords(0,-1), Coords(-1,-1), Coords(1,-1)]
            elif my_facing == Facing.RIGHT: 
                check_coords = [Coords(1,0), Coords(1,-1), Coords(1,1)]
            elif my_facing == Facing.DOWN: 
                check_coords = [Coords(0,1), Coords(-1,1), Coords(1,1)]
            else:
                check_coords = [Coords(-1,0), Coords(-1,-1), Coords(-1,1)]
            
            for ch_c in check_coords:
                if add_coords(my_pos, ch_c) == target_pos:
                    return True
            return False
        
        return False

    def decide(self, knowledge: ChampionKnowledge) -> Action:
        self._update_knowledge(knowledge)
        my_pos = knowledge.position
        
        # Znajdź własną postać w visible_tiles, aby uzyskać facing
        my_facing = None
        my_tile = knowledge.visible_tiles.get(my_pos)
        if my_tile and my_tile.character is not None:
            my_facing = my_tile.character.facing
        
        # Jeśli nie widzimy siebie, użyj domyślnego kierunku
        if my_facing is None:
            my_facing = Facing.UP
        
        current_mist_coords = self.last_known_mist_coords
        
        player_danger_zones = self._get_player_danger_zones(knowledge)
        occupied_by_players = self._get_occupied_by_players_coords(knowledge)
        self.bot_moved_or_turned_this_turn = False

        # Sprawdzenie ataku
        combat_action = self._handle_combat(knowledge, current_mist_coords)
        if combat_action:
            self.actions_history.append(False)
            return combat_action

        # Logika stanów
        if my_pos in current_mist_coords and self.current_state != "FLEEING_MIST":
            self.current_state = "FLEEING_MIST"
            self.path = []
            self.target_coord = None
            self.flee_attempts_in_a_row = 0
        
        # --- INITIAL_ASSESSMENT --- (tylko na początku gry, obsłużone w reset)
        if self.current_state == "INITIAL_ASSESSMENT": # Powinno być już zmienione w reset
             if self.map_strategy == "TREES": self.current_state = "SEARCHING_FOR_TREE"
             else: self.current_state = "GOING_TO_CENTER_OR_MENHIR"


        # --- GOING_TO_CENTER_OR_MENHIR ---
        if self.current_state == "GOING_TO_CENTER_OR_MENHIR":
            if self.known_menhir_coord and (not self.target_coord or self.target_coord != self.known_menhir_coord):
                self.target_coord = self.known_menhir_coord # Preferuj menhir
                self.path = []
            elif not self.target_coord and self.center_coord: # Jeśli nie ma celu lub menhiru, idź do centrum
                self.target_coord = self.center_coord
                self.path = []
            
            if self.target_coord and my_pos == self.target_coord: # Dotarł do celu
                # Co robić w centrum/na menhirze? Na razie kręć się.
                self.current_state = "IDLE_AT_TARGET" 
                self.path = []
                self.target_coord = None
            
            if not self.path and self.target_coord:
                self.path = self._bfs_path(my_pos, self.target_coord, knowledge, player_danger_zones, occupied_by_players, current_mist_coords)

            if self.path:
                next_step_coord = self.path[0]
                action = self._get_move_action_to_target(my_pos, my_facing, next_step_coord)
                if action == Action.STEP_FORWARD:
                    if self._is_tile_safe(next_step_coord, knowledge, player_danger_zones, occupied_by_players, current_mist_coords):
                        self.path.pop(0)
                        self.bot_moved_or_turned_this_turn = True
                        self.actions_history.append(True)
                        return Action.STEP_FORWARD
                    else: # Ścieżka zablokowana
                        self.path = []
                        self.target_coord = None # Spróbuj znaleźć nowy cel (może menhir się pojawił)
                else: # Obrót
                    self.bot_moved_or_turned_this_turn = True
                    self.actions_history.append(True)
                    return action
            
            # Jeśli brak ścieżki/celu, eksploruj
            self.bot_moved_or_turned_this_turn = True
            self.actions_history.append(True)
            return Action.TURN_RIGHT


        # --- SEARCHING_FOR_TREE ---
        elif self.current_state == "SEARCHING_FOR_TREE":
            if self.target_coord and my_pos == self.target_coord:
                self.current_state = "IN_TREE_IDLE"
                self.path = []
                self.spin_idx = 0
                self.bot_moved_or_turned_this_turn = True
                self.actions_history.append(True)
                return self.spin_actions_in_bush[self.spin_idx]

            if not self.path or (self.path and not self._is_tile_safe(self.path[0], knowledge, player_danger_zones, occupied_by_players, current_mist_coords)):
                empty_bushes = self._find_empty_bushes(knowledge, occupied_by_players)
                if empty_bushes:
                    self.target_coord = empty_bushes[0]
                    self.path = self._bfs_path(my_pos, self.target_coord, knowledge, player_danger_zones, occupied_by_players, current_mist_coords)
                else:
                    self.target_coord = None
                    self.path = []
                    # Jeśli nie ma drzew, a strategia to TREES, coś jest nie tak, może przełącz na eksplorację/centrum
                    if self.map_strategy == "TREES" and self.turn_counter > 20: # Po pewnym czasie, jeśli nie znalazł drzewa
                        #print(f"Bot {self.name} nie znalazł drzew na mapie z drzewami. Przełączam na GOING_TO_CENTER.")
                        self.current_state = "GOING_TO_CENTER_OR_MENHIR"
                        self.map_strategy = "NO_TREES_CENTER" # Zmień strategię, aby uniknąć pętli
                        self.target_coord = self.center_coord # Ustaw cel na centrum
                        self.actions_history.append(True); return Action.TURN_RIGHT # Zacznij od nowa

            if self.path:
                next_step_coord = self.path[0]
                action = self._get_move_action_to_target(my_pos, my_facing, next_step_coord)
                if action == Action.STEP_FORWARD:
                    if self._is_tile_safe(next_step_coord, knowledge, player_danger_zones, occupied_by_players, current_mist_coords):
                        self.path.pop(0)
                        self.bot_moved_or_turned_this_turn = True
                        self.actions_history.append(True)
                        return Action.STEP_FORWARD
                    else:
                        self.path = []
                        self.target_coord = None
                else: # Obrót
                    self.bot_moved_or_turned_this_turn = True
                    self.actions_history.append(True)
                    return action
            
            self.bot_moved_or_turned_this_turn = True
            self.actions_history.append(True)
            return Action.TURN_RIGHT # Domyślna eksploracja


        # --- IN_TREE_IDLE ---
        elif self.current_state == "IN_TREE_IDLE":
            current_tile_desc = self.known_map_tiles.get(my_pos)
            if not current_tile_desc or current_tile_desc.type != "forest":
                self.current_state = "SEARCHING_FOR_TREE"
                self.target_coord = None
                # Kontynuuj decyzję w tej samej turze
            
            if self.current_state == "IN_TREE_IDLE": # Sprawdź ponownie, czy stan się nie zmienił
                self.spin_idx = (self.spin_idx + 1) % len(self.spin_actions_in_bush)
                action = self.spin_actions_in_bush[self.spin_idx]
                self.bot_moved_or_turned_this_turn = action != Action.DO_NOTHING
                self.actions_history.append(self.bot_moved_or_turned_this_turn)
                return action

        # --- IDLE_AT_TARGET (np. w centrum) ---
        elif self.current_state == "IDLE_AT_TARGET":
            # Po prostu kręć się lub czekaj, obserwując otoczenie
            # Podobne do IN_TREE_IDLE, ale bez wymogu bycia w drzewie
            self.spin_idx = (self.spin_idx + 1) % len(self.spin_actions_in_bush)
            action = self.spin_actions_in_bush[self.spin_idx] # Użyj tego samego wzoru kręcenia się
            self.bot_moved_or_turned_this_turn = action != Action.DO_NOTHING
            self.actions_history.append(self.bot_moved_or_turned_this_turn)
            return action


        # --- FLEEING_MIST ---
        if self.current_state == "FLEEING_MIST": # Logika ucieczki powinna być tu
            self.flee_attempts_in_a_row += 1

            # Jeśli mamy ścieżkę ucieczki i jest ona wciąż ważna
            if self.path and self._is_tile_safe(self.path[0], knowledge, player_danger_zones, occupied_by_players, current_mist_coords, True, True):
                next_step_coord = self.path[0]
                action = self._get_move_action_to_target(my_pos, my_facing, next_step_coord)
                if action == Action.STEP_FORWARD:
                    self.path.pop(0)
                    self.flee_attempts_in_a_row = 0
                self.bot_moved_or_turned_this_turn = True
                self.actions_history.append(True)
                return action
            else: # Nie ma ścieżki lub jest nieaktualna, znajdź nowy cel ucieczki i ścieżkę
                self.path = []
                flee_destination = self._get_flee_destination(my_pos, current_mist_coords, knowledge, player_danger_zones, occupied_by_players)
                if flee_destination:
                    self.path = self._bfs_path(my_pos, flee_destination, knowledge, player_danger_zones, occupied_by_players, current_mist_coords, True, True)
                    if self.path: # Znaleziono nową ścieżkę ucieczki
                        next_step_coord = self.path[0]
                        action = self._get_move_action_to_target(my_pos, my_facing, next_step_coord)
                        if action == Action.STEP_FORWARD:
                            self.path.pop(0)
                            self.flee_attempts_in_a_row = 0
                        self.bot_moved_or_turned_this_turn = True
                        self.actions_history.append(True)
                        return action
            
            # Jeśli nie udało się znaleźć ścieżki ucieczki ani wykonać kroku, obróć się
            # To jest moment, gdzie logika "omijania przeszkód" powinna zadziałać dzięki BFS
            # Jeśli BFS nie znajduje drogi, to znaczy, że jesteśmy zablokowani
            # W takim przypadku, próbujemy się obrócić
            if self.flee_attempts_in_a_row > 2 : # Jeśli utknęliśmy na kilka tur
                 action_to_take = Action.TURN_LEFT if random.random() < 0.5 else Action.TURN_RIGHT
            else:
                 action_to_take = Action.TURN_RIGHT

            self.bot_moved_or_turned_this_turn = True
            self.actions_history.append(True)
            return action_to_take

        # Domyślna akcja, jeśli żaden stan nie został obsłużony
        if not self.bot_moved_or_turned_this_turn: # Jeśli nic się nie stało
            self.actions_history.append(False) # Zapisz DO_NOTHING lub nieudany ruch

        return Action.DO_NOTHING


    @property
    def name(self) -> str:
        return self.first_name # Zgodnie z dostarczonym plikiem

    @property
    def preferred_tabard(self) -> characters.Tabard:
        #return characters.Tabard.KIMDZONGNEAT
        return characters.Tabard.RED
import heapq
from importlib.util import set_loader
import math
from re import S
import traceback
import random
from turtle import back
from typing import Dict
from gupb import controller
from gupb.model import arenas, effects, tiles
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import weapons
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Axe, Bow, Sword, Amulet

"""
TODO: inteligentniejsze atakowanie, jesli ma mniej zycia niz przeciwnik to powinien uciekac
TODO: sprawdza przeciwnikow w szerszym obszarze i jesli widzi jakeigo w poblizu to ucieka w zaleznosci od zycia
TODO: uciekanie przed mgłą
"""

"""
OPCJA MILENKI
"""


POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
    characters.Action.STEP_BACKWARD,
    characters.Action.STEP_LEFT,
    characters.Action.STEP_RIGHT,
]

FACING_VALUES = [
    characters.Facing.LEFT,
    characters.Facing.RIGHT,
    characters.Facing.UP,
    characters.Facing.DOWN,
]

TerrainDescription = Dict[Coords, tiles.TileDescription]

class CynamonkaController(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.arena = None
        self.current_weapon = Knife
        self.weapons_positions = {}
        self.elixir_positions = {}
        self.mist_positions = {}
        self.position = None
        self.next_forward_position = None # position of player if it goes forward
        self.facing = None
        self.menhir_position = None
        self.is_mist = False
        self.discovered_arena: TerrainDescription = {}
        self.move_count = 0
        self.target = None
        self.walkable_area = set()
        self.runaway_target = None
        self.times_in_row_amulet = 0

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CynamonkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.move_count+=1
            self.update_discovered_arena(knowledge.visible_tiles)
            self.update_walkable_area()
            self.position = knowledge.position
            #print(f"walkable area: {self.walkable_area}")
            #print(f"position: {self.position}")
            self.facing = knowledge.visible_tiles[self.position].character.facing
            self.next_forward_position = self.position + self.facing.value
            self.set_new_weapon()
            # print("Round: " + str(self.move_count))
            # first three ifs are the most important actions, player do it even when the map shrinks
            #if see elixir take it 

            if self.can_collect_elixir(self.next_forward_position) and not self.is_mist_at_position(self.next_forward_position):
                self.times_in_row_amulet = 0
                return POSSIBLE_ACTIONS[2] # go forward
            # if can attack
            if self.should_run_away():
                return self.run_away_from_enemies()
            elif self.can_attack():
                # print("inside can attack")
                return POSSIBLE_ACTIONS[3] # attack
            #if can take a weapon
            if self.can_collect_weapon(self.next_forward_position) and not self.is_mist_at_position(self.next_forward_position):  
                self.times_in_row_amulet = 0
                return POSSIBLE_ACTIONS[2] # go forward
            
            #if there is mist, player acts differently - main goal is to run
            if self.is_mist:
                # if we see menhir we know where to run
                if self.menhir_position:
                    self.times_in_row_amulet = 0
                    return self.go_in_menhir_direction()
                # player can see mist but do not see menhir, it must runaway from mist
                else:
                    # here should be runaway from mist function
                    self.times_in_row_amulet = 0
                    #return self.go_to_center()
                    return self.runaway_from_mist()
            # player do not see mist so it is not its priority to run away
            else:
                # TODO: mozna tez zaimplementowac algorytm zeby szedl w kierunku wroga jesli wrog ma mniej zycia i jest blisko
                if self.is_elixir_in_the_neighbourhood():
                    self.times_in_row_amulet = 0
                    return self.go_in_the_target_direction(self.target)
                if self.is_weapon_in_the_neighbourhood() and self.current_weapon == Knife: 
                    self.times_in_row_amulet = 0
                    return self.go_in_the_target_direction(self.target)
                if self.menhir_position:
                    self.times_in_row_amulet = 0
                    return self.go_in_menhir_direction()
                else:
                    self.times_in_row_amulet = 0
                    return self.go_randomly()
        except Exception as e:
            # Handle exceptions or errors here
            #traceback.print_exc()
            #print(f"An error occurred: {e}")
            return self.go_randomly()

    # returns path if weapon or elixir in the neighbourhood, if its far away return None
    def is_weapon_in_the_neighbourhood(self):
        paths =[]
        if self.weapons_positions:
            for coords in self.weapons_positions.keys():
                path = self.find_nearest_path(self.walkable_area, self.position, coords)
                paths.append(path)
        shortest_path = CynamonkaController.find_shortest_path_from_list(paths)
        if shortest_path:
            if len(shortest_path) <= 7 and (self.discovered_arena[shortest_path[-1]].consumable or self.discovered_arena[shortest_path[-1]].loot):
                self.target = shortest_path[-1]
                return True
        return False
    
    def is_elixir_in_the_neighbourhood(self):
        paths = []
        if self.elixir_positions:
            for coords in self.elixir_positions.keys():
                paths.append(self.find_nearest_path(self.walkable_area, self.position, coords))
        shortest_path = CynamonkaController.find_shortest_path_from_list(paths)
        if shortest_path:
            if len(shortest_path) <= 7 and (self.discovered_arena[shortest_path[-1]].consumable or self.discovered_arena[shortest_path[-1]].loot):
                self.target = shortest_path[-1]
                return True
        return False

    def update_walkable_area(self):
        for coords in self.discovered_arena.keys():
            if self.is_walkable(coords):
                if isinstance(coords, Coords):
                    coords = (coords[0], coords[1])
                self.walkable_area.add(coords)
    
    @staticmethod
    def find_shortest_path_from_list(paths):
        not_empty_paths = [path for path in paths if path is not None]  # Fixed the list comprehension
        if not not_empty_paths:
            return None  # Return None if the list is empty
        shortest_path = min(not_empty_paths, key=len)
        return shortest_path

    def go_in_the_target_direction(self, target_point):
        # Znajdź optymalną trasę do celu
        nearest_path_to_target = self.find_nearest_path(self.walkable_area, self.position, target_point)
        
        if nearest_path_to_target is not None:
            # print("ide do celu")
            # Pobierz kierunek, w którym znajduje się kolejna pozycja na trasie
            next_position_direction = self.calculate_direction(self.position, nearest_path_to_target[0])
            # Sprawdź, czy jesteśmy zwróceni w tym samym kierunku co kolejna pozycja
            if self.facing.value == next_position_direction:
            # Jeśli tak, idź prosto
                return POSSIBLE_ACTIONS[2]  # Step forward
            else:
                # Sprawdź, czy musimy obrócić się o 180 stopni
                if self.is_opposite_direction(self.facing.value, next_position_direction):
                    return POSSIBLE_ACTIONS[4]  # Step backward
                else:
                    # W przeciwnym razie, obróć się w kierunku kolejnej pozycji na trasie
                    if self.is_position_on_left(nearest_path_to_target[0]):
                        return POSSIBLE_ACTIONS[5]  # Turn left
                    else:
                        return POSSIBLE_ACTIONS[6]  # Turn right
        # Jeśli nie udało się znaleźć trasy, wykonaj losowy ruch
        return self.go_randomly()

    def calculate_direction(self, from_position, to_position):
        # Oblicz kierunek między dwiema pozycjami
        direction = coordinates.Coords(to_position[0] - from_position[0], to_position[1] - from_position[1])
        return direction

    def is_position_on_left(self, target_position):
        # Sprawdź, czy target_position jest po "lewej" stronie od aktualnej pozycji
        if self.facing.value == (1, 0):
            return target_position[1] < self.position[1]  # Patrzymy w prawo, więc lewo to niższe wartości Y
        elif self.facing.value == (-1, 0):
            return target_position[1] > self.position[1]  # Patrzymy w lewo, więc lewo to wyższe wartości Y
        elif self.facing.value == (0, 1):
            return target_position[0] > self.position[0]  # Patrzymy w górę, więc lewo to większe wartości X
        elif self.facing.value == (0, -1):
            return target_position[0] < self.position[0]  # Patrzymy w dół, więc lewo to niższe wartości X
        else:
            return False  # Nieznany kierunek

    def is_position_on_right(self, target_position):
        # Sprawdź, czy target_position jest po "prawej" stronie od aktualnej pozycji
        return not self.is_position_on_left(target_position)
        
    def is_opposite_direction(self, direction1, direction2):
        # Sprawdź, czy dwie koordynaty są przeciwne sobie
        return  direction1[0] == -direction2[0] and direction1[1] == -direction2[1]

    def turn_towards_direction(self, target_direction):
        # Obróć się w kierunku podanego kierunku
        if self.facing == characters.Facing.UP:
            if target_direction == characters.Facing.LEFT.value:
                return POSSIBLE_ACTIONS[0]  # Skręć w lewo
            else:
                return POSSIBLE_ACTIONS[1]  # Skręć w prawo
        elif self.facing == characters.Facing.DOWN:
            if target_direction == characters.Facing.LEFT.value:
                return POSSIBLE_ACTIONS[1]  # Skręć w prawo                
            else:
                return POSSIBLE_ACTIONS[0]  # Skręć w lewo
        elif self.facing == characters.Facing.LEFT:
            if target_direction == characters.Facing.UP.value:
                return POSSIBLE_ACTIONS[1]  # Skręć w prawo
            else:
                return POSSIBLE_ACTIONS[0]  # Skręć w lewo
        elif self.facing == characters.Facing.RIGHT:
            if target_direction == characters.Facing.UP.value:
                return POSSIBLE_ACTIONS[0]  # Skręć w lewo
            else:
                return POSSIBLE_ACTIONS[1]  # Skręć w prawo
        else:
            return self.go_randomly()

    def go_in_menhir_direction(self):
        path_from_menhir = self.find_nearest_path(self.walkable_area, self.next_forward_position, self.menhir_position)
        if path_from_menhir:
            distance_from_menhir = len(path_from_menhir)
            if distance_from_menhir > 2:
                return self.go_in_the_target_direction(self.menhir_position)            
            else: 
                return self.go_randomly()
        else: 
            return self.go_randomly()

    def go_randomly(self):
        if self.can_move_forward():
            return random.choices(POSSIBLE_ACTIONS[:3], [1,1,8], k=1)[0]
        elif self.can_turn_right() and self.can_turn_left():
            return random.choice(POSSIBLE_ACTIONS[5:])
        elif self.can_turn_left():
            return POSSIBLE_ACTIONS[5]
        elif self.can_turn_right():
            return POSSIBLE_ACTIONS[6]
        else:
            return random.choice(POSSIBLE_ACTIONS[:2])
        
    # astar funkcja do znalezienia trasy
    def find_nearest_path(self, grid, start, goal):
        # Inicjalizuj listę odwiedzonych pozycji
        if goal is None:
            return None
        visited_positions = set()

        # Inicjalizuj kolejkę priorytetową do przechowywania pozycji i ich kosztów
        priority_queue = [(0, start, [])]  # (koszt, pozycja, ścieżka)

        while priority_queue:
            cost, current_position, path = heapq.heappop(priority_queue)

            if current_position == goal:
                return path  # Znaleziono cel, zwróć ścieżkę

            if current_position in visited_positions:
                continue  # Ta pozycja została już odwiedzona

            visited_positions.add(current_position)

            # Oblicz dostępne pozycje i ich koszty
            for dx, dy in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
                new_position = (current_position[0] + dx, current_position[1] + dy)
                if new_position in grid:
                    new_cost = len(path) + 1 + math.dist(new_position, goal)
                    heapq.heappush(priority_queue, (new_cost, new_position, path + [new_position]))
        return None  # Nie znaleziono ścieżki do celu
    
    def set_new_weapon(self):
        new_weapon = self.discovered_arena[self.position].character.weapon.name
        match new_weapon:
                case 'knife':
                    self.current_weapon = Knife
                case 'sword':
                    self.current_weapon = Sword
                case 'bow_loaded':
                    self.current_weapon = Bow
                case 'bow_unloaded':
                    self.current_weapon = Bow
                case 'axe':
                    self.current_weapon = Axe
                case 'amulet':
                    self.current_weapon = Amulet
                case _:
                    raise ValueError(f'No Weapon named  {new_weapon} found')


    def runaway_from_mist(self):
        # Jeśli brak obszarów mgły, zwróć losową akcję
        if not self.mist_positions:
            return self.go_randomly()

        farthest_distance = 0
        farthest_position = None

        for coords in self.discovered_arena.items():
                # Oblicz odległość między bieżącym położeniem bota a położeniem przeciwnika
                distance = math.dist(self.position, coords)

                if distance > farthest_distance:
                    farthest_distance = distance
                    temp_farthest_position = coords
                    if  self.find_nearest_path(self.walkable_area, self.position, temp_farthest_position) and temp_farthest_position not in self.mist_positions:
                        farthest_position = coords

        if farthest_position is not None: # and self.find_nearest_path(self.walkable_area, self.position, farthest_position) and farthest_position not in self.mist_positions:
            # Znaleziono pozycję, więc uciekaj w jej kierunku
            # direction = coordinates.Coords(farthest_position[0] - self.position[0], farthest_position[1] - self.position[1])
            #print('uciekam przed mggla: ' + str(farthest_position))

            return self.go_in_the_target_direction(farthest_position)

        # Brak dostępnych pól, które nie są w obszarze mgły, zwróć losową akcję
        return self.go_randomly()

    def get_attackable_area(self):
        attackable_area = []
        if self.current_weapon == Knife:
            attackable_area = Knife.cut_positions(self.arena.terrain, self.position, self.facing)
        elif self.current_weapon == Axe:
            attackable_area = Axe.cut_positions(self.arena.terrain, self.position, self.facing)
        elif self.current_weapon == Amulet:
            attackable_area = Amulet.cut_positions(self.arena.terrain, self.position, self.facing)
        elif self.current_weapon == Bow: # and self.current_weapon.__name__ == "bow_loaded":
            attackable_area = weapons.Bow.cut_positions(self.arena.terrain, self.position, self.facing)
        elif self.current_weapon == Sword:
            attackable_area = Sword.cut_positions(self.arena.terrain, self.position, self.facing)
        return attackable_area
    
    def can_attack(self):
        if self.current_weapon == weapons.Bow and self.current_weapon.__name__ == "bow_unloaded":
            self.times_in_row_amulet = 0
            return True
        attackable_area = self.get_attackable_area()
        if self.current_weapon == weapons.Amulet and self.times_in_row_amulet > 5:
                self.times_in_row_amulet = 0
                return False
        for coords, description in self.discovered_arena.items():
            
            if description.character and description.character.controller_name != "CynamonkaController" and coords in attackable_area:
                if self.current_weapon == weapons.Amulet:
                    self.times_in_row_amulet+=1
                else:
                    self.times_in_row_amulet=0
                return True
        return False

    def run_away_from_enemies(self):
        # print("jestem w runaway enemies")
        escape_range = 4  # Zakres, w którym bot sprawdzi obecność przeciwników
        escape_area = self.get_escape_area(escape_range)

        for coords, description in self.discovered_arena.items():
            if description.character and description.character.controller_name != "CynamonkaController" and coords in escape_area:
                # print("zdrowie przeciwnika: " + str(description.character.health) + " moje zdrowie : " + str(self.discovered_arena[self.position].character.health))
                if description.character.health > self.discovered_arena[self.position].character.health:
                    enemy_direction = description.character.facing.value
                    # Uciekaj od przeciwnika
                    escape_position = coordinates.Coords(self.position[0] + enemy_direction[0], self.position[1] + enemy_direction[1])
                    if escape_position in self.walkable_area:
                        # print("zwracam uciekanie do : " + str(escape_position))
                        return self.go_in_the_target_direction(escape_position)
        return None

    # def run_away_from_enemies(self):
    #     # print("uciekam")
    #     # Zakres, w którym bot sprawdzi obecność przeciwników
    #     escape_range = 4
    #     escape_area = self.get_escape_area(escape_range)

    #     farthest_distance = 0
    #     farthest_position = None

    #     for coords, description in self.discovered_arena.items():
    #         if description.character and description.character.controller_name != "CynamonkaController" and coords in escape_area:
    #             if description.character.health > self.discovered_arena[self.position].character.health:

    #                 # Oblicz odległość między botem a przeciwnikiem
    #                 distance = math.dist(self.position, coords)
    #                 print(str(distance))

    #                 if distance > farthest_distance:
    #                     farthest_distance = distance
    #                     temp_farthest_position = coords
    #                     print("temp przeciwnik"+str(temp_farthest_position))
    #                     if  self.find_nearest_path(self.walkable_area, self.position, temp_farthest_position):
    #                         farthest_position = coords

    #     if farthest_position is not None:
    #         print('uciekam przed przeciwnikiem'+ str(farthest_position))
    #         return self.go_in_the_target_direction(farthest_position)

    #     return None
    def closest_point(self, points_set, target):
        closest = None
        min_distance = float('inf')

        for point in points_set:
            distance =  abs(target[0] - point[0]) + abs(target[1] - point[1])
            if distance < min_distance:
                min_distance = distance
                closest = point

        return closest

    def go_to_center(self):
        map_center = (12, 12)  # Center position on a 25x25 map
        direction = (map_center[0] - self.position[0], map_center[1] - self.position[1])
        #print(f"self position: {self.position}")
        if direction == (0, 0):
            return self.go_randomly()
        if map_center in self.walkable_area:
            #print("map center in walkable aren")
            if self.find_nearest_path(self.walkable_area, self.position, map_center):
                #print("go in the target direction")
                return self.go_in_the_target_direction(map_center)
        # else:
        #     almost_map_center = self.closest_point(self.walkable_area, map_center)
        #     #print(f"almost map center in disc area: {almost_map_center}")
        #     if self.find_nearest_path(self.walkable_area, self.position, almost_map_center):
        #         #print("go in the target direction")
        #         return self.go_in_the_target_direction(almost_map_center)
        #print("go randomlys")
        #return self.go_randomly()
        if abs(direction[0]) > abs(direction[1]):
            if direction[0] > 0:
                target_position = (self.position[0] + 1, self.position[1])
                if self.is_walkable(target_position):
                    if self.facing == FACING_VALUES[1]:
                        return POSSIBLE_ACTIONS[2]  
                    elif self.facing == FACING_VALUES[0]:
                        return POSSIBLE_ACTIONS[4]  
                    elif self.facing == FACING_VALUES[2]:
                        return POSSIBLE_ACTIONS[6]
                    else:
                        return POSSIBLE_ACTIONS[5]
            else:
                target_position = (self.position[0] - 1, self.position[1])
                if self.is_walkable(target_position):
                    if self.facing == FACING_VALUES[0]:
                        return POSSIBLE_ACTIONS[2]
                    elif self.facing == FACING_VALUES[1]:
                        return POSSIBLE_ACTIONS[4]  
                    elif self.facing == FACING_VALUES[2]:
                        return POSSIBLE_ACTIONS[5]
                    else:
                        return POSSIBLE_ACTIONS[6]
                    
        if direction[1] > 0:
            target_position = (self.position[0], self.position[1] + 1)
            if self.is_walkable(target_position):
                if self.facing == FACING_VALUES[3]:
                    return POSSIBLE_ACTIONS[2]
                elif self.facing == FACING_VALUES[2]:
                    return POSSIBLE_ACTIONS[4]  
                elif self.facing == FACING_VALUES[0]:
                    return POSSIBLE_ACTIONS[5]
                else:
                    return POSSIBLE_ACTIONS[6]
        else:
            target_position = (self.position[0], self.position[1] - 1)
            if self.is_walkable(target_position):
                if self.facing == FACING_VALUES[2]:
                    return POSSIBLE_ACTIONS[2]
                elif self.facing == FACING_VALUES[1]:
                    return POSSIBLE_ACTIONS[5]  
                elif self.facing == FACING_VALUES[0]:
                    return POSSIBLE_ACTIONS[6]
                else:
                    return POSSIBLE_ACTIONS[4]
                
        return self.go_randomly()



    def get_escape_area(self, escape_range):
        return {(self.position[0] + dx, self.position[1] + dy) for dx in range(-escape_range, escape_range + 1) for dy in range(-escape_range, escape_range + 1) if (self.position[0] 
        + dx, self.position[1] + dy) in self.discovered_arena}

        #return escape_area

    def should_run_away(self):
        escape_action = self.run_away_from_enemies()
        return escape_action is not None


    def can_turn_right(self):
        right_position = self.position + self.facing.turn_right().value
        return self.is_walkable(right_position)
    
    def can_turn_left(self):
        left_position =  self.position + self.facing.turn_left().value
        return self.is_walkable(left_position)

    # check if it is possible to go to given position, if there is a sea wall or mist the champion cannot go there
    def is_walkable(self, position):
        #if position in self.walkable_area:
        if position in self.discovered_arena.keys():
            return self.discovered_arena[position].type != 'sea' and self.discovered_arena[position].type != 'wall' and not self.is_mist_at_position(position)
        return False
    
    def can_move_forward(self):
        return self.is_walkable(self.next_forward_position)

    def can_move_backward(self):
        # Pobierz kierunek, w którym chcemy się poruszyć do tyłu
        backward_position = self.position + self.facing.opposite().value
        return self.is_walkable(backward_position)
            
    def update_discovered_arena(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for coords, description in visible_tiles.items():
            if isinstance(coords, Coords):
                coords = (coords[0], coords[1])
            self.discovered_arena[coords] = description
            if self.elixir_positions and coords in self.elixir_positions.keys() and not description.consumable:
                del self.elixir_positions[coords]
            if description.consumable:
                self.elixir_positions[coords] = description
            if self.weapons_positions and coords in self.weapons_positions.keys() and not description.loot:
                del self.weapons_positions[coords]
            if description.loot:
                self.weapons_positions[coords] = description
            if not self.is_mist and self.mist_positions:
                self.is_mist = True
            if not self.menhir_position and self.is_menhir(coords):
                self.menhir_position = coords
            if effects.EffectDescription(type='mist') in description.effects:
                self.mist_positions[coords] = description
            

    def is_menhir(self, coords):
        return self.discovered_arena[coords].type == 'menhir'
    
    def can_collect_weapon(self, new_position):
        # TODO: Taki totalnie opcjonalny punkt, mysle ze nie ejst istiotny narazie: maybe do some more complex hierarchy of weapon but idk which one, for now Knife is the worst, rest of them are equal
        if self.discovered_arena[new_position].loot and self.current_weapon == Knife:
            return True
        return False
    
    def can_collect_elixir(self, new_position):
        return self.discovered_arena[new_position].consumable

    def is_mist_in_visible_area(self):
        for tile in self.discovered_arena.values():
            if effects.EffectDescription(type='mist') in tile.effects:
                return True
        return False
    
    def is_mist_at_position(self, position):
        for effect in self.discovered_arena[position].effects:
                if effect.type == 'mist':
                    return True
        return False

    def praise(self, score: int) -> None:
        # TODO: ogarnąć o co z tym chodzi , tez raczej opcjonalne
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena = arenas.Arena.load(arena_description.name)
        self.current_weapon = Knife
        self.weapons_positions = {}
        self.elixir_positions = {}
        self.mist_positions = {}
        self.position = None
        self.next_forward_position = None
        self.facing = None
        self.discovered_arena: TerrainDescription = {}
        self.menhir_position = None
        self.move_count = 0
        self.target = None
        self.times_in_row_amulet = 0
        self.is_mist = False
        self.walkable_area = set()
        self.runaway_target = None

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK

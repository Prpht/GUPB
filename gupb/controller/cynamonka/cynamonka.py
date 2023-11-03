import heapq
import math
from re import S
import traceback
import random
from typing import Dict
from gupb import controller
from gupb.model import arenas, effects, tiles
from gupb.model import characters
from gupb.model import coordinates
from gupb.model import weapons
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Axe, Bow, Sword, Amulet
# TODO: nie idzie za bardzo w kierunku eliksiru
# TODO: ogarnac zeby moze atakowal jak ma troche wiecej zycia

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
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
            #print(f"ROUND NUMBER {self.move_count}")
            self.update_discovered_arena(knowledge.visible_tiles)
            self.update_walkable_area()
            self.position = knowledge.position
            self.facing = knowledge.visible_tiles[self.position].character.facing
            self.next_forward_position = self.position + self.facing.value
            self.set_new_weapon()

            # first three ifs are the most important actions, player do it even when the map shrinks
            #if see elixir take it 
            if self.can_collect_elixir(self.next_forward_position) and not self.is_mist_at_position(self.next_forward_position):
                # print("go forward and collect elixir")
                self.times_in_row_amulet = 0
                return POSSIBLE_ACTIONS[2] # go forward
            # if can attack
            if self.can_attack():
                # print("attack")
                return POSSIBLE_ACTIONS[3] # attack
            #if can take a weapon
            if self.can_collect_weapon(self.next_forward_position) and not self.is_mist_at_position(self.next_forward_position):  
                # print("go forward and collect weapon")
                self.times_in_row_amulet = 0
                return POSSIBLE_ACTIONS[2] # go forward
            
            #if there is mist, player acts differently - main goal is to run
            if self.is_mist:
                # print("Attention there is mist")
                # if we see menhir we know where to run
                if self.menhir_position:
                    # print("go in menhir direction")
                    self.times_in_row_amulet = 0
                    return self.go_in_menhir_direction()
                # player can see mist but do not see menhir, it must runaway from mist
                else:
                    # here should be runaway from mist function
                    # print("runaway from mist")
                    self.times_in_row_amulet = 0
                    return self.runaway_from_mist()
            # player do not see mist so it is not its priority to run away
            else:
                # print("there is no mist")

                # TODO: moze tez zaimplementowac algorytm zeby szedl w kierunku wroga jesli wrog ma mniej zycia i jest blisko
                if self.is_weapon_or_elixir_in_the_neighbourhood() and self.current_weapon == Knife: 
                    # print("go in weapon or elixir direction")
                    self.times_in_row_amulet = 0
                    return self.go_in_the_target_direction(self.target)
                if self.menhir_position:
                    # print("go in menhir direction 2")
                    self.times_in_row_amulet = 0
                    return self.go_in_menhir_direction()
                else:
                    # print("there is no mist, no weapon no menhir, go randomly")
                    self.times_in_row_amulet = 0
                    return self.go_randomly()
        except Exception as e:
            # Handle exceptions or errors here
            traceback.print_exc()
            print(f"An error occurred: {e}")


    # returns path if weapon or elixir in the neighbourhood, if its far away return None
    def is_weapon_or_elixir_in_the_neighbourhood(self):
        paths =[]
        if self.weapons_positions:
            for coords in self.weapons_positions.keys():
                path = self.find_nearest_path(self.walkable_area, self.position, coords)
                paths.append(path)
        if self.elixir_positions:
            for coords in self.elixir_positions.keys():
                paths.append(self.find_nearest_path(self.walkable_area, self.position, coords))
        shortest_path = CynamonkaController.find_shortest_path_from_list(paths)
        if shortest_path:
            if len(shortest_path) <= 7 and (self.discovered_arena[shortest_path[-1]].consumable or self.discovered_arena[shortest_path[-1]].loot):
                self.target = shortest_path[-1]
                # print("nowy target zostal ustawiony na ===== " + str(self.target) + str(self.discovered_arena[self.target]))
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
        # print("JESTEEEEM W SROKUUUUUU GO INTO THE TARGET FUNCTION")
        # print("moja pozycja  ==== " + str(self.position))
        # print("Target ===== " + str(target_point))
        # Znajdź optymalną trasę do celu
        nearest_path_to_target = self.find_nearest_path(self.walkable_area, self.position, target_point)
        # print("Path to target ==== " + str(nearest_path_to_target))

        
        if nearest_path_to_target is not None:
            # Pobierz kierunek, w którym znajduje się kolejna pozycja na trasie
            next_position_direction = self.calculate_direction(self.position, nearest_path_to_target[0])
            # print("next pos dir ======== " + str(next_position_direction))
            # print("and my direction ==== " + str(self.facing.value))

            # Sprawdź, czy jesteśmy zwróceni w tym samym kierunku co kolejna pozycja
            if self.facing.value == next_position_direction:
                # print("self facing value =" + str(self.facing.value))
                # Jeśli tak, idź prosto
                return POSSIBLE_ACTIONS[2]
            else:
                # W przeciwnym razie, sprawdź, czy musimy obrócić się o 180 stopni
                if self.is_opposite_direction(self.facing.value, next_position_direction):
                    return POSSIBLE_ACTIONS[1] #po prostu wtedy zawsze w prawo
                else:
                    # W przeciwnym razie, obróć się w kierunku kolejnej pozycji na trasie
                    return self.turn_towards_direction(next_position_direction)
        # Jeśli nie udało się znaleźć trasy, wykonaj losowy ruch
        return self.go_randomly()

    def calculate_direction(self, from_position, to_position):
        # Oblicz kierunek między dwiema pozycjami
        direction = coordinates.Coords(to_position[0] - from_position[0], to_position[1] - from_position[1])
        return direction

    
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
        # print("inside go randomly function")
        if self.can_move_forward():
            return random.choices(POSSIBLE_ACTIONS[:3], [1,1,8], k=1)[0]
        elif self.can_turn_right() and self.can_turn_left:
            return random.choice(POSSIBLE_ACTIONS[:2])
        elif self.can_turn_left():
            return POSSIBLE_ACTIONS[0]
        else: 
            return POSSIBLE_ACTIONS[1]
        # if self.can_move_forward():
        #     print("forward")
        #     return POSSIBLE_ACTIONS[2]
        # if self.can_turn_right() and self.can_turn_left:
        #     print("right")
        #     return random.choice(POSSIBLE_ACTIONS[:2])
        # elif self.can_turn_left():
        #     return POSSIBLE_ACTIONS[0]
        # else: 
        #     return POSSIBLE_ACTIONS[1]
    

    # def find_nearest_path(self, grid, start, goal):
    #     # Initialize a list to represent the path
    #     path = []
    #     current_position = start
    #     current_direction = self.facing.value 
    #     steps_taken = [0]
    #     visited_positions = set()  # Zbiór odwiedzonych pozycji

    #     print("start to find nearest path")
    #     while current_position != goal:
    #         # Calculate the positions for moving forward, turning right, and turning left
    #         forward_position = (current_position[0] + current_direction[0], current_position[1] + current_direction[1])
    #         right_position = (current_position[0] + current_direction[1], current_position[1] - current_direction[0])
    #         left_position = (current_position[0] - current_direction[1], current_position[1] + current_direction[0])

    #         valid_positions = [pos for pos in (forward_position, right_position, left_position) if pos in grid]

    #         if not valid_positions:
    #             return None

    #         # Calculate the weight for each position (distance + steps)
    #         weights = [abs(pos[0] - goal[0]) + abs(pos[1] - goal[1]) + steps_taken[-1] + (1 if pos == forward_position else 2) for pos in valid_positions for pos in valid_positions]
    #         # Choose the position that brings you closer to the goal
    #         closest_position = valid_positions[weights.index(min(weights))]

    #         if closest_position in visited_positions:
    #             print("przypadek zapetlenia, sciezka juz odwiedzona")
    #             return None

    #         # Update the path and current position
    #         path.append(coordinates.Coords(closest_position[0], closest_position[1]))
    #         visited_positions.add(closest_position) 
    #         current_position = closest_position
    #         steps_taken.append(steps_taken[-1] + (1 if closest_position == forward_position else 2))

    #         # Update the direction based on the movement
    #         if closest_position == forward_position:
    #             pass  # Keep the same direction (no need to change direction)
    #         elif closest_position == right_position:
    #             current_direction = (current_direction[1], -current_direction[0])  # Turn right
    #         elif closest_position == left_position:
    #             current_direction = (-current_direction[1], current_direction[0])  # Turn left
    #     print(f"end to find nearest path {path}")
    #     return path

    import heapq

    # astar funkcja do znalezienia trasy
    def find_nearest_path(self, grid, start, goal):
        # Inicjalizuj listę odwiedzonych pozycji
        # TODO: to dodalam
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
        # print("imie nowej broni ==== " + str(new_weapon))
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
        # główne załozenie: jesli zidentyfikuje mgle na mapie kieruje sie w strone najdalszego odkrytego do tej pory punktu, do ktorego istenieje sciezka

        # Jeśli brak obszarów mgły, zwróć losową akcję
        # print("jestem w srodku uciekania")
        if not self.mist_positions:
            # print("brak mgly")
            return self.go_randomly()
        
        if self.runaway_target is not None and self.runaway_target not in self.walkable_area:

            max_distance = 0
            best_position = None

            for position in self.discovered_arena:
                #print("sprawdzana pozycja = " + str(position))
                if position not in self.mist_positions and position in self.walkable_area:
                    # Oblicz odległość między polem a najbliższym obszarem mgły
                    min_distance = min(math.dist(position, mist) for mist in self.mist_positions)

                    if min_distance > max_distance:
                        max_distance = min_distance
                        best_position = position

            if best_position is not None and self.find_nearest_path(self.walkable_area, self.position, best_position):
                # Znaleziono najlepsze pole, więc uciekaj w jego kierunku
                direction = coordinates.Coords(best_position[0] - self.position[0], best_position[1] - self.position[1])
                #print("Uciekam przed mgla w kierunku : " + str(best_position))
                self.runaway_target = best_position
                return self.go_in_the_target_direction(self.runaway_target)
            else:
                # Brak dostępnych pól, które nie są w obszarze mgły, zwróć losową akcję
                #print("brak dostepnych pol")
                return self.go_randomly()
        else:
            return self.go_in_the_target_direction(self.runaway_target)

    # TODO: w poprzednich latach wiekszosc bierze pozycje broni w taki sposob ale w sumie to zaczynam miec watpliwosci czy tak mozna
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
        # else:
        #     print("Does not have a weapon")
        return attackable_area
    
    def can_attack(self):
        #TODO: naprawić case z amuletem, bo czasem zapętla atak
        #TODO: naprawić case z łukiem, bo czasem nie czyta go
        #print(f"num in rows ammulet: {self.times_in_row_amulet}")
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
                    #print("`you have amulet and you will attack")
                    self.times_in_row_amulet+=1
                else:
                    self.times_in_row_amulet=0
                #print(f"pole gracza ktore atakujemy: {description.character}")
                return True
        return False

    def can_turn_right(self):
        right_position = self.position + self.facing.turn_right().value
        return self.is_walkable(right_position)
    
    def can_turn_left(self):
        left_position =  self.position + self.facing.turn_left().value
        return self.is_walkable(left_position)

    # check if it is possible to go to given position, if there is a sea wall or mist the champion cannot go there
    def is_walkable(self, position):
        return self.discovered_arena[position].type != 'sea' and self.discovered_arena[position].type != 'wall' and not self.is_mist_at_position(position)

    def can_move_forward(self):
        return self.is_walkable(self.next_forward_position)
            
    def update_discovered_arena(self, visible_tiles: Dict[Coords, tiles.TileDescription]):
        for coords, description in visible_tiles.items():
            self.discovered_arena[coords] = description
            if coords in self.elixir_positions.keys() and not description.consumable:
                del self.elixir_positions[coords]
            if description.consumable:
                self.elixir_positions[coords] = description
            if self.weapons_positions and coords in self.weapons_positions.keys() and not description.loot:
                del self.weapons_positions[coords]
            if description.loot:
                self.weapons_positions[coords] = description
                #TODO: sprawdzic czy ta zmiana jest okej:
            if not self.is_mist and self.mist_positions:
                self.is_mist = True
            if not self.menhir_position and self.is_menhir(coords):
                # print("menhir")
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
        #print("RESET")
        self.arena = arenas.Arena.load(arena_description.name)
        self.current_weapon = Knife
        self.weapons_positions = {}
        self.elixir_positions = {}
        self.position = None
        self.next_forward_position = None
        self.facing = None
        self.discovered_arena: TerrainDescription = {}
        self.menhir_position = None
        self.move_count = 0
        self.target = None
        self.times_in_row_amulet = 0

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.PINK

    # TODO: Najlepiej byloby pusic symulacje i liczyc ile punktow/ ruchow zrobil nasz gracz, super gdyby udaloby ci sie dodac tych gracyz z 1 labu, ale to takie dodatkowe
    # wazne jest to zeby puscic tego bota z 1000 razy i zebrac jego srednia i tych randowmoych, jak bedziemy widziec ze jest duzo lepszy niz wiekszosc randomow to znaczy ze jest git
    # ja dodalam ogolnie z 12 tych randomow, im wiecej tym lepiej


    # TODO; On czasem tak muli i sie nie rusza, obczaic o co chodzi, generalnie pewnie to jest zwiazane z tym ze te funkcje pojscia do celu i menhira
    # sa slabe, takze jak sie zaimplementuje nowe nie powinno byc problemu
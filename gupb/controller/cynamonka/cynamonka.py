import traceback
import random
from typing import Dict

from gupb import controller

from gupb.model import arenas, effects, tiles
from gupb.model import characters
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Axe, Bow, Sword, Amulet

POSSIBLE_ACTIONS = [
    characters.Action.TURN_LEFT,
    characters.Action.TURN_RIGHT,
    characters.Action.STEP_FORWARD,
    characters.Action.ATTACK,
]


TerrainDescription = Dict[Coords, tiles.TileDescription]

class CynamonkaController(controller.Controller):
    def __init__(self, first_name: str, arena_description: arenas.ArenaDescription):
        self.first_name: str = first_name
        self.arena = arenas.Arena.load(arena_description.name)
        self.current_weapon = Knife
        self.weapons_positions = {}
        self.elixir_positions = {}
        self.position = None
        self.next_forward_position = None # position of player if it goes forward
        self.facing = None
        self.menhir_position = None
        self.is_mist = False
        self.discovered_arena: TerrainDescription = {}
        self.move_count = 0
        self.target = None
        self.walkable_area = set()

    def __eq__(self, other: object) -> bool:
        if isinstance(other, CynamonkaController):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        try:
            self.move_count+=1
            print(f"ROUND NUMBER {self.move_count}")
            self.update_discovered_arena(knowledge.visible_tiles)
            self.update_walkable_area()
            self.position = knowledge.position
            self.facing = knowledge.visible_tiles[self.position].character.facing
            self.next_forward_position = self.position + self.facing.value

            # first three ifs are the most important actions, player do it even when the map shrinks
            #if see elixir take it 
            if self.can_collect_elixir(self.next_forward_position) and not self.is_mist_at_position(self.next_forward_position):
                print("go forward and collect elixir")
                return POSSIBLE_ACTIONS[2] # go forward
            # if can attack
            # TODO: sprawdzic czy atakowanie na epwno dorbze dziala, w sensie ze atakuje faktycznie w te pozycje ktore powinien
            if self.can_attack():
                print("attack")
                return POSSIBLE_ACTIONS[3] # attack
            #if can take a weapon
            if self.can_collect_weapon(self.next_forward_position) and not self.is_mist_at_position(self.next_forward_position):  
                print("go forward and collect weapon")
                return POSSIBLE_ACTIONS[2] # go forward
            
            #if there is mist, player acts differently - main goal is to run
            if self.is_mist:
                print("Attention there is mist")
                # if we see menhir we know where to run
                if self.menhir_position:
                    print("go in menhir direction")
                    return self.go_in_menhir_direction()
                # player can see mist but do not see menhir, it must runaway from mist
                else:
                    # here should be runaway from mist function
                    print("runaway from mist")
                    return self.go_randomly()
                    #return self.runaway_from_mist()
            # player do not see mist so it is not its priority to run away
            else:
                print("there is no mist")

                # TODO: zaimplementowac algorytm zeby on nie szedl w kierunku broni jesli ma lepsza, czyli tylko jak ma noz to ma szukac
                # TODO: moze tez zaimplementowac algorytm zeby szedl w kierunku wroga jesli wrog ma mniej zycia i jest blisko
                if self.is_weapon_or_elixir_in_the_neighbourhood():
                    return self.go_in_the_target_direction()
                if self.menhir_position:
                    print("go in menhir direction 2")
                    return self.go_randomly()
                else:
                    print("there is no mist, no weapon no menhir, go randomly")
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
            if len(shortest_path) <= 7:
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

    
    def go_in_the_target_direction(self):
        # TODO: to jest implementacja tylko taka robocza, nie dziala to zbyt dobrze, trzeba napisac ja od nowa, najlepiej wgl nie patrz za bardzo na to co tu jest xd
        # jest funkcja find_nearest_path, ktora znajduje nam po kolei kroki ktore powinnismy wykonac zbey dojsc do jakiegos punktiu
        # trzeba ja wykorzystac jakos tak zeby gracz robil po kolei te kroki ktore powinien, trzeba pamietac ze funkcja find earest path zwraca
        # lsite pozycji uwzlędniając pozycje początkowa zawodnika i końcową,. Dodatkowo np jesli patrzymy wprzód to koszt przejscia z pola (1,1) na pole (1,2) jest mniejszy niz przejscia z pola (1,1) na pole (2,1)
        # bo trzeba sie obrocic i potem isc prosto, czyli to sie liczy jako dwa kroki, a nie jeden jak w pierwszym przypadku, narazie ten algorytm tego nie uwzglednia
        nearest_path_to_target_from_next_pos = self.find_nearest_path(self.walkable_area, self.next_forward_position, self.target)
        nearest_path_to_target = self.find_nearest_path(self.walkable_area, self.position, self.target)
        if nearest_path_to_target and nearest_path_to_target_from_next_pos is not None:
            if (len(nearest_path_to_target_from_next_pos) < len(nearest_path_to_target)) and self.can_move_forward():
                return POSSIBLE_ACTIONS[2]
        if self.position[0]< self.target[0] and self.can_turn_right():
            return POSSIBLE_ACTIONS[1]
        if self.position[0] > self.target[0] and self.can_turn_left():
            return POSSIBLE_ACTIONS[0]
        # plan jest taki ze jak nie moze skrecic w prawo i lewo (w sensie moze ale jest tam przeszkoda) to obraca sie w prawo bo wtedy bedzie tyleem, ryzyko zapetlenia
        return random.choices(POSSIBLE_ACTIONS[:3], [1,1,8], k=1)[0]
    
    def go_in_menhir_direction(self):
        # TODO: tak samo jak w przypadku funkcji go_in_the_target_direction, cale do zaimplementowania od nowa, tak naprawde to one beda takie same
        # mozna zrobic jedna funckje, jedyne co to w tym przyadku nie zlaezy nam jakos zeby dotrzec do samego menhira, wystarczy byc w poblizu, mozemy uznac 
        # ze jesli gracz jest <=2 od menhiru to juz do niego nie idzie

        nearest_path_to_target_from_next_pos = self.find_nearest_path(self.walkable_area, self.next_forward_position, self.menhir_position)
        nearest_path_to_target = self.find_nearest_path(self.walkable_area, self.position, self.menhir_position)
        if nearest_path_to_target and nearest_path_to_target_from_next_pos is not None:
            if (len(nearest_path_to_target_from_next_pos) < len(nearest_path_to_target)) and self.can_move_forward():
                return POSSIBLE_ACTIONS[2]
        if self.position[0] < self.menhir_position[0] and self.can_turn_right():
            return POSSIBLE_ACTIONS[1]
        if self.position[0] > self.menhir_position[0] and self.can_turn_left():
            return POSSIBLE_ACTIONS[0]
        # plan jest taki ze jak nie moze skrecic w prawo i lewo (w sensie moze ale jest tam przeszkoda) to obraca sie w prawo bo wtedy bedzie tyleem, ryzyko zapetlenia TODO: sprawdzic to
        return random.choices(POSSIBLE_ACTIONS[:3], [1,1,8], k=1)[0]
    
    def go_randomly(self):
        if self.can_move_forward():
            print("forward")
            return POSSIBLE_ACTIONS[2]
        if self.can_turn_right():
            print("right")
            return POSSIBLE_ACTIONS[1]
        if self.can_turn_left():
            print("left")
            return POSSIBLE_ACTIONS[0]
        print("randomly")
        return POSSIBLE_ACTIONS[1]
    

    def find_nearest_path(self, grid, start, goal):
        # TODO: tak jak pisalam wczesniej, trzeba dodac tutaj,a lbo w innej funkcji koszt przechodzenia z jednego pola na drugie
        # TODO: powinno być git, ale uwzględnić, ze aktualnie nie przypisuje sie nigdzie self. target, zadne wartosci, wiec wyrzuca blad, bo jest Nonem

        # wytłumaczenie w komentarzu w mniej wiecej 138 linijce
        # Initialize a list to represent the path
        path = [start]
        current_position = start
        current_direction = self.facing.value 
        steps_taken = [0]

        while current_position != goal:
            # Calculate the positions for moving forward, turning right, and turning left
            forward_position = (current_position[0] + current_direction[0], current_position[1] + current_direction[1])
            right_position = (current_position[0] + current_direction[1], current_position[1] - current_direction[0])
            left_position = (current_position[0] - current_direction[1], current_position[1] + current_direction[0])

            valid_positions = [pos for pos in (forward_position, right_position, left_position) if pos in grid]

            if not valid_positions:
                return None

            # Calculate the weight for each position (distance + steps)
            weights = [abs(pos[0] - goal[0]) + abs(pos[1] - goal[1]) + steps_taken[-1] + (1 if pos == forward_position else 2) for pos in valid_positions for pos in valid_positions]

            # Choose the position that brings you closer to the goal
            closest_position = valid_positions[weights.index(min(weights))]


            # Update the path and current position
            path.append(closest_position)
            current_position = closest_position

            steps_taken.append(steps_taken[-1] + (1 if closest_position == forward_position else 2))


            # Update the direction based on the movement
            if closest_position == forward_position:
                pass  # Keep the same direction (no need to change direction)
            elif closest_position == right_position:
                current_direction = (current_direction[1], -current_direction[0])  # Turn right
            elif closest_position == left_position:
                current_direction = (-current_direction[1], current_direction[0])  # Turn left

        return path

    def runaway_from_mist(self):
        #TODO: to sie bedzie troche roznic od go in the target direction bo w sumie bedzie dzialac odwrotnie, no i mgla jest na wielu polach
        pass

    # TODO: w poprzednich latach wiekszosc bierze pozycje broni w taki sposob ale w sumie to zaczynam miec watpliwosci czy tak mozna
    def get_attackable_area(self):
        attackable_area = []
        if self.current_weapon == Knife:
            attackable_area = Knife.cut_positions(self.arena.terrain, self.position, self.facing)
        elif self.current_weapon == Axe:
            attackable_area = Axe.cut_positions(self.arena.terrain, self.position, self.facing)
        elif self.current_weapon == Amulet:
            attackable_area = Amulet.cut_positions(self.arena.terrain, self.position, self.facing)
        elif self.current_weapon == Bow and self.current_weapon.__name__ == "bow_loaded":
            attackable_area = Bow.cut_positions(self.arena.terrain, self.position, self.facing)
        elif self.current_weapon == Sword:
            attackable_area = Sword.cut_positions(self.arena.terrain, self.position, self.facing)
        else:
            print("Does not have a weapon")
        return attackable_area
    
    def can_attack(self):
        if self.current_weapon.__name__ == "bow_unloaded":
            return True
        attackable_area = self.get_attackable_area()
        for coords, description in self.discovered_arena.items():
            if description.character and coords in attackable_area:
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
            if description.consumable:
                self.elixir_positions[coords] = description
            if description.loot:
                self.weapons_positions[coords] = description
            if not self.is_mist and self.is_mist_at_position(coords):
                self.is_mist = True
            if not self.menhir_position and self.is_menhir(coords):
                print("menhir")
                self.menhir_position = coords

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
        self.position = None
        self.next_forward_position = None
        self.facing = None
        self.discovered_arena: TerrainDescription = {}
        self.menhir_position = None
        self.move_count = 0
        self.target = None

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.YELLOW

    # TODO: Najlepiej byloby pusic symulacje i liczyc ile punktow/ ruchow zrobil nasz gracz, super gdyby udaloby ci sie dodac tych gracyz z 1 labu, ale to takie dodatkowe
    # wazne jest to zeby puscic tego bota z 1000 razy i zebrac jego srednia i tych randowmoych, jak bedziemy widziec ze jest duzo lepszy niz wiekszosc randomow to znaczy ze jest git
    # ja dodalam ogolnie z 12 tych randomow, im wiecej tym lepiej


    # TODO; On czasem tak muli i sie nie rusza, obczaic o co chodzi, generalnie pewnie to jest zwiazane z tym ze te funkcje pojscia do celu i menhira
    # sa slabe, takze jak sie zaimplementuje nowe nie powinno byc problemu

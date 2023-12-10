from gupb.controller.cynamonka.utils import POSSIBLE_ACTIONS
from gupb.controller.cynamonka.pathfinder import PathFinder
from gupb.model import characters, coordinates
import random
import math

class Actions:

    def __init__(self, knowledge, path_finder: PathFinder):
        self.my_knowledge = knowledge
        self.path_finder = path_finder

    def go_in_the_target_direction(self, target_point):
                # Znajdź optymalną trasę do celu
        nearest_path_to_target = PathFinder.find_nearest_path(self.my_knowledge.map.walkable_area, self.my_knowledge.position, target_point)
        
        if nearest_path_to_target is not None and len(nearest_path_to_target) > 0:
            # Pobierz kierunek, w którym znajduje się kolejna pozycja na trasie
            next_position_direction = PathFinder.calculate_direction(self.my_knowledge.position, nearest_path_to_target[0])

            # Sprawdź, czy jesteśmy zwróceni w tym samym kierunku co kolejna pozycja
            if self.my_knowledge.facing.value == next_position_direction:
                # Jeśli tak, idź prosto
                return POSSIBLE_ACTIONS[2]
            else:
                # W przeciwnym razie, sprawdź, czy musimy obrócić się o 180 stopni
                if PathFinder.is_opposite_direction(self.my_knowledge.facing.value, next_position_direction):
                    return POSSIBLE_ACTIONS[1] #po prostu wtedy zawsze w prawo
                else:
                    # W przeciwnym razie, obróć się w kierunku kolejnej pozycji na trasie
                    return self.turn_towards_direction(next_position_direction)
        # Jeśli nie udało się znaleźć trasy, wykonaj losowy ruch
        return self.go_randomly()
    
    def turn_towards_direction(self, target_direction):
        # Obróć się w kierunku podanego kierunku
        if self.my_knowledge.facing == characters.Facing.UP:
            if target_direction == characters.Facing.LEFT.value:
                return POSSIBLE_ACTIONS[0]  # Skręć w lewo
            else:
                return POSSIBLE_ACTIONS[1]  # Skręć w prawo
        elif self.my_knowledge.facing == characters.Facing.DOWN:
            if target_direction == characters.Facing.LEFT.value:
                return POSSIBLE_ACTIONS[1]  # Skręć w prawo                
            else:
                return POSSIBLE_ACTIONS[0]  # Skręć w lewo
        elif self.my_knowledge.facing == characters.Facing.LEFT:
            if target_direction == characters.Facing.UP.value:
                return POSSIBLE_ACTIONS[1]  # Skręć w prawo
            else:
                return POSSIBLE_ACTIONS[0]  # Skręć w lewo
        elif self.my_knowledge.facing == characters.Facing.RIGHT:
            if target_direction == characters.Facing.UP.value:
                return POSSIBLE_ACTIONS[0]  # Skręć w lewo
            else:
                return POSSIBLE_ACTIONS[1]  # Skręć w prawo
        else:
            return self.go_randomly()
        
    def go_randomly(self):
        #print("go randomly")
        if self.my_knowledge.can_move_forward():
            return random.choices(POSSIBLE_ACTIONS[:3], [1,1,8], k=1)[0]
        elif self.my_knowledge.can_turn_right() and self.my_knowledge.can_turn_left():
            return random.choice(POSSIBLE_ACTIONS[5:])

        return random.choice(POSSIBLE_ACTIONS[:2])
        
    def go_in_menhir_direction(self, menhir_position):
        path_from_menhir = PathFinder.find_nearest_path(self.my_knowledge.map.walkable_area, self.my_knowledge.position, menhir_position)
        if path_from_menhir:
            distance_from_menhir = len(path_from_menhir)
            if distance_from_menhir > 3:
                return self.go_in_the_target_direction(menhir_position)            
        return self.go_randomly()

    
    def go_to_center_of_map(self):
        #print(f"go to center: {self.my_knowledge.map.center}")
        closest_point_to_center = PathFinder.find_the_closest_point_to_target(self.my_knowledge.map.walkable_area, self.my_knowledge.map.center)
        
        action, path_to_center = self.path_finder.calculate_next_move( closest_point_to_center)
        if path_to_center and action:
            if len(path_to_center) > 3:
                return action
        return self.go_randomly()
    
    def run_away_from_enemies(self):
        # print("jestem w runaway enemies")
        escape_range = 4  # Zakres, w którym bot sprawdzi obecność przeciwników
        escape_area = self.get_escape_area(escape_range)

        for coords, description in self.my_knowledge.map.terrain.items():
            if description.character and description.character.controller_name != "Cynamonka" and coords in escape_area:
                # print("zdrowie przeciwnika: " + str(description.character.health) + " moje zdrowie : " + str(self.discovered_arena[self.position].character.health))
                if description.character.health > self.my_knowledge.health:
                    enemy_direction = description.character.facing.value
                    # Uciekaj od przeciwnika
                    escape_position = coordinates.Coords(self.my_knowledge.position[0] + enemy_direction[0], self.my_knowledge.position[1] + enemy_direction[1])
                    if escape_position in self.my_knowledge.map.walkable_area:
                        # print("zwracam uciekanie do : " + str(escape_position))
                        return self.go_in_the_target_direction(escape_position)
        return None
    
    def get_escape_area(self, escape_range):
        return {(self.my_knowledge.position[0] + dx, self.my_knowledge.position[1] + dy) for dx in range(-escape_range, escape_range + 1) for dy in range(-escape_range, escape_range + 1) if (self.my_knowledge.position[0] 
        + dx, self.my_knowledge.position[1] + dy) in self.my_knowledge.map.terrain}


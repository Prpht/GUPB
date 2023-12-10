import os, random
from typing import Dict, NamedTuple, Optional, List
import traceback
from gupb.model import arenas, tiles, coordinates, weapons, games
from gupb.model import characters, consumables, effects
from gupb.model.characters import CHAMPION_STARTING_HP
from gupb.model.coordinates import Coords
from gupb.model.weapons import Knife, Axe, Bow, Sword, Amulet
from gupb.controller.cynamonka.pathfinder import PathFinder
from gupb.controller.cynamonka.utils import POSSIBLE_ACTIONS
from gupb.controller.cynamonka.actions import Actions

class Map:
    def __init__(self, name: str, terrain: arenas.Terrain) -> None:
        self.name = name
        self.terrain = terrain
        self.size = arenas.terrain_size(self.terrain)
        self.menhir_position = None
        self.center = coordinates.Coords(round(self.size[0] / 2), round(self.size[1] / 2))
        self.walkable_area = []
        self.is_mist = False
        self.mist_positions = []

    def update_discovered_arena(self, visible_tiles: Dict[Coords, tiles.Tile]):
        
        for coords, description in visible_tiles.items():
            if isinstance(coords, Coords):
                coords = (coords[0], coords[1])
            if not coords in self.terrain:
                self.terrain[coords] = tiles.Land()
            
            if  description.type != self.terrain[coords].__class__.__name__.lower():
                new_tile_type = None
                if description.type == 'land':
                    new_tile_type = tiles.Land
                elif description.type == 'wall':
                    new_tile_type = tiles.Wall
                elif description.type == 'sea':
                    new_tile_type = tiles.Sea
                elif description.type == 'menhir':
                    new_tile_type = tiles.Menhir
                    self.menhir_position = coords
                else:
                    new_tile_type = tiles.Land
            else:
                new_tile_type = tiles.Land

            self.terrain[coords] = new_tile_type()
            self.terrain[coords].loot = Map.weapon_converter(description.loot)
            self.terrain[coords].consumable = Map.poison_converter(description.consumable)
            self.terrain[coords].effects = self.effects_converter(description.effects, coords)
            self.terrain[coords].character = description.character
            

    def update_walkable_area(self):
        self.walkable_area = []
        for coords, tile in self.terrain.items():
            if tile.passable:
                if isinstance(coords, Coords):
                    coords = (coords[0], coords[1])
                self.walkable_area.append(coords)

    @staticmethod
    def load(name: str) -> 'Map':
        terrain = dict()
        arena_file_path = os.path.join('resources', 'arenas', f'{name}.gupb')
        with open(arena_file_path) as file:
            for y, line in enumerate(file.readlines()):
                for x, character in enumerate(line):
                    if character != '\n':
                        position = coordinates.Coords(x, y)
                        if character in arenas.TILE_ENCODING:
                            terrain[position] = arenas.TILE_ENCODING[character]()
                        elif character in arenas.WEAPON_ENCODING:
                            terrain[position] = tiles.Land()
                            terrain[position].loot = arenas.WEAPON_ENCODING[character]()
        return Map(name, terrain)
    
    @staticmethod
    def weapon_converter(weapon_description):
        match weapon_description:
                case 'knife':
                    return Knife
                case 'sword':
                    return Sword
                case 'bow_loaded':
                    return Bow
                case 'bow_unloaded':
                    return Bow
                case 'axe':
                    return Axe
                case 'amulet':
                    return Amulet
                case _:
                    return None
    @staticmethod
    def poison_converter(consumable_description):
        if consumable_description is None or not isinstance(consumable_description, consumables.ConsumableDescription):
            return None
        
        if consumable_description.name == 'potion':
            return consumables.Potion
        return None
    
    def effects_converter(self, effects_description, coords):
        converted_effects = []

        for effect in effects_description:
            if effect.type == 'mist':
                self.is_mist = True
                converted_effects.append(effects.Mist)
                self.mist_positions.append(coords)
        
        return converted_effects
    

    
    def find_dangerous_tiles(self):
        dangerous_tiles = {}

        for coords in self.terrain:
            
            enemy_description = self.terrain[coords].character
            
            if enemy_description is not None and enemy_description.controller_name != "Cynamonka":
                weapon = Map.weapon_converter(enemy_description.weapon)

                if weapon is None:
                    continue

                positions = weapon.cut_positions(self.terrain, coords, enemy_description.facing)

                for position in positions:
                    if position not in dangerous_tiles:
                        dangerous_tiles[position] = coords
        
        return dangerous_tiles
    


class MyKnowledge:
    def __init__(self):
        self.position = None
        self.facing = None
        self.number_of_alive_champions = 0
        self.map :Map = None
        self.health = 0
        self.current_weapon = Knife
        self.dangerous_tiles = None
        self.times_in_row_amulet = 0

    def update_my_knowledge(self, knowledge: characters.ChampionKnowledge):
        self.position = knowledge.position
        self.facing = knowledge.visible_tiles[self.position].character.facing
        self.number_of_alive_champions = knowledge.no_of_champions_alive
        self.health = knowledge.visible_tiles[self.position].character.health
        self.current_weapon = Map.weapon_converter(knowledge.visible_tiles[self.position].character.weapon.name)
        self.map.update_discovered_arena(knowledge.visible_tiles)
        self.map.update_walkable_area()
        self.dangerous_tiles = self.map.find_dangerous_tiles()

    def get_attackable_area(self):
        attackable_area = []
        if self.current_weapon == Knife:
            attackable_area = Knife.cut_positions(self.map.terrain, self.position, self.facing)
        elif self.current_weapon == Axe:
            attackable_area = Axe.cut_positions(self.map.terrain, self.position, self.facing)
        elif self.current_weapon == Amulet:
            attackable_area = Amulet.cut_positions(self.map.terrain, self.position, self.facing)
        elif self.current_weapon == Bow: # and self.current_weapon.__name__ == "bow_loaded":
            attackable_area = weapons.Bow.cut_positions(self.map.terrain, self.position, self.facing)
        elif self.current_weapon == Sword:
            attackable_area = Sword.cut_positions(self.map.terrain, self.position, self.facing)
        return attackable_area

    def is_enemeny_in_attackable_area(self):
        attackable_area = self.get_attackable_area()
        for coords in attackable_area:
            if self.map.terrain[coords].character is not None and self.map.terrain[coords].character.controller_name != "Cynamonka":
                return True
        return False
    
    def is_weak(self):
        return self.health < 0.5 * CHAMPION_STARTING_HP
    
    def find_path_to_weapon_in_the_neighbourhood(self):
        paths =[]
        for coords in self.map.terrain:
            if self.map.terrain[coords].loot:
                path = PathFinder.find_nearest_path(self.map.walkable_area, self.position, coords)
                paths.append(path)
        shortest_path = PathFinder.find_shortest_path_from_list(paths)
        if shortest_path:
            return shortest_path
        return None
        
    def find_path_to_poison_in_the_neighbourhood(self):
        paths =[]
        for coords in self.map.terrain:
            if self.map.terrain[coords].consumable:
                path = PathFinder.find_nearest_path(self.map.walkable_area, self.position, coords)
                paths.append(path)
        shortest_path = PathFinder.find_shortest_path_from_list(paths)
        if shortest_path:
            return shortest_path
        return None
    
    def can_turn_right(self):
        right_position = self.position + self.facing.turn_right().value
        return self.is_walkable(right_position)
    
    def can_turn_left(self):
        left_position =  self.position + self.facing.turn_left().value
        return self.is_walkable(left_position)

    # check if it is possible to go to given position, if there is a sea wall or mist the champion cannot go there
    def is_walkable(self, position):
        return self.map.terrain[position].terrain_passable() and not self.is_mist_at_position(position)

    def is_mist_at_position(self, position):
        if effects.Mist in self.map.terrain[position].effects:
            return True
        return False
    
    def can_move_forward(self):
        forward_position = self.position + self.facing.value
        return self.is_walkable(forward_position)
    
    def can_collect_elixir(self, new_position):
        return self.map.terrain[new_position].consumable and new_position not in self.dangerous_tiles
    
    def can_attack(self):
        if self.current_weapon == weapons.Bow and self.current_weapon.__name__ == "bow_unloaded":
            self.times_in_row_amulet = 0
            return True
        attackable_area = self.get_attackable_area()
        if self.current_weapon == weapons.Amulet and self.times_in_row_amulet > 5:
                self.times_in_row_amulet = 0
                return False
        for coords, description in self.map.terrain.items():
            if description.character and description.character.controller_name != "Cynamonka" and coords in attackable_area and self.health >= description.character.health:
                if self.current_weapon == weapons.Amulet:
                    self.times_in_row_amulet+=1
                else:
                    self.times_in_row_amulet=0
                return True
        return False

    def can_collect_weapon(self, new_position):
        # TODO: Taki totalnie opcjonalny punkt, mysle ze nie ejst istiotny narazie: maybe do some more complex hierarchy of weapon but idk which one, for now Knife is the worst, rest of them are equal
        if self.map.terrain[new_position].loot and self.current_weapon == Knife and new_position not in self.dangerous_tiles:
            return True
        return False
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.current_weapon = Knife
        self.position = None
        self.facing = None
        self.times_in_row_amulet = 0
        self.map = Map.load(arena_description.name)
        self.number_of_alive_champions = 0
        self.dangerous_tiles = None
        self.health = 0
    

class Decider:
    def __init__(self):
        self.my_knowledge = MyKnowledge()


    def find_the_best_action(self, knowledge: characters.ChampionKnowledge):
        try:
            self.my_knowledge.update_my_knowledge(knowledge)
            path_finder = PathFinder(self.my_knowledge)
            #path_finder.update_paths(self.my_knowledge.position)
            new_action = Actions(self.my_knowledge, path_finder)

            # firstly go to poison
            if self.my_knowledge.can_collect_elixir(self.my_knowledge.position + self.my_knowledge.facing.value) and not self.my_knowledge.is_mist_at_position(self.my_knowledge.position + self.my_knowledge.facing.value):
                #print("collecting elixir")
                return POSSIBLE_ACTIONS[2] # go forward
    
            if self.my_knowledge.can_collect_elixir(self.my_knowledge.position + self.my_knowledge.facing.turn_right().value) and not self.my_knowledge.is_mist_at_position(self.my_knowledge.position + self.my_knowledge.facing.turn_right().value):
                #print("collecting elixir")
                return POSSIBLE_ACTIONS[6]  # Right
            
            if self.my_knowledge.can_collect_elixir(self.my_knowledge.position + self.my_knowledge.facing.turn_left().value) \
                    and not self.my_knowledge.is_mist_at_position(self.my_knowledge.position + self.my_knowledge.facing.turn_left().value):
                #print("collecting elixir")
                return POSSIBLE_ACTIONS[5]  # Left

            # then attack
            # TODO: add escaping
            escape_action = new_action.run_away_from_enemies()
            if escape_action:
                return escape_action
            if self.my_knowledge.can_attack():
                # print("inside can attack")
                #print("attack")
                return POSSIBLE_ACTIONS[3] # attack
            
            # collect weapon
            if self.my_knowledge.can_collect_weapon(self.my_knowledge.position + self.my_knowledge.facing.value) and not self.my_knowledge.is_mist_at_position(self.my_knowledge.position + self.my_knowledge.facing.value):
                #print("collect weapon")
                return POSSIBLE_ACTIONS[2] # go forward
    
            if self.my_knowledge.can_collect_weapon(self.my_knowledge.position + self.my_knowledge.facing.turn_right().value) and not self.my_knowledge.is_mist_at_position(self.my_knowledge.position + self.my_knowledge.facing.turn_right().value):
                #print("collect weapon")
                return POSSIBLE_ACTIONS[6]  # Right
            
            if self.my_knowledge.can_collect_weapon(self.my_knowledge.position + self.my_knowledge.facing.turn_left().value) and not self.my_knowledge.is_mist_at_position(self.my_knowledge.position + self.my_knowledge.facing.turn_left().value):
                #print("collect weapon")
                return POSSIBLE_ACTIONS[5]  # Left
            
            # check if there is a mist
            if self.my_knowledge.map.is_mist:
                if self.my_knowledge.map.menhir_position:
                    self.my_knowledge.times_in_row_amulet = 0
                    #print("going in menhir direction")
                    return new_action.go_in_menhir_direction(self.my_knowledge.map.menhir_position)
                else:
                    # TODO: dodaj tu uciekanie przed mgla
                    return new_action.go_randomly()
            else:
                
                poison_path = self.my_knowledge.find_path_to_poison_in_the_neighbourhood()
                if poison_path and len(poison_path) < 7:
                    return new_action.go_in_the_target_direction(poison_path[-1])
                
                weapon_path = self.my_knowledge.find_path_to_weapon_in_the_neighbourhood()
                if weapon_path and len(weapon_path) < 7:
                    return new_action.go_in_the_target_direction(weapon_path[-1])
                
                if self.my_knowledge.map.menhir_position:
                    return new_action.go_in_menhir_direction(self.my_knowledge.map.menhir_position)
                
                return new_action.go_randomly()
        except Exception as e:
            # Handle exceptions or errors here
            traceback.print_exc()
            print(f"An error occurred: {e}")
            return new_action.go_randomly()
        
    def should_run_away(self):
        escape_action = self.run_away_from_enemies()
        return escape_action is not None
    
    def reset(self, arena_description: arenas.ArenaDescription) -> None:
        self.my_knowledge.reset(arena_description)





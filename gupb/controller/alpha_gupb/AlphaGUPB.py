import random

from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.tiles import TileDescription
from gupb.model.effects import EffectDescription
from gupb.controller.alpha_gupb.pathfinder import pathfinder
import copy
from typing import NamedTuple, Optional, List

from collections import defaultdict

POSSIBLE_ACTIONS = [
    characters.Action.TURN_RIGHT,
    characters.Action.TURN_LEFT,
    characters.Action.STEP_FORWARD
]



class AlphaGUPB(controller.Controller):
    def __init__(self, first_name: str):
        self.first_name: str = first_name
        self.all_knowledge = {}
        self.positions = []
        self.knowledge_age = defaultdict(int)
        self.position = None
        self.champion = None
        self.facing = None
        self.menhir = None
        self.closest_enemy = None
        self.mist = []
        self.walkable_tiles = []

        

    def find_weapons(self):
        tiles_with_weapons = {}
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].loot and self.all_knowledge[tile].loot.name not in ['amulet', 'bow_loaded', 'bow_unloaded', 'Amulet']):
                tiles_with_weapons[tile] = self.all_knowledge[tile].loot
        return tiles_with_weapons
    
    def find_potion(self):
        tiles_with_potions = []
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].consumable and self.all_knowledge[tile].consumable.name == 'potion'):
                tiles_with_potions.append(tile)
        return tiles_with_potions
    
    def distance(self, p1, p2):
        return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5

    def closest_tile(self, pos, tiles):
        if(len(tiles) == 1):
            tiles = list(tiles)
            if(tiles[0][0] == self.position[0] and tiles[0][1] ==self.position[1]):
                return False
            else:
                return tiles[0]
        def distance(p1, p2):
            return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5
        
        # Filter out the pos tile from the list of tiles
        filtered_tiles = [tile for tile in tiles if tile != pos]
        
        # Return the closest tile from the filtered list
        return min(filtered_tiles, key=lambda tile: distance(pos, tile))

    def furthest_tiles(self, pos, tiles):
        def distance(p1, p2):
            return ((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2) ** 0.5
        filtered_tiles = [tile for tile in tiles if tile != pos]
        sorted_tiles = sorted(filtered_tiles, key=lambda tile: distance(pos, tile), reverse=True)
        return sorted_tiles

    def furthest_tile_from_enemy(self, furthest_tiles, enemy):
        for tile in furthest_tiles:
            if(self.distance(self.position, tile) < self.distance(enemy, tile)):
                return tile
        return []
        


    def get_blocks(self, knowledge):
        blocks = []
        for tile in knowledge:
            walkable = self.can_walk(tile)
            block = {"x": tile[0], "y": tile[1], "walkable":walkable}
            blocks.append(block)
        return blocks

    def can_walk(self, tile):
        tile = tuple(tile)
        if(tile not in self.all_knowledge):
            return False
        if(self.all_knowledge[tile].type == 'sea'):
            return False
        if(self.all_knowledge[tile].type == 'wall'):
            return False
        return True

    def easy_access(self, tile):
        pos = list(self.position)
        if(pos[0]==tile[0] and pos[1]==tile[1]):
            return [False, False]
        diff_x = tile[0] - pos[0]
        diff_y = tile[1] - pos[1]

        if(diff_x > 0):
            x_dir = 1
        elif(diff_x == 0):
            x_dir = 0
        else:
            x_dir = -1

        if(diff_y > 0):
            y_dir = 1
        elif(diff_y == 0):
            y_dir = 0
        else:
            y_dir = -1

        path = []
        cant_go_x = False
        cant_go_y = False

        while(pos[0] != tile[0] or pos[1] != tile[1]):

            if(pos[0] != tile[0]):
                pos[0] += x_dir
                if(self.can_walk(pos)):
                    cant_go_x = False
                    path.append(pos.copy())
                    if(pos[0]==tile[0] and pos[1]==tile[1]):
                        return [True, path]
                else:
                    cant_go_x = True
                    pos[0] -= x_dir

            if(pos[1] != tile[1]):
                pos[1] += y_dir
                if(self.can_walk(pos)):
                    cant_go_y = False
                    path.append(pos.copy())
                    if(pos[0]==tile[0] and pos[1]==tile[1]):
                        return [True, path]
                else:
                    cant_go_y = True
                    pos[1] -= y_dir
                
            if(cant_go_x and cant_go_y):
                return [False, False]
            if(cant_go_x and pos[1] == tile[1]):
                return [False, False]
            if(cant_go_y and pos[0] == tile[0]):
                return [False, False]
        return [True, path]
    
    def go_right(self):
        if(self.facing == characters.Facing.RIGHT):
            return characters.Action.STEP_FORWARD
        if(self.facing == characters.Facing.LEFT):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.UP):
            return characters.Action.TURN_RIGHT
        if(self.facing == characters.Facing.DOWN):
            return characters.Action.TURN_LEFT
        
    def go_left(self):
        if(self.facing == characters.Facing.RIGHT):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.LEFT):
            return characters.Action.STEP_FORWARD
        if(self.facing == characters.Facing.UP):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.DOWN):
            return characters.Action.TURN_RIGHT
        
    def go_up(self):
        if(self.facing == characters.Facing.UP):
            return characters.Action.STEP_FORWARD
        if(self.facing == characters.Facing.LEFT):
            return characters.Action.TURN_RIGHT
        if(self.facing == characters.Facing.RIGHT):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.DOWN):
            return characters.Action.TURN_LEFT   
        
    def go_down(self):
        if(self.facing == characters.Facing.RIGHT):
            return characters.Action.TURN_RIGHT
        if(self.facing == characters.Facing.LEFT):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.UP):
            return characters.Action.TURN_LEFT
        if(self.facing == characters.Facing.DOWN):
            return characters.Action.STEP_FORWARD   
            
    def is_enemy_front(self):
        front_coords = self.position + self.facing.value
        return self.all_knowledge[front_coords].character
    
    def go_to_center(self):
        if(self.position[0] > 12):
            new_pos = [self.position[0]-1, self.position[1]]
            if(self.can_walk(new_pos)):
                return self.go_left()
        elif(self.position[1] > 12):
            new_pos = [self.position[0], self.position[1]-1]
            if(self.can_walk(new_pos)):
                return self.go_up()
        if(self.position[0] < 12):
            new_pos = [self.position[0]+1, self.position[1]]
            if(self.can_walk(new_pos)):
                return self.go_right()
        if(self.position[1] < 12):
            new_pos = [self.position[0], self.position[1]+1]
            if(self.can_walk(new_pos)):
                return self.go_down()
        
        return random.choice(POSSIBLE_ACTIONS)

    def find_move(self, target_tile):
        if(target_tile[0]!=self.position[0]):
            direction = target_tile[0] - self.position[0]
            if(direction == 1):
                return(self.go_right())
            if(direction == -1):
                return(self.go_left())

        elif(target_tile[1]!=self.position[1]):
            direction = target_tile[1] - self.position[1]
            if(direction == 1):
                return(self.go_down())
            if(direction == -1):
                return(self.go_up())



    def run_away(self, tile):
        pos = list(self.position)
        if(pos[0]==tile[0] and pos[1]==tile[1]):
            return random.choice(POSSIBLE_ACTIONS)
        diff_x = tile[0] - pos[0]
        diff_y = tile[1] - pos[1]

        if(abs(diff_x)<abs(diff_y)):
            for tile in self.all_knowledge:
                if(diff_x>0):
                    if(tile[0] < pos[0] and self.can_walk(tile)):
                        return tile
                if(diff_x<0):
                    if(tile[0] < pos[0] and self.can_walk(tile)):
                        return tile
           
        for tile in self.all_knowledge:
            if(diff_y>0):
                if(tile[1] < pos[1] and self.can_walk(tile)):
                    return tile
            if(diff_y<0):
                if(tile[1] > pos[1] and self.can_walk(tile)):
                    return tile
        return False

    def get_enemies(self, tiles):
        enemies = {}
        for tile in tiles:
            if(tiles[tile].character and tiles[tile].character.controller_name!="AlphaGUPB"):
                enemies[tuple(tile)] = tiles[tile].character
        return enemies

    def attackable_tiles(self):
        if(self.weapon.name == 'bow_loaded'):
            attackable_tiles_down = []
            attackable_tiles_left = []
            attackable_tiles_right = []
            attackable_tiles_up = []
            for y in range(self.position[1]+1,50):
                attackable_tiles_down.append((self.position[0],y))

            for y in range(self.position[1]-1,-50, -1):
                attackable_tiles_up.append((self.position[0],y))

            for x in range(self.position[0]-1,-50, -1):
                attackable_tiles_left.append((x, self.position[1]))

            for x in range(self.position[0]+1,50):
                attackable_tiles_right.append((x,self.position[1]))
            
            
        elif(self.weapon.name == 'sword'):
            attackable_tiles_right = [(self.position[0]+1,self.position[1]),
                                (self.position[0]+2,self.position[1]),
                                (self.position[0]+3,self.position[1])]
            
            attackable_tiles_left = [(self.position[0]-1,self.position[1]),
                                (self.position[0]-2,self.position[1]),
                                (self.position[0]-3,self.position[1])]
            
            
            attackable_tiles_up = [(self.position[0],self.position[1]-1),
                                  (self.position[0],self.position[1]-2),
                                  (self.position[0],self.position[1]-3)]

            attackable_tiles_down =  [(self.position[0],self.position[1]+1),
                                     (self.position[0],self.position[1]+2),
                                     (self.position[0],self.position[1]+3)]


        elif(self.weapon.name == 'axe'):
            attackable_tiles_left = [(self.position[0]-1,self.position[1]-1),
                                (self.position[0]-1,self.position[1]),
                                (self.position[0]-1,self.position[1]+1)]
            
            attackable_tiles_right = [(self.position[0]+1,self.position[1]-1),
                                (self.position[0]+1,self.position[1]),
                                (self.position[0]+1,self.position[1]+1)]
            
            attackable_tiles_up = [(self.position[0]-1,self.position[1]-1),
                                (self.position[0],self.position[1]-1),
                                (self.position[0]+1,self.position[1]-1)]
            
            attackable_tiles_down = [(self.position[0]-1,self.position[1]+1),
                                (self.position[0],self.position[1]+1),
                                (self.position[0]+1,self.position[1]+1)]
            
 
        elif(self.weapon.name == 'amulet'):
            attackable_tiles_left = attackable_tiles_down = attackable_tiles_right = attackable_tiles_up =[(self.position[0]+1,self.position[1]+1),
                                                                                                        (self.position[0]-1,self.position[1]+1),
                                                                                                        (self.position[0]+1,self.position[1]-1),
                                                                                                        (self.position[0]-1,self.position[1]-1),
                                                                                                        (self.position[0]+2,self.position[1]+2),
                                                                                                        (self.position[0]-2,self.position[1]+2),
                                                                                                        (self.position[0]+2,self.position[1]-2),
                                                                                                        (self.position[0]-2,self.position[1]-2)]
        elif(self.weapon.name == 'knife'):
            attackable_tiles_left = [(self.position[0]-1,self.position[1])]
            
            attackable_tiles_right = [(self.position[0]+1,self.position[1])]
            
            attackable_tiles_up = [(self.position[0],self.position[1]-1)]
            
            attackable_tiles_down = [(self.position[0],self.position[1]+1)]
        
        else:
            return [], [], [], []
        return attackable_tiles_left,attackable_tiles_right, attackable_tiles_up, attackable_tiles_down
    
    def attack_enemy(self, direction):
        if(direction == "left"):
            if(self.facing == characters.Facing.LEFT):
                return characters.Action.ATTACK
            elif(self.facing == characters.Facing.UP):
                return characters.Action.TURN_LEFT
            elif(self.facing == characters.Facing.DOWN):
                return characters.Action.TURN_RIGHT
            
        if(direction == "right"):
            if(self.facing == characters.Facing.RIGHT):
                return characters.Action.ATTACK
            elif(self.facing == characters.Facing.UP):
                return characters.Action.TURN_RIGHT
            elif(self.facing == characters.Facing.DOWN):
                return characters.Action.TURN_LEFT
                
        if(direction == "up"):          
            if(self.facing == characters.Facing.UP):
                return characters.Action.ATTACK
            elif(self.facing == characters.Facing.LEFT):
                return characters.Action.TURN_RIGHT
            elif(self.facing == characters.Facing.RIGHT):
                return characters.Action.TURN_LEFT
            
        if(direction == "down"):
            if(self.facing == characters.Facing.DOWN):
                return characters.Action.ATTACK
            elif(self.facing == characters.Facing.RIGHT):
                return characters.Action.TURN_RIGHT
            elif(self.facing == characters.Facing.LEFT):
                return characters.Action.TURN_LEFT
            
        return characters.Action.TURN_LEFT
    
    def can_attack(self):
        attackable_tiles_left,attackable_tiles_right, attackable_tiles_up, attackable_tiles_down = self.attackable_tiles()
        if (len(attackable_tiles_down)+len(attackable_tiles_left)+len(attackable_tiles_right)+len(attackable_tiles_up)==0):
            return False
        enemies = self.get_enemies(self.all_knowledge)
        if not enemies:
            return False
        for enemy in enemies: 
            if enemy in attackable_tiles_left:
                return "left"
            if enemy in attackable_tiles_right:
                return "right"
            if enemy in attackable_tiles_up:
                return "up"
            if enemy in attackable_tiles_down:
                return "down"
        return False


    def get_mist(self):
        tiles = []
        for tile in self.all_knowledge:
            effects = self.all_knowledge[tile].effects
            for effect in effects:
                if(isinstance(effect, EffectDescription) and effect.type == 'mist'):
                    tiles.append(tile)
        return tiles
    
    def get_menhir(self):
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].type == 'menhir'):
                return tile
        return None
    
    def get_closest_mist(self, tiles):
        pos_x = self.position[0]
        pos_y = self.position[1]
        closest_tiles = []
        for tile in tiles:
            min_distance_x = 999
            min_distance_y = 999

            tile_distance_x = abs(pos_x - tile[0])
            tile_distance_y = abs(pos_y - tile[1])
            if(tile_distance_x <= min_distance_x or tile_distance_y <= min_distance_y):
                closest_tiles.append(tile)
            min_distance_x = min(min_distance_x, tile_distance_x)
            min_distance_y = min(min_distance_y, tile_distance_y)

        return closest_tiles

    def get_tiles_next_to_mist(self, tiles_with_mist):
        tiles_next_to_mist = []
        pos_x = self.position[0]
        pos_y = self.position[1]
        for tile in tiles_with_mist:
            if(tile[0] > pos_x):
                x = tile[0]-3
            else:
                x = tile[0]+3

            if(tile[1] > pos_y):
                y = tile[1]-3
            else:
                y = tile[1]+3
            tiles_next_to_mist.append((x,y))
        return tiles_next_to_mist

                    
    def update_knowledge(self, visible_tiles):
        for visible_tile in visible_tiles:
            self.all_knowledge[visible_tile] = copy.copy(visible_tiles[visible_tile])
            self.knowledge_age[visible_tile] = 0

        tiles_to_delete = []
        for tile in self.knowledge_age:
            self.knowledge_age[tile] +=1
            if(self.knowledge_age[tile]> 6):
                tiles_to_delete.append(tile)
        for tile in tiles_to_delete:
            self.all_knowledge[tile]= TileDescription(type = self.all_knowledge[tile].type, character=None, loot = None, consumable=None, effects= self.all_knowledge[tile].effects)
            del self.knowledge_age[tile]

    def see_enemy(self, tiles):
        for tile in tiles:
            if(tiles[tile].character!=None and tiles[tile].character.controller_name!="AlphaGUPB"):
                return True
        return False
    
    def get_champion(self):
        for tile in self.all_knowledge:
            if(tile == self.position):
                return self.all_knowledge[tile].character

    def position_amulet(self, enemy_position):
        if(enemy_position[0] >= self.position[0] and enemy_position[1] >= self.position[1]):
            return (enemy_position[0]-1, enemy_position[1]-1)
        
        elif(enemy_position[0] >= self.position[0] and enemy_position[1] <= self.position[1]):
            return (enemy_position[0]-1, enemy_position[1]+1)
        
        elif(enemy_position[0] <= self.position[0] and enemy_position[1] <= self.position[1]):
            return (enemy_position[0]+1, enemy_position[1]-1)
        
        elif(enemy_position[0] <= self.position[0] and enemy_position[1] >= self.position[1]):
            return (enemy_position[0]+1, enemy_position[1]+1)
    
    def should_attack(self, enemy):
        enemy = self.all_knowledge[enemy].character
        if not enemy:
            return True
        if(self.champion.health<=enemy.health):
            return False
        if(self.champion.weapon.name in ['Axe', 'Sword', 'axe', 'sword']):
            return True
        if(enemy.weapon.name in ['amulet, Amulet','knife']):
            return True
        return False

    def should_attack2(self, enemy):
        enemy = self.all_knowledge[enemy].character
        if not enemy:
            return True
        if(self.champion.health<enemy.health):
            return False
        return True
    

    def can_step_forward(self):
        new_position = self.position + self.facing.value
        return self.all_knowledge[new_position].type == 'land'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, AlphaGUPB):
            return self.first_name == other.first_name
        return False

    def __hash__(self) -> int:
        return hash(self.first_name)

    def decide(self, knowledge: characters.ChampionKnowledge) -> characters.Action:
        self.update_knowledge(knowledge.visible_tiles)
        self.position = knowledge.position
        self.positions.append(self.position)
        self.mist = self.get_mist()
        blocks = self.get_blocks(self.all_knowledge)
        self.facing= knowledge.visible_tiles[knowledge.position].character.facing
        self.weapon = knowledge.visible_tiles[knowledge.position].character.weapon
        enemies = self.get_enemies(self.all_knowledge)
        if(len(enemies)>0):
            self.closest_enemy = self.closest_tile(self.position, enemies.keys())
        else:
            self.closest_enemy = None
            
        can_attack = self.can_attack()  
        tiles_with_potions = self.find_potion()
        weapons = self.find_weapons()
        self.champion = self.get_champion()

        for tile in self.all_knowledge:
                    if(self.can_walk(tile) and (tile[0]!= self.position[0] and tile[1]!=self.position[1])):
                        self.walkable_tiles.append(tile)

        if not self.menhir:
            self.menhir = self.get_menhir()


        if (self.closest_enemy and (self.weapon in ['bow_loaded', 'bow_unloaded'])):
            distance = self.distance(self.position, self.closest_enemy)
            if(distance < 4):
                furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                if(furthest_tile!= self.position):
                    path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                    return self.find_move(path[1])
    
        if(can_attack):
            if(self.champion.weapon.name =='bow_loaded'):
                return self.attack_enemy(can_attack)
            elif(self.should_attack2(self.closest_enemy)):
                return self.attack_enemy(can_attack)
            else:
                furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                return self.find_move(path[1])
        
        if(len(self.positions)>5 and len(set(self.positions[-9:])) == 1):
            self.positions = []
            return random.choice(POSSIBLE_ACTIONS)
    
        if(len(self.mist)>0):
            closest_mist = self.closest_tile(self.position, self.mist)
            if(abs(closest_mist[0] - self.position[0])< 8 and  abs(closest_mist[1] - self.position[1])<8):
                if(self.menhir): 
                    if(self.position != self.menhir):
                        path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.menhir)
                        return self.find_move(path[1])
                    else:
                        return characters.Action.ATTACK
                furthest_tile = self.furthest_tiles(closest_mist, self.walkable_tiles)[0]
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                return self.find_move(path[1])
        
        if(len(tiles_with_potions)>0):
            closest_potion= self.closest_tile(self.position, tiles_with_potions)
            if(closest_potion != self.position):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_potion)
                if(path[1] not in self.mist):
                    return self.find_move(path[1])  


        if(self.weapon.name in ['axe', 'sword', 'knife'] and self.closest_enemy):
            if(self.should_attack(self.closest_enemy)):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.closest_enemy)
                if(path[1] not in self.mist):
                    return self.find_move(path[1])
            
        if(self.weapon.name == 'bow_unloaded'):
            return characters.Action.ATTACK
        if(len(weapons)!=0 and self.weapon.name in ['knife', 'amulet', 'Amulet', 'bow_loaded', 'bow_unloaded']):
            closest_weapon = self.closest_tile(self.position, weapons.keys())
            if closest_weapon:
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_weapon)
                if(path[1]!=self.position and (path[1] not in self.mist)):
                    return self.find_move(path[1])
        
        if self.closest_enemy:
            distance = self.distance(self.position, self.closest_enemy)
            if(distance<8):
                if len(self.walkable_tiles)>0:
                    furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                    furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                    if(furthest_tile!= self.position):
                        path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                        return self.find_move(path[1])
                
        if not self.menhir:
            if(self.can_step_forward()):
                return controller.characters.Action.STEP_FORWARD
        return controller.characters.Action.TURN_LEFT


    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.all_knowledge = {}
        self.positions = []
        self.knowledge_age = defaultdict(int)
        self.position = None
        self.champion = None
        self.facing = None
        self.menhir = None
        self.closest_enemy = None
        self.mist = []
        self.walkable_tiles = []


    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ALPHA

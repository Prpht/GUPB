import random
from gupb import controller
from gupb.model import arenas
from gupb.model import characters
from gupb.model.tiles import TileDescription
from gupb.model.effects import EffectDescription
from gupb.controller.alpha_gupb.pathfinder import pathfinder
import copy
from typing import NamedTuple, Optional, List
from gupb.controller.alpha_gupb.movement.movement import go_down, go_left, go_right, go_up, go_down_slow, go_left_slow, go_right_slow, go_up_slow
from gupb.controller.alpha_gupb.combat.combat import attackable_tiles, attack_enemy, can_attack_check
from gupb.model import arenas
import time
import numpy as np

from collections import defaultdict

POSSIBLE_ACTIONS = [
    characters.Action.TURN_RIGHT,
    characters.Action.TURN_LEFT,
    characters.Action.STEP_FORWARD
]

def timeit(func):
    """Decorator to time a function or method"""
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        #print(f"{func.__name__} took {end-start} seconds to run.")
        return result
    return wrapper

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
        self.seen_tiles = set()
        self.last_hp = 8
        self.arena_knowledge = 0
        self.have_tile = 0
        self.random_tile = None
        self.enemy_attackable_tiles = []
        self.tiles_to_attack_enemy = []

    def find_weapons(self):
        tiles_with_weapons = {}
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].loot and self.all_knowledge[tile].loot.name not in ['bow_loaded', 'bow_unloaded', 'amulet']):
                tiles_with_weapons[tile] = self.all_knowledge[tile].loot
        return tiles_with_weapons

    def find_axe(self):
        tiles_with_weapons = {}
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].loot and self.all_knowledge[tile].loot.name == 'axe'):
                tiles_with_weapons[tile] = self.all_knowledge[tile].loot
        return tiles_with_weapons
    
    def find_potion(self):
        tiles_with_potions = []
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].consumable and self.all_knowledge[tile].consumable.name == 'potion'):
                tiles_with_potions.append(tile)
        return tiles_with_potions
    

    def find_forest(self):
        tiles_with_forest = []
        for tile in self.all_knowledge:
            if(self.all_knowledge[tile].type == 'forest'):
                tiles_with_forest.append(tile)
        return tiles_with_forest
    
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
    
    def not_walked_tiles(self):
        tiles = []
        for tile in self.all_knowledge:
            if(tile not in self.seen_tiles and self.can_walk(tile)):
                tiles.append(tile)
        return tiles


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

        
            
    def is_enemy_front(self):
        front_coords = self.position + self.facing.value
        return self.all_knowledge[front_coords].character
    

    def find_move(self, target_tile):
        if(target_tile[0]!=self.position[0]):
            direction = target_tile[0] - self.position[0]
            if(direction == 1):
                return(go_right(self.facing))
            if(direction == -1):
                return(go_left(self.facing))

        elif(target_tile[1]!=self.position[1]):
            direction = target_tile[1] - self.position[1]
            if(direction == 1):
                return(go_down(self.facing))
            if(direction == -1):
                return(go_up(self.facing))
            

    def find_move_slow(self, target_tile):
        if(target_tile[0]!=self.position[0]):
            direction = target_tile[0] - self.position[0]
            if(direction == 1):
                return(go_right_slow(self.facing))
            if(direction == -1):
                return(go_left_slow(self.facing))

        elif(target_tile[1]!=self.position[1]):
            direction = target_tile[1] - self.position[1]
            if(direction == 1):
                return(go_down_slow(self.facing))
            if(direction == -1):
                return(go_up_slow(self.facing))
            


    def get_enemies(self, tiles):
        enemies = {}
        for tile in tiles:
            if(tiles[tile].character and tiles[tile].character.controller_name!="AlphaGUPB"):
                enemies[tuple(tile)] = tiles[tile].character
        return enemies


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

    @timeit
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

    @timeit
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
        #print("updating knowledge")
        for visible_tile in visible_tiles:
            if(isinstance(visible_tiles[visible_tile],TileDescription)):
                self.all_knowledge[visible_tile] = copy.copy(visible_tiles[visible_tile])
                self.knowledge_age[visible_tile] = 0
            else:
                self.all_knowledge[visible_tile] = visible_tiles[visible_tile].description()
 
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
        if(self.weapon.name in ['amulet', 'axe']):
            return True
        enemy = self.all_knowledge[enemy].character
        if not enemy:
            return True
        if(self.champion.health - enemy.health >2):
            return True
        if(self.champion.health<=enemy.health):
            return False
        if(self.champion.weapon.name in ['Axe', 'Sword', 'axe', 'sword', 'knife']):
            return True
        if(enemy.weapon.name in ['amulet, Amulet','knife']):
            return True
        return False

    def should_attack2(self, enemy):
        #print("pos", self.position)
        #print("enemy attackable tiles ",self.enemy_attackable_tiles)
        pos_tuple = (self.position[0], self.position[1])
        if(pos_tuple in self.tiles_with_forest):
            return True
        if(pos_tuple not in self.enemy_attackable_tiles):
            return True
        enemy = self.all_knowledge[enemy].character
        #if(self.weapon.name in ['sword', 'axe', 'amulet']):
        #    return True
        if not enemy:
            return True
        if(self.champion.health<enemy.health):
            return False
        return True

    def get_enemy_weapon(self, enemy):
        for tile in self.all_knowledge:
            if (tile==enemy):
                return self.all_knowledge[tile].character.weapon.name
        
    def can_step(self, direction):
        if(direction=='up'): new_position=(self.position[0],self.position[1]-1)
        if(direction=='down'): new_position=(self.position[0],self.position[1]+1)
        if(direction=='right'): new_position=(self.position[0]+1,self.position[1])
        if(direction=='left'): new_position=(self.position[0]-1,self.position[1])

        if(self.can_walk(new_position)):
            #print("can walk", new_position)
            return True
        #print("cant walk ", new_position)
        return False
    
    def close_tiles(self):
        return [(self.position[0]-1, self.position[1]),
                (self.position[0]+1, self.position[1]),
                (self.position[0], self.position[1]-1),
                (self.position[0], self.position[1]+1)]
    
    def attackable_tiles_enemy(self, enemies):
        attackable_tiles_list = []
        for enemy in enemies:
            attackable_tiles_enemy = (attackable_tiles(self.get_enemy_weapon(enemy),enemy))
            for direction in attackable_tiles_enemy:
                for tile in direction:
                    attackable_tiles_list.append(tile)
        #print("ATTACKABLE ", attackable_tiles_list)
        return attackable_tiles_list

    

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
        #print("start")
        arena = arenas.Arena.load(self.arena.name)
        if not self.arena_knowledge:
            self.update_knowledge(arena.terrain)
            self.arena_knowledge = 1
            #print("arena knowledge updated")
        self.update_knowledge(knowledge.visible_tiles)
        #print("updated 2")
        self.alive_champions = knowledge.no_of_champions_alive
        self.position = knowledge.position
        self.positions.append(self.position)
        self.mist = self.get_mist()
        self.facing= knowledge.visible_tiles[knowledge.position].character.facing
        self.weapon = knowledge.visible_tiles[knowledge.position].character.weapon
        enemies = self.get_enemies(self.all_knowledge)
        for tile in knowledge.visible_tiles:
            self.seen_tiles.add(tile)
        self.attackable_tiles = attackable_tiles(self.weapon.name, self.position)
        tiles_with_potions = self.find_potion()
        self.tiles_with_forest = self.find_forest()
        #print("potions found")
        weapons = self.find_weapons()
        #print("weapons found")
        self.champion = self.get_champion()
        #print("champion got")
        self.explored_tiles = []

        for tile in arena.terrain:
            if(self.can_walk(tile) and (tile[0]!= self.position[0] and tile[1]!=self.position[1]) and tile not in self.mist):
                self.walkable_tiles.append(tile)
        self.explored_tiles.append(self.position)
        blocks = self.get_blocks(self.all_knowledge)
        if not self.menhir:
            self.menhir = self.get_menhir()

        #print("enemies ", enemies)
        if(len(enemies)>0):
            self.closest_enemy = self.closest_tile(self.position, enemies.keys())
            self.enemy_attackable_tiles  = self.attackable_tiles_enemy(enemies)
            self.tiles_to_attack_enemy = attackable_tiles(self.weapon.name, self.closest_enemy)
        else:
            self.closest_enemy = None
            self.enemy_attackable_tiles = []

        can_attack = can_attack_check(enemies, self.attackable_tiles) 

        pos_tuple = (self.position[0], self.position[1])
        #print("position ", pos_tuple)
        #print("enemy attackable ", self.enemy_attackable_tiles)
        if(pos_tuple in self.enemy_attackable_tiles and not can_attack and self.position not in self.tiles_with_forest):
            #print("can be attacked!")
            for tile in self.close_tiles():
                if(tile not in self.enemy_attackable_tiles and self.can_walk(tile) and tile != self.closest_enemy and tile in attackable_tiles(self.weapon, self.closest_enemy)):
                    #print("tactical move cant attack from ",self.position, " to ", tile)
                    return self.find_move(tile)
            for tile in self.close_tiles():
                if(tile not in self.enemy_attackable_tiles and self.can_walk(tile) and tile != self.closest_enemy):
                    #print("tactical move cant attack from ",self.position, " to ", tile)
                    return self.find_move(tile)

            #print("no tactical move")
        else:
            #print("cant be attacked")
            pass
            
         

        """
        if (self.closest_enemy and (self.weapon.name in ['bow_loaded', 'bow_unloaded'])):
            #print("close enemy and bow") 
            distance = self.distance(self.position, self.closest_enemy)
            if(distance < 3):
                furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                if(furthest_tile!= self.position):
                    path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                    return self.find_move(path[1])
        """
    
        if(can_attack):
            if(knowledge.no_of_champions_alive ==2):
                return attack_enemy(self.facing, can_attack)
            #print('can attack ', can_attack)
            if(self.weapon.name =='bow_loaded'):
                #print("attacking with bow")
                return attack_enemy(self.facing, can_attack)
            if(self.should_attack2(self.closest_enemy)):
                #print("attacking")
                return attack_enemy(self.facing, can_attack)
            else:
                #print("shouldnt attack")
                #print("looking for tactical move")
                for tile in self.close_tiles():
                    if(tile not in self.enemy_attackable_tiles and tile in self.tiles_to_attack_enemy and self.can_walk(tile)):
                        #print("tactical move")
                        return self.find_move(tile)
                #print("no tactical move")
                if can_attack == 'right': 
                    if(self.can_step('left')):
                        return self.find_move((self.position[0]-1,self.position[1]))
                    if(self.can_step('up')):
                        return self.find_move((self.position[0],self.position[1]-1))
                    if(self.can_step('down')):
                        return self.find_move((self.position[0],self.position[1]+1))
                    
                if can_attack == 'left': 
                    if(self.can_step('right')):
                        return self.find_move((self.position[0]+1,self.position[1]))
                    if(self.can_step('up')):
                        return self.find_move((self.position[0],self.position[1]-1))
                    if(self.can_step('down')):
                        return self.find_move((self.position[0],self.position[1]+1))
                
                if can_attack == 'up': 
                    if(self.can_step('right')):
                        return self.find_move((self.position[0]+1,self.position[1]))
                    if(self.can_step('left')):
                        return self.find_move((self.position[0]-1,self.position[1]))
                    if(self.can_step('down')):
                        return self.find_move((self.position[0],self.position[1]+1))
                    
                if can_attack == 'down': 
                    if(self.can_step('up')):
                        return self.find_move((self.position[0],self.position[1]-1))
                    if(self.can_step('right')):
                        return self.find_move((self.position[0]+1,self.position[1]))
                    if(self.can_step('left')):
                        return self.find_move((self.position[0]-1,self.position[1]))
                
                

                #furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                #furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                #path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                #if(path):
                #    #print("and running away")
                #    return self.find_move(path[1])
                #else:
                #    #print("attacking anyway")
                #    return attack_enemy(self.facing, can_attack)
                
        if(len(self.positions)>5 and len(set(self.positions[-9:])) == 1):
            self.positions = []
            #print("random move")
            return random.choice(POSSIBLE_ACTIONS)
    
        if(len(self.mist)>0):
            #print("mist")
            closest_mist = self.closest_tile(self.position, self.mist)
            if(self.distance(self.position, closest_mist) < 10):
                if(self.menhir): 
                    #print("know menhir")
                    if(self.distance(self.position, self.menhir) > 3):
                        path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.menhir)
                        if path:
                            #print("going to menhir")
                            return self.find_move_slow(path[1])
                else:
                    for tile in self.walkable_tiles:
                        if (self.distance(self.position,tile)<self.distance(closest_mist,tile)):
                            path = pathfinder.astar(blocks, (self.position[0], self.position[1]), tile)
                            if(path):
                                #print("no menhir, running away")
                                return self.find_move_slow(path[1])
                        
               # furthest_tiles = self.furthest_tiles(closest_mist, self.walkable_tiles)
               # for tile in furthest_tiles:
               #     if (tile not in self.mist and self.can_walk(tile)):
               #         path = pathfinder.astar(blocks, (self.position[0], self.position[1]), tile)
               #         if (path):
               #             #print("no menhir, running away")
               #             return self.find_move(path[1])
        
        #print("checking for potions")
        if(len(tiles_with_potions)>0):
            closest_potion= self.closest_tile(self.position, tiles_with_potions)
            if(closest_potion != self.position):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_potion)
                if path:
                    if(path[1] not in self.mist):
                        #print("going to potion")
                        return self.find_move(path[1])  
        #print("no potions")




        #print("looking for axe")
        self.axes = self.find_axe()
        if (self.weapon.name != 'axe' and len(self.axes)>0):
            closest_axe = self.closest_tile(self.position, self.axes.keys())
            if closest_axe:
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_axe)
                if(path):
                    if(path[1]!=self.position and (path[1] not in self.mist) and len(path)<12 and path[1] not in self.enemy_attackable_tiles):
                        #print("going to axe")
                        return self.find_move_slow(path[1])
                    if(len(path)<=3):
                        #print("going to axe")
                        return self.find_move_slow(path[1])
                    else:
                        #print("axe too far away")
                        pass

        #print("checking for chasing")
        if(self.weapon.name in ['axe', 'sword', 'knife'] and self.closest_enemy):
            if(self.should_attack(self.closest_enemy)):
                #print("should attack")
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.closest_enemy)
                if(path[1] not in self.mist):
                    #print("chasing enemy")
                    return self.find_move_slow(path[1])
                
        #print("shouldnt chase")


        if(self.weapon.name == 'bow_unloaded'):
            return characters.Action.ATTACK
        if(len(weapons)!=0 and self.weapon.name in ['knife', 'bow_loaded', 'bow_unloaded','amulet']):
            closest_weapon = self.closest_tile(self.position, weapons.keys())
            #print("closest weapon", closest_weapon)
            if closest_weapon:
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_weapon)
                if(path):
                    if(path[1]!=self.position and (path[1] not in self.mist) and len(path)<12 and path[1] not in self.enemy_attackable_tiles):
                        #print("going to weapon")
                        return self.find_move_slow(path[1])
                    else:
                        #print("weapon too far away")
                        pass

        #print("checking for forest")
        if(len(self.tiles_with_forest)>0 and (self.position not in self.tiles_with_forest and self.weapon.name !='axe' and self.menhir) or knowledge.no_of_champions_alive>8 ):
            closest_forest=  self.closest_tile(self.position, self.tiles_with_forest)
            if(closest_forest != self.position and self.distance(self.position,closest_forest)<20):
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_forest)
                if path:
                    if(path[1] not in self.mist and path[1] not in self.enemy_attackable_tiles):
                        #print("going to forest")
                        return self.find_move_slow(path[1])  
        #print("no forest")
        
        if (self.closest_enemy and (self.position not in self.tiles_with_forest)):
            enemy_weapon = self.get_enemy_weapon(self.closest_enemy)
            distance = self.distance(self.position, self.closest_enemy)
            #print("distance to closest enemy ", distance)
            if(distance<=2  and self.weapon.name !='amulet' and enemy_weapon not in ['sword', 'axe', 'bow_loaded', 'bow_unloaded'] and self.should_attack(self.closest_enemy)):
                #print("trying to predict attack")
                #path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.closest_enemy)
                path = self.closest_enemy
                #print("got path", path," to ", self.closest_enemy)
                if(path[0]<self.position[0]):
                    direction = "left"
                elif(path[0]>self.position[0]):
                    direction = "right"
                elif(path[1] > self.position[1]):
                    direction = "down"
                else:
                    direction = "up"
                    #print("predicting attack ", direction)
                return attack_enemy(self.facing, direction)
            elif(distance<6):
                #print("trying to run away")
                if len(self.walkable_tiles)>0:
                    #print("know some walkable tiles")
                    furthest_tiles = self.furthest_tiles(self.closest_enemy, self.walkable_tiles)
                    furthest_tile = self.furthest_tile_from_enemy(furthest_tiles, self.closest_enemy)
                    #print("futhest tile ",furthest_tile)
                    if furthest_tile:
                        if(furthest_tile!= self.position):
                            path = pathfinder.astar(blocks, (self.position[0], self.position[1]), furthest_tile)
                            if(path):
                                #print("got path len ", len(path))
                                #print("running away from enemy to ", furthest_tile)
                                #print("enemy at ", self.closest_enemy)
                                if(distance <=2):
                                    return self.find_move(path[1])
                                else:
                                    return self.find_move_slow(path[1])
                    

  
        if(self.champion.health<self.last_hp):
            self.last_hp = self.champion.health
            #print("someone is attacking")
            if(self.can_step('right')):
                return self.find_move((self.position[0]+1,self.position[1]))
            if(self.can_step('up')):
                return self.find_move((self.position[0],self.position[1]-1))
            if(self.can_step('down')):
                return self.find_move((self.position[0],self.position[1]+1))
            if(self.can_step('left')):
                return self.find_move((self.position[0]-1,self.position[1]))
            
        #and knowledge.no_of_champions_alive <9)) and not (self.position in self.tiles_with_forest)
        if ((not self.menhir and knowledge.no_of_champions_alive<8)  or self.weapon.name =='axe'):    #xd
        #if not self.menhir and self.alive_champions < 5 or self.last_hp > 8:
            if not self.random_tile:
                self.random_tile = random.choice(self.walkable_tiles)

            if self.random_tile not in self.seen_tiles:
                path = pathfinder.astar(blocks, (self.position[0], self.position[1]), self.random_tile)
                #print("exploring")
                #print(self.random_tile)
                if path and path[1] not in self.enemy_attackable_tiles:
                    return self.find_move_slow(path[1])
                else:
                    self.random_tile = None
            else:
                self.random_tile = None


            #print("left")
            return controller.characters.Action.TURN_LEFT
            #print('exploring')
            not_explored = self.not_walked_tiles()
            if not not_explored:
                #print('no tiles to explore')
                pass
            closest_tile = self.closest_tile(self.position, not_explored)
            #print("going to", closest_tile)
            #print("pos", self.position)
            path = pathfinder.astar(blocks, (self.position[0], self.position[1]), closest_tile)
            return self.find_move(path[1])
            #print("running :)")
            if(self.can_step_forward()):
                return controller.characters.Action.STEP_FORWARD
        #print("left")
        return controller.characters.Action.TURN_LEFT


    def praise(self, score: int) -> None:
        pass

    def reset(self, game_no: int, arena_description: arenas.ArenaDescription) -> None:
        self.arena = arena_description
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
        self.explored_tiles = []
        self.arena_knowledge = 0
        self.enemy_attackable_tiles  = []

    @property
    def name(self) -> str:
        return f'{self.first_name}'

    @property
    def preferred_tabard(self) -> characters.Tabard:
        return characters.Tabard.ALPHA